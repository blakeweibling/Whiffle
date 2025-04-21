import cv2
import numpy as np
import json
import os
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from collections import OrderedDict
import platform
import pygame
import random
import requests
import threading
import queue

# Initialize Pygame mixer for sound effects and music
pygame.mixer.init()

# Fixed radius for scoring zones
ZONE_RADIUS = 20
CALIBRATION_VISUAL_RADIUS = 20
TOTAL_ZONES = 21
TIMED_MODE_DURATION = 120  # 2 minutes

# Files
CALIBRATION_FILE = "whiffle_zones.json"
HIGH_SCORE_FILE = "whiffle_high_score.json"
CONFIG_FILE = "whiffle_config.json"

# Supabase configuration for online leaderboard (optional, disabled for Pi to reduce load)
SUPABASE_URL = "https://jtkbujumrobglftzokcs.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0a2J1anVtcm9iZ2xmdHpva2NzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMTM4NzcsImV4cCI6MjA1NzU4OTg3N30.OibLuqr3X922SUSBL8yGxDw8uwuTjivH97-2wNhJDqs"
LEADERBOARD_ENDPOINT = f"{SUPABASE_URL}/rest/v1/leaderboard"

# Detection settings (simplified for Pi)
BALL_COLOR_RANGE = {
    "lower_white": [0, 0, 180],
    "upper_white": [180, 70, 255],
    "lower_red": [0, 120, 120],
    "upper_red": [5, 255, 255]
}
MIN_CONTOUR_AREA = 20  # Reduced for smaller resolution
MIN_RADIUS = 4
RED_MIN_CONTOUR_AREA = 30
RED_MIN_RADIUS = 6
RED_MIN_CIRCULARITY = 0.85
RED_BALL_LIMIT = 1
RED_BALL_COOLDOWN = 2.0

# Particle effect settings (reduced for Pi)
PARTICLE_COUNT = 10
PARTICLE_LIFETIME = 300
PARTICLE_MAX_SPEED = 3
PARTICLE_MAX_SIZE = 5

# Power-up settings
POWER_UP_SPAWN_INTERVAL = 15
POWER_UP_DURATION = 10
POWER_UP_MULTIPLIER = 3
POWER_UP_EXTRA_TIME = 10
POWER_UP_TYPES = ["Score Multiplier", "Slow Motion", "Extra Time", "Double Balls"]

# Game state
current_score = 0
high_score = 0
high_score_initials = "N/A"
scored_ball_ids = set()

# Webcam backend for Raspberry Pi
WEBCAM_BACKEND = cv2.CAP_V4L2
ALTERNATE_WEBCAM_BACKEND = cv2.CAP_ANY

def list_webcams():
    index = 0
    available_cameras = []
    while index < 10:
        cap = cv2.VideoCapture(index, WEBCAM_BACKEND)
        if not cap.isOpened():
            cap = cv2.VideoCapture(index, ALTERNATE_WEBCAM_BACKEND)
        if not cap.isOpened():
            break
        ret, frame = cap.read()
        if ret:
            available_cameras.append(index)
        cap.release()
        index += 1
    return available_cameras

def select_webcam():
    try:
        cameras = list_webcams()
        if not cameras:
            tk.messagebox.showerror("Error", "No webcams found. Please connect a camera and restart.")
            return None
        if len(cameras) == 1:
            print(f"Only one webcam found at index {cameras[0]}. Using it.")
            return cameras[0]
        print("Available webcams:")
        for idx in cameras:
            print(f"Index {idx}")
        while True:
            choice = int(input("Select a webcam index (e.g., 0, 1, etc.): "))
            if choice in cameras:
                return choice
            print("Invalid index. Please choose from the available indices.")
    except ValueError:
        tk.messagebox.showerror("Error", "Invalid input. Please enter a number.")
        return None
    except Exception as e:
        tk.messagebox.showerror("Error", f"Failed to detect webcams: {e}")
        return None

def load_point_zones(filename=CALIBRATION_FILE):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            zones = [(zone['x'], zone['y'], ZONE_RADIUS, zone['points']) for zone in data if not zone.get('special')]
            special_hole = next(((zone['x'], zone['y'], ZONE_RADIUS, zone['points']) for zone in data if zone.get('special')), None)
            return zones, special_hole
    return [], None

def save_point_zones(point_zones, special_hole, filename=CALIBRATION_FILE):
    data = [{'x': x, 'y': y, 'points': points} for (x, y, _, points) in point_zones]
    if special_hole:
        x, y, _, points = special_hole
        data.append({'x': x, 'y': y, 'points': points, 'special': True})
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Zones saved to {filename}")

def load_high_score():
    global high_score, high_score_initials
    try:
        headers = {"apikey": SUPABASE_API_KEY, "Authorization": f"Bearer {SUPABASE_API_KEY}"}
        response = requests.get(LEADERBOARD_ENDPOINT, headers=headers, params={"order": "score.desc", "limit": 5})
        response.raise_for_status()
        leaderboard = response.json()
        if leaderboard:
            high_score = leaderboard[0]["score"]
            high_score_initials = leaderboard[0]["initials"]
        return leaderboard
    except requests.RequestException as e:
        print(f"Error fetching leaderboard: {e}")
        if os.path.exists(HIGH_SCORE_FILE):
            with open(HIGH_SCORE_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    high_score = data[0]["score"]
                    high_score_initials = data[0]["initials"]
                    return data
        return []

def save_high_score(initials="N/A", new_score=None, leaderboard=None):
    global high_score, high_score_initials
    if new_score is None:
        return

    # Skip online saving on Pi to reduce network load; use local storage only
    if leaderboard is None:
        leaderboard = load_high_score()
    leaderboard.append({"score": new_score, "initials": initials if initials.strip() else "N/A"})
    leaderboard = sorted(leaderboard, key=lambda x: x["score"], reverse=True)[:5]
    with open(HIGH_SCORE_FILE, 'w') as f:
        json.dump(leaderboard, f)

    leaderboard = load_high_score()
    if leaderboard:
        high_score = leaderboard[0]["score"]
        high_score_initials = leaderboard[0]["initials"]

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"sound_effects_enabled": True, "tutorial_shown": False}

def save_config(sound_effects_enabled, tutorial_shown):
    data = {"sound_effects_enabled": sound_effects_enabled, "tutorial_shown": tutorial_shown}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f)

def set_webcam_resolution(cap):
    resolutions = [(1280, 720), (640, 480)]  # Use lower resolutions for Pi
    for width, height in resolutions:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Attempted to set resolution to {width}x{height}, actual resolution is {actual_width}x{actual_height}")
        for _ in range(5):
            ret, frame = cap.read()
            if ret and frame is not None and actual_width == width and actual_height == height:
                print(f"Successfully set webcam resolution to {actual_width}x{actual_height}")
                return actual_width, actual_height, frame
            time.sleep(0.1)
        print(f"Failed to set resolution to {width}x{height}, trying next resolution...")
    print("Failed to set any resolution from the list.")
    return None, None, None

class CentroidTracker:
    def __init__(self, max_disappeared=5):
        self.next_object_id = 0
        self.objects = OrderedDict()
        self.disappeared = OrderedDict()
        self.max_disappeared = max_disappeared

    def register(self, centroid):
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1

    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]

    def update(self, centroids):
        if not centroids:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects

        if not self.objects:
            for centroid in centroids:
                self.register(centroid)
        else:
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())
            D = np.zeros((len(object_centroids), len(centroids)))
            for i, (obj_x, obj_y) in enumerate(object_centroids):
                for j, (cen_x, cen_y) in enumerate(centroids):
                    D[i, j] = np.sqrt((obj_x - cen_x)**2 + (obj_y - cen_y)**2)

            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]
            used_rows, used_cols = set(), set()

            for row, col in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                object_id = object_ids[row]
                self.objects[object_id] = centroids[col]
                self.disappeared[object_id] = 0
                used_rows.add(row)
                used_cols.add(col)

            for row in range(len(object_centroids)):
                if row not in used_rows:
                    object_id = object_ids[row]
                    self.disappeared[object_id] += 1
                    if self.disappeared[object_id] > self.max_disappeared:
                        self.deregister(object_id)

            for col in range(len(centroids)):
                if col not in used_cols:
                    self.register(centroids[col])

        return self.objects

def detect_and_track_balls(frame, tracker):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    blurred = cv2.GaussianBlur(hsv, (3, 3), 0)  # Smaller kernel for Pi
    
    lower_white = np.array(BALL_COLOR_RANGE["lower_white"])
    upper_white = np.array(BALL_COLOR_RANGE["upper_white"])
    mask_white = cv2.inRange(blurred, lower_white, upper_white)
    mask_white = cv2.erode(mask_white, None, iterations=1)  # Reduced iterations
    mask_white = cv2.dilate(mask_white, None, iterations=1)
    contours_white, _ = cv2.findContours(mask_white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    lower_red = np.array(BALL_COLOR_RANGE["lower_red"])
    upper_red = np.array(BALL_COLOR_RANGE["upper_red"])
    mask_red = cv2.inRange(blurred, lower_red, upper_red)
    mask_red = cv2.erode(mask_red, None, iterations=1)
    mask_red = cv2.dilate(mask_red, None, iterations=1)
    contours_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    centroids = []
    balls = []
    
    for contour in contours_white:
        area = cv2.contourArea(contour)
        ((x, y), radius) = cv2.minEnclosingCircle(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        if area > MIN_CONTOUR_AREA and radius > MIN_RADIUS and circularity > 0.6:
            centroids.append((int(x), int(y)))
            balls.append((int(x), int(y), int(radius), "white"))

    red_balls_count = 0
    for contour in contours_red:
        if red_balls_count >= RED_BALL_LIMIT:
            break
        area = cv2.contourArea(contour)
        ((x, y), radius) = cv2.minEnclosingCircle(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        if area > RED_MIN_CONTOUR_AREA and radius > RED_MIN_RADIUS and circularity > RED_MIN_CIRCULARITY:
            centroids.append((int(x), int(y)))
            balls.append((int(x), int(y), int(radius), "red"))
            red_balls_count += 1

    tracked_objects = tracker.update(centroids)
    tracked_balls = []
    for obj_id, (x, y) in tracked_objects.items():
        for ball_x, ball_y, radius, color in balls:
            if abs(ball_x - x) < 10 and abs(ball_y - y) < 10:
                tracked_balls.append((ball_x, ball_y, radius, obj_id, color))
                break
    return tracked_balls

def calculate_score(balls, point_zones, special_hole, power_up_zone, last_red_score_time, red_score_cooldown, power_up):
    global scored_ball_ids, current_score
    round_score = 0
    scored_positions = []
    special_hole_triggered = False
    power_up_activated = False
    power_up_type = None
    current_time = time.time()

    for ball_x, ball_y, _, ball_id, color in balls:
        if ball_id not in scored_ball_ids:
            if power_up_zone and power_up_zone.is_active():
                zone_x, zone_y, zone_radius = power_up_zone.x, power_up_zone.y, power_up_zone.radius
                distance = np.sqrt((ball_x - zone_x)**2 + (ball_y - zone_y)**2)
                if distance <= zone_radius:
                    scored_ball_ids.add(ball_id)
                    scored_positions.append((ball_x, ball_y))
                    power_up_activated = True
                    power_up_type = random.choice(POWER_UP_TYPES)
                    power_up_zone.deactivate()
                    continue

            if special_hole:
                special_x, special_y, special_radius, special_points = special_hole
                distance = np.sqrt((ball_x - special_x)**2 + (ball_y - special_y)**2)
                if distance <= special_radius:
                    special_hole_triggered = True
                    scored_ball_ids.add(ball_id)
                    scored_positions.append((ball_x, ball_y))
                    continue

            for zone_x, zone_y, zone_radius, points in point_zones:
                distance = np.sqrt((ball_x - zone_x)**2 + (ball_y - zone_y)**2)
                if distance <= zone_radius:
                    base_points = points
                    if color == "red" and (current_time - last_red_score_time >= red_score_cooldown):
                        base_points *= 2
                        last_red_score_time = current_time
                    if power_up and power_up.is_active() and power_up.power_up_type == "Score Multiplier":
                        base_points *= POWER_UP_MULTIPLIER
                        power_up.deactivate()
                    round_score += base_points
                    scored_ball_ids.add(ball_id)
                    scored_positions.append((ball_x, ball_y))
                    break

    if special_hole_triggered:
        current_score *= 2

    return round_score, last_red_score_time, scored_positions, power_up_activated, power_up_type

class PowerUpZone:
    def __init__(self, x, y, radius, duration):
        self.x = x
        self.y = y
        self.radius = radius
        self.duration = duration
        self.start_time = time.time()
        self.active = True

    def is_active(self):
        if not self.active or (time.time() - self.start_time) > self.duration:
            self.active = False
        return self.active

    def deactivate(self):
        self.active = False

    def get_remaining_time(self):
        if not self.active:
            return 0
        elapsed = time.time() - self.start_time
        return max(0, self.duration - elapsed)

class PowerUp:
    def __init__(self, power_up_type, duration=None):
        self.power_up_type = power_up_type
        self.duration = duration if duration else (None if power_up_type in ["Score Multiplier", "Double Balls"] else POWER_UP_DURATION)
        self.start_time = None
        self.active = False

    def activate(self):
        self.start_time = time.time()
        self.active = True

    def deactivate(self):
        self.active = False

    def is_active(self):
        if not self.active:
            return False
        if self.duration is None:
            return True
        elapsed = time.time() - self.start_time
        if elapsed > self.duration:
            self.deactivate()
            return False
        return True

    def get_remaining_time(self):
        if self.duration is None:
            return None
        if not self.active:
            return 0
        elapsed = time.time() - self.start_time
        return max(0, self.duration - elapsed)

class SplashScreen:
    def __init__(self, root, callback):
        self.root = root
        self.callback = callback
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        try:
            splash_image = Image.open("splash.png").resize((800, 600), Image.Resampling.LANCZOS)
            self.splash_photo = ImageTk.PhotoImage(splash_image)
        except Exception as e:
            print(f"Error loading splash image: {e}")
            self.splash_photo = None

        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="black", highlightthickness=0)
        self.canvas.pack()
        if self.splash_photo:
            self.canvas.create_image(400, 300, image=self.splash_photo, anchor="center")
        self.canvas.bind("<Button-1>", self.close_splash)

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 800) // 2
        y = (screen_height - 600) // 2
        self.root.geometry(f"800x600+{x}+{y}")

    def close_splash(self, event=None):
        self.root.destroy()
        self.callback()

class CustomDialog:
    def __init__(self, parent, title, prompt, show_special_option=False):
        self.root = tk.Toplevel(parent)
        self.root.title(title)
        self.root.configure(bg="#2E2E2E")
        self.root.transient(parent)
        self.root.grab_set()
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
        self.result = None
        self.is_special = False

        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        x = parent_x + (parent.winfo_width() - 300) // 2
        y = parent_y + (parent.winfo_height() - 150) // 2
        self.root.geometry(f"300x150+{x}+{y}")

        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)
        frame.configure(style="Custom.TFrame")

        style = ttk.Style()
        style.configure("Custom.TFrame", background="#2E2E2E")
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#4CAF50", foreground="white")

        tk.Label(frame, text=prompt, font=("Helvetica", 10), bg="#2E2E2E", fg="white").pack(pady=5)
        self.entry = tk.Entry(frame, font=("Helvetica", 10), bg="#4A4A4A", fg="white", insertbackground="white")
        self.entry.pack(pady=5)
        self.entry.focus_set()

        if show_special_option:
            self.special_var = tk.BooleanVar(value=False)
            tk.Checkbutton(frame, text="Make this the special double-score hole", variable=self.special_var, 
                           font=("Helvetica", 10), bg="#2E2E2E", fg="white", selectcolor="#4A4A4A").pack(pady=5)

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=5)
        ttk.Button(button_frame, text="OK", style="Custom.TButton", command=self.ok).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", style="Custom.TButton", command=self.cancel).pack(side="left", padx=5)

        self.root.bind("<Return>", lambda e: self.ok())
        self.root.bind("<Escape>", lambda e: self.cancel())

    def ok(self):
        self.result = self.entry.get().strip() or "N/A"
        self.is_special = getattr(self, 'special_var', tk.BooleanVar(value=False)).get()
        self.root.grab_release()
        self.root.destroy()

    def cancel(self):
        self.result = "N/A"
        self.is_special = False
        self.root.grab_release()
        self.root.destroy()

    def show(self):
        self.root.wait_window()
        return self.result, self.is_special

class TutorialWindow:
    def __init__(self, on_close_callback):
        self.root = tk.Toplevel()
        self.root.title("Tutorial")
        self.root.geometry("600x400")
        self.root.configure(bg="#2E2E2E")
        self.root.resizable(False, False)
        self.on_close_callback = on_close_callback

        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)
        style = ttk.Style()
        style.configure("Custom.TLabel", foreground="white", background="#2E2E2E")

        self.steps = [
            "Welcome to Whiffle Playfield!\nClick 'Next' to learn how to play.",
            "Step 1: Calibration\nClick on the playfield to define scoring zones.\nSet points for each (e.g., 50, 100).\nOptionally mark one as a special double-score hole!",
            "Step 2: Playing the Game\nDrop balls onto the playfield. White balls score normally, red balls double points!",
            "Step 3: Scoring\nLand in a zone to earn points. Watch for a flash and particles!\nThe special hole doubles your total score!",
            "Step 4: Power-Ups\nGreen zones appear every 15s! Land a ball in them for bonuses like Score Multiplier, Slow Motion, Extra Time, or Double Balls.",
            "Step 5: Game Modes\nClassic Mode (untimed) or Timed Mode (2-minute challenge)!",
            "Step 6: Menus\nUse 'File' to save/load, 'New Game' for mode, 'High Score' for leaderboard, 'Options' for settings.",
            "You're ready!\nClick 'Finish' to start."
        ]

        self.current_step = 0
        self.tutorial_text = tk.StringVar(value=self.steps[0])
        ttk.Label(frame, textvariable=self.tutorial_text, font=("Helvetica", 12), style="Custom.TLabel", wraplength=550).pack(pady=20)

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        self.prev_button = ttk.Button(button_frame, text="Previous", command=self.prev_step)
        self.prev_button.pack(side="left", padx=5)
        self.next_button = ttk.Button(button_frame, text="Next", command=self.next_step)
        self.next_button.pack(side="left", padx=5)
        self.finish_button = ttk.Button(button_frame, text="Finish", command=self.close)
        self.finish_button.pack(side="left", padx=5)

        self.update_buttons()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def update_buttons(self):
        self.prev_button.config(state="disabled" if self.current_step == 0 else "normal")
        self.next_button.config(state="disabled" if self.current_step == len(self.steps) - 1 else "normal")
        self.finish_button.config(state="normal" if self.current_step == len(self.steps) - 1 else "disabled")

    def prev_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self.tutorial_text.set(self.steps[self.current_step])
            self.update_buttons()

    def next_step(self):
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self.tutorial_text.set(self.steps[self.current_step])
            self.update_buttons()

    def close(self):
        self.root.destroy()
        self.on_close_callback()

class OptionsWindow:
    def __init__(self, on_close_callback, game_instance):
        self.root = tk.Toplevel()
        self.root.title("Options")
        self.root.geometry("400x400")
        self.root.configure(bg="#2E2E2E")
        self.on_close_callback = on_close_callback
        self.game = game_instance

        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)
        style = ttk.Style()
        style.configure("Custom.TLabel", foreground="white", background="#2E2E2E")
        style.configure("Custom.TEntry", fieldbackground="#4A4A4A", foreground="white")

        ttk.Label(frame, text="Options", font=("Helvetica", 14, "bold"), style="Custom.TLabel").pack(pady=10)

        self.fields = [
            ("Lower Hue (0-180)", BALL_COLOR_RANGE["lower_white"][0], 0, 180),
            ("Lower Sat (0-255)", BALL_COLOR_RANGE["lower_white"][1], 0, 255),
            ("Lower Val (0-255)", BALL_COLOR_RANGE["lower_white"][2], 0, 255),
            ("Upper Hue (0-180)", BALL_COLOR_RANGE["upper_white"][0], 0, 180),
            ("Upper Sat (0-255)", BALL_COLOR_RANGE["upper_white"][1], 0, 255),
            ("Upper Val (0-255)", BALL_COLOR_RANGE["upper_white"][2], 0, 255),
        ]
        self.entries = []
        for label, value, _, _ in self.fields:
            ttk.Label(frame, text=label, font=("Helvetica", 10), style="Custom.TLabel").pack(pady=2)
            entry = ttk.Entry(frame, font=("Helvetica", 10), style="Custom.TEntry")
            entry.insert(0, str(value))
            entry.pack(pady=2)
            self.entries.append(entry)

        self.music_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Mute Music", variable=self.music_var, command=self.toggle_music).pack(pady=5)
        self.sound_effects_var = tk.BooleanVar(value=not self.game.sound_effects_enabled)
        ttk.Checkbutton(frame, text="Disable Sound Effects", variable=self.sound_effects_var, command=self.toggle_sound_effects).pack(pady=5)

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=self.save).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Close", command=self.close).pack(side="left", padx=5)

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def save(self):
        global BALL_COLOR_RANGE
        try:
            BALL_COLOR_RANGE["lower_white"] = [int(self.entries[0].get()), int(self.entries[1].get()), int(self.entries[2].get())]
            BALL_COLOR_RANGE["upper_white"] = [int(self.entries[3].get()), int(self.entries[4].get()), int(self.entries[5].get())]
            save_config(not self.sound_effects_var.get(), self.game.tutorial_shown)
            print("Options saved")
        except ValueError:
            tk.messagebox.showerror("Error", "Invalid input in options")
        self.close()

    def toggle_music(self):
        pygame.mixer.music.pause() if self.music_var.get() else pygame.mixer.music.unpause()
        print("Music " + ("muted" if self.music_var.get() else "unmuted"))

    def toggle_sound_effects(self):
        self.game.sound_effects_enabled = not self.sound_effects_var.get()
        print(f"Sound effects {'disabled' if not self.game.sound_effects_enabled else 'enabled'}")

    def close(self):
        self.root.destroy()
        self.on_close_callback()

class HelpWindow:
    def __init__(self, on_close_callback, game_instance):
        self.root = tk.Toplevel()
        self.root.title("Help")
        self.root.geometry("400x300")
        self.root.configure(bg="#2E2E2E")
        self.on_close_callback = on_close_callback
        self.game = game_instance

        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)
        style = ttk.Style()
        style.configure("Custom.TLabel", foreground="white", background="#2E2E2E")

        ttk.Label(frame, text="Help", font=("Helvetica", 14, "bold"), style="Custom.TLabel").pack(pady=10)
        help_lines = [
            "Hotkeys: 'q' to quit, 'c' to calibrate",
            "Menu: File (save/load), New Game (mode), High Score (leaderboard)",
            "Options (settings)",
            "Power-Ups: Land in green zones for bonuses!",
            "Credits: Ideas by Blake Weibling, coding by Grok3"
        ]
        for line in help_lines:
            ttk.Label(frame, text=line, font=("Helvetica", 10), style="Custom.TLabel").pack(pady=5)

        ttk.Button(frame, text="Show Tutorial", command=self.show_tutorial).pack(pady=5)
        ttk.Button(frame, text="Close", command=self.close).pack(pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def show_tutorial(self):
        self.root.destroy()
        TutorialWindow(self.on_close_callback)

    def close(self):
        self.root.destroy()
        self.on_close_callback()

class WhiffleGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Whiffle Playfield")
        self.root.geometry("800x480")  # Reduced window size for Pi
        self.root.configure(bg="#2E2E2E")
        self.root.resizable(True, True)
        self.new_high_score_prompted = False
        self.is_timed_mode = False
        self.time_remaining = 0
        self.timer_id = None
        self.power_up_zone = None
        self.power_up = None
        self.power_up_label = None
        self.last_power_up_spawn = 0
        self.frame_delay = 10
        self.last_frame_time = time.time()
        self.tracked_balls_queue = queue.Queue()  # Queue for threaded ball detection
        self.running = True

        try:
            self.ball_detected_sound = pygame.mixer.Sound("ball_detected.wav")
            self.score_sound = pygame.mixer.Sound("score.wav")
            self.game_start_sound = pygame.mixer.Sound("game_start.wav")
        except pygame.error as e:
            print(f"Error loading sound effects: {e}")
            self.ball_detected_sound = self.score_sound = self.game_start_sound = None

        try:
            pygame.mixer.music.load("background_music.mp3")
            pygame.mixer.music.set_volume(0.3)  # Lower volume to reduce Pi load
            pygame.mixer.music.play(-1)
        except pygame.error as e:
            print(f"Error loading background music: {e}")

        config = load_config()
        self.sound_effects_enabled = config["sound_effects_enabled"]
        self.tutorial_shown = config["tutorial_shown"]

        style = ttk.Style()
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#2196F3", foreground="black")

        menu_frame = ttk.Frame(self.root)
        menu_frame.pack(fill="x", pady=5, padx=10)
        buttons = [
            ("File", self.file_menu),
            ("New Game", self.new_game_menu),
            ("High Score", self.high_score),
            ("Options", self.options_menu),
            ("Help", lambda: HelpWindow(self.resume_frame, self))
        ]
        for text, command in buttons:
            ttk.Button(menu_frame, text=text, style="Custom.TButton", command=command).pack(side="left", padx=5)

        self.canvas = tk.Canvas(self.root, bg="#2E2E2E", highlightthickness=2, highlightbackground="#2196F3")
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)  # Reduced padding
        self.canvas.bind("<Button-1>", self.canvas_click)

        self.save_button = ttk.Button(self.root, text="Save Zones", style="Custom.TButton", command=self.queue_save_zones, state="disabled")
        self.save_button.pack(pady=5)

        self.stats_frame = ttk.Frame(self.root)
        self.stats_frame.pack(fill="x", padx=5, pady=5)
        self.balls_label = tk.Label(self.stats_frame, text="Balls: 0", font=("Helvetica", 10), bg="#2E2E2E", fg="white")  # Smaller font
        self.balls_label.pack(side="left", padx=5)
        self.score_label = tk.Label(self.stats_frame, text="Score: 0", font=("Helvetica", 10), bg="#2E2E2E", fg="white")
        self.score_label.pack(side="left", padx=5)
        self.timer_label = tk.Label(self.stats_frame, text="Time: N/A", font=("Helvetica", 10), bg="#2E2E2E", fg="white")
        self.timer_label.pack(side="left", padx=5)
        self.power_up_label = tk.Label(self.stats_frame, text="Power-Up: None", font=("Helvetica", 10), bg="#2E2E2E", fg="white")
        self.power_up_label.pack(side="left", padx=5)
        self.res_label = tk.Label(self.stats_frame, text="Res: 0x0", font=("Helvetica", 10), bg="#2E2E2E", fg="white")
        self.res_label.pack(side="right", padx=5)

        webcam_index = select_webcam()
        if webcam_index is None:
            self.root.destroy()
            return

        try:
            self.cap = cv2.VideoCapture(webcam_index, WEBCAM_BACKEND)
            if not self.cap.isOpened():
                print(f"Failed to open webcam with backend {WEBCAM_BACKEND}, trying alternate backend {ALTERNATE_WEBCAM_BACKEND}")
                self.cap = cv2.VideoCapture(webcam_index, ALTERNATE_WEBCAM_BACKEND)
            if not self.cap.isOpened():
                raise Exception("Could not open webcam with any backend.")
            self.width, self.height, initial_frame = set_webcam_resolution(self.cap)
            if self.width is None:
                raise Exception("Could not set resolution.")
        except Exception as e:
            tk.messagebox.showerror("Error", f"Webcam initialization failed: {e}")
            self.root.destroy()
            return

        global current_score, scored_ball_ids
        current_score = 0
        scored_ball_ids.clear()
        self.point_zones, self.special_hole = load_point_zones()
        self.calibrating = not self.point_zones and not self.special_hole
        self.zone_count = len(self.point_zones)
        self.special_hole_defined = bool(self.special_hole)
        self.paused = False
        self.save_triggered = False
        self.zone_circles = []
        self.zone_texts = []
        self.frame = initial_frame
        self.red_zone_circles = []
        self.red_zone_texts = []
        self.green_ball_circles = []
        self.special_hole_circle = None
        self.special_hole_text = None
        self.power_up_zone_circle = None
        self.power_up_zone_text = None
        self.tracker = CentroidTracker(max_disappeared=5)
        self.previous_balls = []
        self.tracked_balls = []
        self.last_red_score_time = 0.0
        self.particles = []
        self.rendered_width = 0
        self.rendered_height = 0
        self.rendered_offset_x = 0
        self.rendered_offset_y = 0

        if self.calibrating:
            self.save_button.config(state="normal")

        if self.game_start_sound and self.sound_effects_enabled:
            self.game_start_sound.play()

        if not self.tutorial_shown:
            self.tutorial_shown = True
            save_config(self.sound_effects_enabled, self.tutorial_shown)
            TutorialWindow(self.resume_frame)

        # Start the ball detection thread
        threading.Thread(target=self.ball_detection_thread, daemon=True).start()
        self.root.after(100, self.update_frame)

    def ball_detection_thread(self):
        while self.running:
            if not self.paused and not self.calibrating:
                ret, frame = self.cap.read()
                if ret:
                    tracked_balls = detect_and_track_balls(frame, self.tracker)
                    self.tracked_balls_queue.put(tracked_balls)
                time.sleep(0.067)  # Limit to 15 FPS for detection thread
            else:
                time.sleep(0.1)

    def create_particle(self, x, y):
        return {
            "x": x, "y": y, "size": random.uniform(2, PARTICLE_MAX_SIZE),
            "dx": random.uniform(-PARTICLE_MAX_SPEED, PARTICLE_MAX_SPEED),
            "dy": random.uniform(-PARTICLE_MAX_SPEED, PARTICLE_MAX_SPEED),
            "lifetime": PARTICLE_LIFETIME, "start_time": time.time() * 1000,
            "color": random.choice(["yellow", "orange", "red"])
        }

    def spawn_particle_explosion(self, x, y):
        for _ in range(PARTICLE_COUNT):
            self.particles.append(self.create_particle(x, y))

    def update_particles(self):
        current_time = time.time() * 1000
        self.particles = [p for p in self.particles if (current_time - p["start_time"]) <= p["lifetime"]]
        for p in self.particles:
            elapsed = current_time - p["start_time"]
            p["x"] += p["dx"]
            p["y"] += p["dy"]
            alpha = 1.0 - (elapsed / p["lifetime"])
            size = p["size"] * alpha
            self.canvas.create_oval(p["x"] - size, p["y"] - size, p["x"] + size, p["y"] + size, fill=p["color"], outline="")

    def spawn_power_up_zone(self):
        if not self.point_zones or (time.time() - self.last_power_up_spawn < POWER_UP_SPAWN_INTERVAL) or (self.power_up_zone and self.power_up_zone.is_active()):
            return
        zone = random.choice(self.point_zones)
        self.power_up_zone = PowerUpZone(zone[0], zone[1], ZONE_RADIUS, POWER_UP_DURATION)
        self.last_power_up_spawn = time.time()

    def file_menu(self):
        self.paused = True
        file_window = tk.Toplevel(self.root)
        file_window.title("File")
        file_window.geometry("300x200")
        file_window.configure(bg="#2E2E2E")

        frame = ttk.Frame(file_window, padding=10)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="File Options", font=("Helvetica", 14, "bold"), bg="#2E2E2E", fg="white").pack(pady=10)
        tk.Button(frame, text="Save", command=lambda: self.save_file(file_window)).pack(pady=5)
        tk.Button(frame, text="Load", command=lambda: self.load_file(file_window)).pack(pady=5)

    def save_file(self, window):
        dialog = CustomDialog(window, "Save", "Enter filename:")
        filename, _ = dialog.show()
        if filename != "N/A":
            save_point_zones(self.point_zones, self.special_hole, filename)
        window.destroy()
        self.resume_frame()

    def load_file(self, window):
        dialog = CustomDialog(window, "Load", "Enter filename:")
        filename, _ = dialog.show()
        if filename != "N/A":
            self.point_zones, self.special_hole = load_point_zones(filename)
            self.zone_count = len(self.point_zones)
            self.special_hole_defined = bool(self.special_hole)
        window.destroy()
        self.resume_frame()

    def new_game_menu(self):
        self.paused = True
        new_game_window = tk.Toplevel(self.root)
        new_game_window.title("Select Game Mode")
        new_game_window.geometry("300x200")
        new_game_window.configure(bg="#2E2E2E")

        frame = ttk.Frame(new_game_window, padding=10)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Select Game Mode", font=("Helvetica", 14, "bold"), bg="#2E2E2E", fg="white").pack(pady=10)
        tk.Button(frame, text="Classic Mode", command=lambda: self.new_game(True, new_game_window)).pack(pady=5)
        tk.Button(frame, text="Timed Mode (2m)", command=lambda: self.new_game(False, new_game_window)).pack(pady=5)

    def new_game(self, classic=True, window=None):
        if window:
            window.destroy()
        global current_score, scored_ball_ids, RED_BALL_LIMIT
        current_score = 0
        scored_ball_ids.clear()
        RED_BALL_LIMIT = 1
        self.tracker = CentroidTracker(max_disappeared=5)
        self.previous_balls = []
        self.new_high_score_prompted = False
        self.power_up_zone = None
        self.power_up = None
        self.last_power_up_spawn = 0
        self.frame_delay = 10
        self.power_up_label.config(text="Power-Up: None")
        self.is_timed_mode = not classic
        if self.is_timed_mode:
            self.time_remaining = TIMED_MODE_DURATION
            self.timer_label.config(text=f"Time: {self.time_remaining // 60}m{self.time_remaining % 60:02d}s")
            self.start_timer()
        else:
            self.time_remaining = 0
            self.timer_label.config(text="Time: N/A")
            if self.timer_id:
                self.root.after_cancel(self.timer_id)
                self.timer_id = None
        if self.game_start_sound and self.sound_effects_enabled:
            self.game_start_sound.play()
        self.resume_frame()

    def start_timer(self):
        if self.time_remaining > 0:
            self.time_remaining -= 1
            self.timer_label.config(text=f"Time: {self.time_remaining // 60}m{self.time_remaining % 60:02d}s")
            self.timer_id = self.root.after(1000, self.start_timer)
        else:
            self.timer_label.config(text="Time: 0m00s")
            self.paused = True
            self.check_high_score()

    def check_high_score(self):
        global current_score
        if current_score > high_score and not self.new_high_score_prompted:
            self.new_high_score_prompted = True
            while True:
                dialog = CustomDialog(self.root, "New High Score!", "Enter your initials (3 letters):")
                initials, _ = dialog.show()
                if initials != "N/A" and len(initials.strip()) > 0:
                    initials = initials.upper()[:3]
                    save_high_score(initials, current_score)
                    break
                elif initials == "N/A":
                    save_high_score("N/A", current_score)
                    break
            self.paused = False

    def high_score(self):
        self.paused = True
        high_score_window = tk.Toplevel(self.root)
        high_score_window.title("High Score Leaderboard")
        high_score_window.geometry("300x400")
        high_score_window.configure(bg="#2E2E2E")

        frame = ttk.Frame(high_score_window, padding=10)
        frame.pack(fill="both", expand=True)
        style = ttk.Style()
        style.configure("Custom.TLabel", foreground="white", background="#2E2E2E")

        ttk.Label(frame, text="High Score Leaderboard", font=("Helvetica", 14, "bold"), style="Custom.TLabel").pack(pady=10)
        leaderboard = load_high_score()
        if not leaderboard:
            ttk.Label(frame, text="No scores yet!", font=("Helvetica", 12), style="Custom.TLabel").pack(pady=5)
        else:
            for i, entry in enumerate(leaderboard, 1):
                ttk.Label(frame, text=f"{i}. {entry['initials']}: {entry['score']}", font=("Helvetica", 12), style="Custom.TLabel").pack(pady=5)
        ttk.Button(frame, text="Close", command=lambda: high_score_window.destroy() or self.resume_frame()).pack(pady=10)

    def options_menu(self):
        self.paused = True
        OptionsWindow(self.resume_frame, self)

    def resume_frame(self):
        self.paused = False
        self.update_frame()

    def queue_save_zones(self):
        if self.calibrating:
            self.save_triggered = True

    def canvas_click(self, event):
        if not self.calibrating:
            return

        x, y = event.x, event.y
        canvas_width, canvas_height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.frame is not None and canvas_width > 0 and canvas_height > 0:
            frame_width, frame_height = self.frame.shape[1], self.frame.shape[0]
            aspect_ratio = frame_width / frame_height
            new_height = int(canvas_width / aspect_ratio)
            if new_height > canvas_height:
                new_height = canvas_height
                new_width = int(canvas_height * aspect_ratio)
            else:
                new_width = canvas_width
            offset_x = (canvas_width - new_width) // 2
            offset_y = (canvas_height - new_height) // 2
            scale_x = frame_width / new_width
            scale_y = frame_height / new_height
            x_frame = int((x - offset_x) * scale_x)
            y_frame = int((y - offset_y) * scale_y)
        else:
            x_frame, y_frame = x, y

        radius = CALIBRATION_VISUAL_RADIUS
        dialog = CustomDialog(self.root, "Points", f"Points for zone at ({x_frame}, {y_frame}):", 
                              show_special_option=not self.special_hole_defined)
        self.paused = True
        points, is_special = dialog.show()
        self.paused = False

        if points != "N/A":
            try:
                points = int(points)
                if is_special and not self.special_hole_defined:
                    self.special_hole = (x_frame, y_frame, ZONE_RADIUS, points)
                    self.special_hole_defined = True
                    circle_id = self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="purple", width=2)
                    self.zone_circles.append(circle_id)
                    text_id = self.canvas.create_text(x, y + radius + 15, text="Double!", fill="purple", font=("Helvetica", 10))
                    self.zone_texts.append(text_id)
                else:
                    self.point_zones.append((x_frame, y_frame, ZONE_RADIUS, points))
                    self.zone_count += 1
                    circle_id = self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="blue", width=2)
                    self.zone_circles.append(circle_id)
                    text_id = self.canvas.create_text(x, y + radius + 15, text=str(points), fill="white", font=("Helvetica", 10))
                    self.zone_texts.append(text_id)
            except ValueError:
                tk.messagebox.showwarning("Warning", "Invalid points value. Zone not added.")
        if self.zone_count + (1 if self.special_hole else 0) >= TOTAL_ZONES:
            tk.messagebox.showinfo("Calibration", f"Reached {TOTAL_ZONES} zones. Click 'Save Zones' to finish or continue adding.")

    def update_frame(self):
        if self.paused:
            self.root.after(self.frame_delay, self.update_frame)
            return

        current_time = time.time()
        target_frame_time = 0.067  # 15 FPS (1/15 ≈ 0.067 seconds)
        if current_time - self.last_frame_time < target_frame_time:
            self.root.after(int((target_frame_time - (current_time - self.last_frame_time)) * 1000), self.update_frame)
            return
        self.last_frame_time = current_time

        print("Updating frame...")
        self.read_frame()
        self.render_frame()
        self.update_game_logic(self.rendered_width, self.rendered_height, self.rendered_offset_x, self.rendered_offset_y)

        elapsed = (time.time() - current_time) * 1000  # Time taken in milliseconds
        self.frame_delay = max(67, int(elapsed * 1.5))  # Dynamic adjustment, minimum 15 FPS
        print(f"Frame processed in {elapsed}ms, next delay: {self.frame_delay}ms")
        self.root.after(self.frame_delay, self.update_frame)

    def read_frame(self):
        try:
            ret, self.frame = self.cap.read()
            if not ret:
                tk.messagebox.showerror("Error", "Failed to read frame from webcam.")
                self.destroy()
            else:
                print("Frame captured successfully")
        except Exception as e:
            tk.messagebox.showerror("Error", f"Frame capture failed: {e}")
            self.destroy()

    def render_frame(self):
        self.canvas.delete("all")
        if self.frame is not None:
            frame_rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            canvas_width, canvas_height = self.canvas.winfo_width(), self.canvas.winfo_height()
            if canvas_width > 0 and canvas_height > 0:
                aspect_ratio = self.frame.shape[1] / self.frame.shape[0]
                new_height = int(canvas_width / aspect_ratio)
                if new_height > canvas_height:
                    new_height = canvas_height
                    new_width = int(canvas_height * aspect_ratio)
                else:
                    new_width = canvas_width
                # Downscale for Pi display to reduce load
                img = img.resize((int(new_width / 2), int(new_height / 2)), Image.Resampling.LANCZOS)
            else:
                new_width, new_height = self.frame.shape[1] // 2, self.frame.shape[0] // 2  # Default half resolution

            offset_x = (canvas_width - new_width) // 2
            offset_y = (canvas_height - new_height) // 2
            self.photo = ImageTk.PhotoImage(image=img)
            self.canvas.create_image(offset_x, offset_y, image=self.photo, anchor="nw")
            self.update_particles()

            # Store dimensions for use in update_game_logic
            self.rendered_width = new_width
            self.rendered_height = new_height
            self.rendered_offset_x = offset_x
            self.rendered_offset_y = offset_y

            for x_frame, y_frame, r, points in self.point_zones:
                x_canvas = int(x_frame * (new_width / (self.frame.shape[1] // 2)) + offset_x)
                y_canvas = int(y_frame * (new_height / (self.frame.shape[0] // 2)) + offset_y)
                r_canvas = int(r * (new_width / (self.frame.shape[1] // 2)))
                self.red_zone_circles.append(self.canvas.create_oval(x_canvas - r_canvas, y_canvas - r_canvas, 
                                                                     x_canvas + r_canvas, y_canvas + r_canvas, outline="red", width=1))
                self.red_zone_texts.append(self.canvas.create_text(x_canvas, y_canvas, text=str(points), fill="white", font=("Helvetica", 8)))

            if self.special_hole:
                x_frame, y_frame, r, points = self.special_hole
                x_canvas = int(x_frame * (new_width / (self.frame.shape[1] // 2)) + offset_x)
                y_canvas = int(y_frame * (new_height / (self.frame.shape[0] // 2)) + offset_y)
                r_canvas = int(r * (new_width / (self.frame.shape[1] // 2)))
                self.special_hole_circle = self.canvas.create_oval(x_canvas - r_canvas, y_canvas - r_canvas, 
                                                                   x_canvas + r_canvas, y_canvas + r_canvas, outline="purple", width=1)
                self.special_hole_text = self.canvas.create_text(x_canvas, y_canvas, text="Double!", fill="purple", font=("Helvetica", 8))

            if self.power_up_zone and self.power_up_zone.is_active():
                x_frame, y_frame, r = self.power_up_zone.x, self.power_up_zone.y, self.power_up_zone.radius
                x_canvas = int(x_frame * (new_width / (self.frame.shape[1] // 2)) + offset_x)
                y_canvas = int(y_frame * (new_height / (self.frame.shape[0] // 2)) + offset_y)
                r_canvas = int(r * (new_width / (self.frame.shape[1] // 2)))
                self.power_up_zone_circle = self.canvas.create_oval(x_canvas - r_canvas, y_canvas - r_canvas, 
                                                                    x_canvas + r_canvas, y_canvas + r_canvas, outline="green", width=1)
                self.power_up_zone_text = self.canvas.create_text(x_canvas, y_canvas, text="Power-Up", fill="green", font=("Helvetica", 8))

            if self.power_up and self.power_up.is_active():
                if self.power_up.power_up_type == "Slow Motion":
                    self.canvas.configure(highlightbackground="blue")
                elif self.power_up.power_up_type == "Score Multiplier":
                    self.canvas.configure(highlightbackground="gold")
                elif self.power_up.power_up_type == "Extra Time":
                    self.canvas.configure(highlightbackground="green")
                elif self.power_up.power_up_type == "Double Balls":
                    self.canvas.configure(highlightbackground="pink")
            else:
                self.canvas.configure(highlightbackground="#2196F3")
            print(f"Rendered frame with dimensions {new_width}x{new_height}")
        else:
            print("Frame is None, cannot render")

    def update_game_logic(self, new_width, new_height, offset_x, offset_y):
        global current_score, RED_BALL_LIMIT
        try:
            if self.calibrating:
                cv2.putText(self.frame, f"Click to define zones ({self.zone_count + (1 if self.special_hole else 0)}/{TOTAL_ZONES})", 
                            (10, self.frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)  # Smaller text and thickness
                self.save_button.config(state="normal")
            else:
                self.save_button.config(state="disabled")
                self.spawn_power_up_zone()
                if self.power_up and self.power_up.is_active():
                    remaining = self.power_up.get_remaining_time()
                    if remaining is not None:
                        self.power_up_label.config(text=f"Power-Up: {self.power_up.power_up_type} ({int(remaining)}s)")
                    else:
                        self.power_up_label.config(text=f"Power-Up: {self.power_up.power_up_type}")
                    if self.power_up.power_up_type == "Slow Motion":
                        self.frame_delay = 50
                else:
                    self.power_up_label.config(text="Power-Up: None")
                    self.frame_delay = 10
                    if self.power_up and self.power_up.power_up_type == "Double Balls":
                        RED_BALL_LIMIT = 1

                if self.save_triggered:
                    save_point_zones(self.point_zones, self.special_hole)
                    self.calibrating = False
                    self.save_triggered = False

                # Get tracked balls from queue
                while not self.tracked_balls_queue.empty():
                    self.tracked_balls = self.tracked_balls_queue.get()

                total_balls = len(self.tracked_balls)
                new_balls = [ball for ball in self.tracked_balls if ball[3] not in [pb[3] for pb in self.previous_balls]]
                if new_balls and self.ball_detected_sound and self.sound_effects_enabled:
                    self.ball_detected_sound.play()

                round_score, self.last_red_score_time, scored_positions, power_up_activated, power_up_type = calculate_score(
                    self.tracked_balls, self.point_zones, self.special_hole, self.power_up_zone, self.last_red_score_time, RED_BALL_COOLDOWN, self.power_up
                )
                if power_up_activated and not (self.power_up and self.power_up.is_active()):
                    if power_up_type in ["Score Multiplier", "Double Balls"]:
                        self.power_up = PowerUp(power_up_type)
                    elif power_up_type == "Slow Motion":
                        self.power_up = PowerUp(power_up_type, POWER_UP_DURATION)
                    elif power_up_type == "Extra Time" and self.is_timed_mode:
                        self.power_up = PowerUp(power_up_type)
                        self.time_remaining += POWER_UP_EXTRA_TIME
                    self.power_up.activate()
                    if power_up_type == "Double Balls":
                        RED_BALL_LIMIT = 2

                if round_score > 0:
                    if self.score_sound and self.sound_effects_enabled:
                        self.score_sound.play()
                    self.canvas.configure(bg="yellow")
                    self.root.after(100, lambda: self.canvas.configure(bg="#2E2E2E"))
                    for pos_x, pos_y in scored_positions:
                        canvas_x = int(pos_x * (new_width / (self.frame.shape[1] // 2)) + offset_x)
                        canvas_y = int(pos_y * (new_height / (self.frame.shape[0] // 2)) + offset_y)
                        self.spawn_particle_explosion(canvas_x, canvas_y)
                current_score += round_score

                if not self.is_timed_mode:
                    self.check_high_score()

                for (x, y, r, ball_id, color) in self.tracked_balls:
                    x_canvas = int(x * (new_width / (self.frame.shape[1] // 2)) + offset_x)
                    y_canvas = int(y * (new_height / (self.frame.shape[0] // 2)) + offset_y)
                    r_canvas = int(r * (new_width / (self.frame.shape[1] // 2)))
                    outline_color = "red" if color == "red" else "green"
                    self.green_ball_circles.append(self.canvas.create_oval(x_canvas - r_canvas, y_canvas - r_canvas,
                                                                           x_canvas + r_canvas, y_canvas + r_canvas,
                                                                           outline=outline_color, width=1))
                    self.green_ball_circles.append(self.canvas.create_text(x_canvas, y_canvas - r_canvas - 5, 
                                                                           text=f"ID: {ball_id}", fill="yellow", font=("Helvetica", 6)))

                self.balls_label.config(text=f"Balls: {total_balls}")
                self.score_label.config(text=f"Score: {current_score}")
                self.res_label.config(text=f"Res: {self.width}x{self.height}")
                self.previous_balls = self.tracked_balls
                print(f"Updated game logic: {total_balls} balls detected, score: {current_score}")
        except Exception as e:
            print(f"Error in update_game_logic: {e}")

    def handle_input(self):
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            self.running = False
            save_high_score(high_score_initials, current_score)
            self.destroy()
        elif key == ord('c'):
            self.point_zones = []
            self.special_hole = None
            self.special_hole_defined = False
            self.calibrating = True
            self.zone_count = 0
            global scored_ball_ids
            scored_ball_ids.clear()
            self.tracker = CentroidTracker(max_disappeared=5)
            self.power_up_zone = None
            self.power_up = None
            self.last_power_up_spawn = 0
            self.frame_delay = 10
            self.power_up_label.config(text="Power-Up: None")
            for item in self.zone_circles + self.red_zone_circles + self.green_ball_circles + self.zone_texts + self.red_zone_texts:
                self.canvas.delete(item)
            self.zone_circles = []
            self.zone_texts = []
            self.red_zone_circles = []
            self.red_zone_texts = []
            self.green_ball_circles = []
            if self.special_hole_circle:
                self.canvas.delete(self.special_hole_circle)
                self.special_hole_circle = None
            if self.special_hole_text:
                self.canvas.delete(self.special_hole_text)
                self.special_hole_text = None
            if self.power_up_zone_circle:
                self.canvas.delete(self.power_up_zone_circle)
                self.power_up_zone_circle = None
            if self.power_up_zone_text:
                self.canvas.delete(self.power_up_zone_text)
                self.power_up_zone_text = None

    def destroy(self):
        self.running = False
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.root.destroy()

def start_game():
    root = tk.Tk()
    app = WhiffleGame(root)
    root.mainloop()

if __name__ == "__main__":
    splash_root = tk.Tk()
    SplashScreen(splash_root, start_game)
    splash_root.mainloop()