import cv2
import numpy as np
import json
import os
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from collections import OrderedDict
import platform
import pygame

# Initialize Pygame mixer for sound effects and music
pygame.mixer.init()

# Fixed radius for scoring zones
ZONE_RADIUS = 20
CALIBRATION_VISUAL_RADIUS = 20
TOTAL_ZONES = 21

# Files
CALIBRATION_FILE = "whiffle_zones.json"
HIGH_SCORE_FILE = "whiffle_high_score.json"
CONFIG_FILE = "whiffle_config.json"  # New file for sound settings

# Detection settings (relaxed for white balls, strict for red balls)
BALL_COLOR_RANGE = {
    "lower_white": [0, 0, 180],  # Slightly wider range for white balls
    "upper_white": [180, 70, 255],
    "lower_red": [0, 120, 120],  # Calibrated from test_red_detection.py
    "upper_red": [5, 255, 255]   # Calibrated from test_red_detection.py
}
MIN_CONTOUR_AREA = 30  # For white balls
MIN_RADIUS = 6         # For white balls
RED_MIN_CONTOUR_AREA = 50  # Stricter for red balls
RED_MIN_RADIUS = 10        # Stricter for red balls
RED_MIN_CIRCULARITY = 0.85 # Stricter circularity for red balls
RED_BALL_LIMIT = 1         # Maximum number of red balls tracked at once
RED_BALL_COOLDOWN = 2.0    # Cooldown in seconds for red ball scoring

# Game state
current_score = 0
high_score = 0
high_score_initials = "N/A"  # Added to store initials
scored_ball_ids = set()      # Track ball IDs that have already scored

# Determine the platform and set the appropriate webcam backend
system = platform.system()
if system == "Windows":
    WEBCAM_BACKEND = cv2.CAP_DSHOW  # DirectShow for Windows
elif system == "Darwin":  # macOS
    WEBCAM_BACKEND = cv2.CAP_AVFOUNDATION  # AVFoundation for macOS
else:
    WEBCAM_BACKEND = cv2.CAP_ANY  # Fallback for Linux or other systems

# Function to list available webcams
def list_webcams():
    index = 0
    available_cameras = []
    while index < 10:  # Check up to 10 indices
        cap = cv2.VideoCapture(index, WEBCAM_BACKEND)
        if not cap.isOpened():
            break
        ret, frame = cap.read()
        if ret:
            available_cameras.append(index)
        cap.release()
        index += 1
    return available_cameras

# Function to select a webcam
def select_webcam():
    cameras = list_webcams()
    if not cameras:
        print("No webcams found.")
        return None
    if len(cameras) == 1:
        print(f"Only one webcam found at index {cameras[0]}. Using it.")
        return cameras[0]

    print("Available webcams:")
    for idx in cameras:
        print(f"Index {idx}")
    while True:
        try:
            choice = int(input("Select a webcam index (e.g., 0, 1, etc.): "))
            if choice in cameras:
                return choice
            print("Invalid index. Please choose from the available indices.")
        except ValueError:
            print("Please enter a valid number.")

def load_point_zones(filename=CALIBRATION_FILE):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            return [(zone['x'], zone['y'], ZONE_RADIUS, zone['points']) for zone in data]
    return []

def save_point_zones(point_zones, filename=CALIBRATION_FILE):
    data = [{'x': x, 'y': y, 'points': points} for (x, y, _, points) in point_zones]
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Zones saved to {filename}")

def load_high_score():
    global high_score, high_score_initials
    if os.path.exists(HIGH_SCORE_FILE):
        with open(HIGH_SCORE_FILE, 'r') as f:
            data = json.load(f)
            high_score = data.get("high_score", 0)
            high_score_initials = data.get("initials", "N/A")
    print(f"Loaded high score: {high_score} by {high_score_initials}")
    return high_score

def save_high_score(initials="N/A"):
    global high_score, high_score_initials
    high_score_initials = initials
    with open(HIGH_SCORE_FILE, 'w') as f:
        json.dump({"high_score": high_score, "initials": high_score_initials}, f)
    print(f"Saved high score: {high_score} by {high_score_initials}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return data.get("sound_effects_enabled", True)
    return True  # Default to sound effects enabled if no config file exists

def save_config(sound_effects_enabled):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"sound_effects_enabled": sound_effects_enabled}, f)
    print(f"Saved config: sound_effects_enabled = {sound_effects_enabled}")

def set_webcam_resolution(cap):
    resolutions = [(1920, 1080), (1280, 720), (640, 480)]
    for width, height in resolutions:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        for _ in range(5):
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"Set resolution to {actual_width}x{actual_height}")
                return actual_width, actual_height, frame
            time.sleep(0.1)
    print("Failed to set resolution.")
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
    blurred = cv2.GaussianBlur(hsv, (5, 5), 0)
    
    # Detect white balls
    lower_white = np.array(BALL_COLOR_RANGE["lower_white"])
    upper_white = np.array(BALL_COLOR_RANGE["upper_white"])
    mask_white = cv2.inRange(blurred, lower_white, upper_white)
    mask_white = cv2.erode(mask_white, None, iterations=2)
    mask_white = cv2.dilate(mask_white, None, iterations=2)
    contours_white, _ = cv2.findContours(mask_white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Detect red balls
    lower_red = np.array(BALL_COLOR_RANGE["lower_red"])
    upper_red = np.array(BALL_COLOR_RANGE["upper_red"])
    mask_red = cv2.inRange(blurred, lower_red, upper_red)
    mask_red = cv2.erode(mask_red, None, iterations=2)
    mask_red = cv2.dilate(mask_red, None, iterations=2)
    mask_red = cv2.dilate(mask_red, None, iterations=2)  # Additional dilation to fill holes
    contours_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    centroids = []
    balls = []
    print(f"Found {len(contours_white)} white contours, {len(contours_red)} red contours")
    
    # Process white balls
    for contour in contours_white:
        area = cv2.contourArea(contour)
        ((x, y), radius) = cv2.minEnclosingCircle(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        if area > MIN_CONTOUR_AREA and radius > MIN_RADIUS and circularity > 0.6:
            centroids.append((int(x), int(y)))
            balls.append((int(x), int(y), int(radius), "white"))
            print(f"White ball at ({x}, {y}) with radius {radius}, area {area}, circularity {circularity}")

    # Process red balls with stricter criteria
    red_balls_count = 0
    for contour in contours_red:
        if red_balls_count >= RED_BALL_LIMIT:  # Limit the number of red balls tracked
            break
        area = cv2.contourArea(contour)
        ((x, y), radius) = cv2.minEnclosingCircle(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        if area > RED_MIN_CONTOUR_AREA and radius > RED_MIN_RADIUS and circularity > RED_MIN_CIRCULARITY:
            centroids.append((int(x), int(y)))
            balls.append((int(x), int(y), int(radius), "red"))
            red_balls_count += 1
            print(f"Red ball at ({x}, {y}) with radius {radius}, area {area}, circularity {circularity}")

    tracked_objects = tracker.update(centroids)
    tracked_balls = []
    for obj_id, (x, y) in tracked_objects.items():
        for ball_x, ball_y, radius, color in balls:
            if abs(ball_x - x) < 10 and abs(ball_y - y) < 10:
                tracked_balls.append((ball_x, ball_y, radius, obj_id, color))
                break
    
    print(f"Tracked {len(tracked_balls)} balls")
    return tracked_balls

def calculate_score(balls, point_zones, last_red_score_time, red_score_cooldown):
    global scored_ball_ids
    round_score = 0
    current_time = time.time()
    for ball_x, ball_y, _, ball_id, color in balls:
        if ball_id not in scored_ball_ids:  # Only score if ball hasn't scored before
            for zone_x, zone_y, zone_radius, points in point_zones:
                distance = np.sqrt((ball_x - zone_x)**2 + (ball_y - zone_y)**2)
                if distance <= zone_radius:
                    base_points = points
                    if color == "red" and (current_time - last_red_score_time >= red_score_cooldown):
                        base_points *= 2  # Double points for red balls
                        print(f"Red ball ID {ball_id} doubled {points} to {base_points} points")
                        last_red_score_time = current_time  # Update last red score time
                    round_score += base_points
                    scored_ball_ids.add(ball_id)  # Mark ball as scored
                    print(f"Ball ID {ball_id} scored {base_points} points")
                    break
    return round_score, last_red_score_time

class CustomDialog:
    def __init__(self, parent, title, prompt):
        self.root = tk.Toplevel(parent)
        self.root.title(title)
        self.root.configure(bg="#2E2E2E")
        self.root.transient(parent)
        self.root.grab_set()
        self.result = None

        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)
        frame.configure(style="Custom.TFrame")

        style = ttk.Style()
        style.configure("Custom.TFrame", background="#2E2E2E")
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#4CAF50", foreground="black")
        style.map("Custom.TButton", background=[("active", "#45A049")], foreground=[("active", "black")])

        label = tk.Label(frame, text=prompt, font=("Helvetica", 10), bg="#2E2E2E", fg="black")
        label.pack(pady=5)

        self.entry = tk.Entry(frame, font=("Helvetica", 10), bg="#4A4A4A", fg="white", insertbackground="white")
        self.entry.pack(pady=5)
        self.entry.focus_set()

        button_frame = ttk.Frame(frame, style="Custom.TFrame")
        button_frame.pack(pady=5)
        ttk.Button(button_frame, text="OK", style="Custom.TButton", command=self.ok).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", style="Custom.TButton", command=self.cancel).pack(side="left", padx=5)

        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
        self.root.bind("<Return>", lambda e: self.ok())
        self.root.bind("<Escape>", lambda e: self.cancel())

    def ok(self):
        self.result = self.entry.get()
        self.root.destroy()

    def cancel(self):
        self.result = None
        self.root.destroy()

    def show(self):
        self.root.wait_window()
        return self.result

class OptionsWindow:
    def __init__(self, on_close_callback, game_instance):
        self.root = tk.Toplevel()
        self.root.title("Options")
        self.root.geometry("400x400")
        self.root.configure(bg="#2E2E2E")
        self.root.resizable(True, True)
        self.on_close_callback = on_close_callback
        self.game = game_instance

        self.frame = ttk.Frame(self.root, padding=10, style="Custom.TFrame")
        self.frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Custom.TFrame", background="#2E2E2E")
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#4CAF50", foreground="black")
        style.map("Custom.TButton", background=[("active", "#45A049")], foreground=[("active", "black")])
        style.configure("Custom.TCheckbutton", foreground="black")  # Ensure checkbutton text is black
        style.configure("Custom.TLabel", foreground="black")  # Ensure label text is black

        tk.Label(self.frame, text="Options", font=("Helvetica", 14, "bold"), bg="#2E2E2E", fg="black").pack(pady=10)

        self.fields = [
            ("Lower Hue (0-180)", BALL_COLOR_RANGE["lower_white"][0], 0, 180),
            ("Lower Sat (0-255)", BALL_COLOR_RANGE["lower_white"][1], 0, 255),
            ("Lower Val (0-255)", BALL_COLOR_RANGE["lower_white"][2], 0, 255),
            ("Upper Hue (0-180)", BALL_COLOR_RANGE["upper_white"][0], 0, 180),
            ("Upper Sat (0-255)", BALL_COLOR_RANGE["upper_white"][1], 0, 255),
            ("Upper Val (0-255)", BALL_COLOR_RANGE["upper_white"][2], 0, 255),
        ]
        self.entries = []
        for i, (label, value, _, _) in enumerate(self.fields):
            tk.Label(self.frame, text=label, font=("Helvetica", 10), bg="#2E2E2E", fg="black", style="Custom.TLabel").pack(pady=2)
            entry = ttk.Entry(self.frame, font=("Helvetica", 10))
            entry.insert(0, str(value))
            entry.pack(pady=2)
            self.entries.append(entry)

        # Add music mute/unmute toggle
        self.music_var = tk.BooleanVar(value=True)  # True means music is on
        tk.Checkbutton(self.frame, text="Mute Music", variable=self.music_var, command=self.toggle_music, style="Custom.TCheckbutton").pack(pady=5)

        # Add sound effects enable/disable toggle
        self.sound_effects_var = tk.BooleanVar(value=not self.game.sound_effects_enabled)  # Invert because checkbox is "Disable"
        tk.Checkbutton(self.frame, text="Disable Sound Effects", variable=self.sound_effects_var, command=self.toggle_sound_effects, style="Custom.TCheckbutton").pack(pady=5)

        button_frame = ttk.Frame(self.frame, style="Custom.TFrame")
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", style="Custom.TButton", command=self.save).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Close", style="Custom.TButton", command=self.close).pack(side="left", padx=5)

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def save(self):
        global BALL_COLOR_RANGE
        try:
            BALL_COLOR_RANGE["lower_white"] = [int(self.entries[0].get()), int(self.entries[1].get()), int(self.entries[2].get())]
            BALL_COLOR_RANGE["upper_white"] = [int(self.entries[3].get()), int(self.entries[4].get()), int(self.entries[5].get())]
            save_config(not self.sound_effects_var.get())  # Save the inverted state (Disable = False means enabled)
            print("Options saved")
        except ValueError:
            print("Invalid input in options")
        self.root.destroy()
        self.on_close_callback()

    def toggle_music(self):
        if self.music_var.get():
            pygame.mixer.music.unpause()
            print("Music unmuted")
        else:
            pygame.mixer.music.pause()
            print("Music muted")
        self.root.destroy()
        self.on_close_callback()

    def toggle_sound_effects(self):
        self.game.sound_effects_enabled = not self.sound_effects_var.get()  # Invert because checkbox is "Disable"
        print(f"Sound effects {'disabled' if not self.game.sound_effects_enabled else 'enabled'}")
        self.root.destroy()
        self.on_close_callback()

    def close(self):
        self.root.destroy()
        self.on_close_callback()

class HelpWindow:
    def __init__(self, on_close_callback):
        self.root = tk.Toplevel()
        self.root.title("Help")
        self.root.geometry("400x300")
        self.root.configure(bg="#2E2E2E")
        self.root.resizable(True, True)
        self.on_close_callback = on_close_callback

        self.frame = ttk.Frame(self.root, padding=10, style="Custom.TFrame")
        self.frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Custom.TFrame", background="#2E2E2E")
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#F44336", foreground="black")
        style.map("Custom.TButton", background=[("active", "#D32F2F")], foreground=[("active", "black")])
        style.configure("Custom.TLabel", foreground="black")  # Ensure label text is black

        tk.Label(self.frame, text="Help", font=("Helvetica", 14, "bold"), bg="#2E2E2E", fg="black", style="Custom.TLabel").pack(pady=10)

        help_lines = [
            "Hotkeys: 'q' to quit, 'c' to calibrate",
            "Menu: File (save/load)",
            "New Game (reset), High Score (view)",
            "Options (settings)",
            "Credits: Ideas by Blake Weibling, coding help from Grok3"
        ]
        for line in help_lines:
            tk.Label(self.frame, text=line, font=("Helvetica", 10), bg="#2E2E2E", fg="black", style="Custom.TLabel").pack(pady=5)

        ttk.Button(self.frame, text="Close", style="Custom.TButton", command=self.close).pack(pady=10)

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        self.root.destroy()
        self.on_close_callback()

class WhiffleGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Whiffle Playfield")
        self.root.geometry("800x600")
        self.root.configure(bg="#2E2E2E")
        self.root.resizable(True, True)

        # Load sound effects
        try:
            self.ball_detected_sound = pygame.mixer.Sound("ball_detected.wav")
            self.score_sound = pygame.mixer.Sound("score.wav")
            self.game_start_sound = pygame.mixer.Sound("game_start.wav")
        except pygame.error as e:
            print(f"Error loading sound effects: {e}")
            self.ball_detected_sound = None
            self.score_sound = None
            self.game_start_sound = None

        # Load background music
        try:
            pygame.mixer.music.load("background_music.mp3")
            pygame.mixer.music.set_volume(0.5)  # Set volume to 50%
            pygame.mixer.music.play(-1)  # Play on loop (-1 for infinite)
        except pygame.error as e:
            print(f"Error loading background music: {e}")

        # Load sound effects setting from config file
        self.sound_effects_enabled = load_config()

        style = ttk.Style()
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#2196F3", foreground="black")
        style.map("Custom.TButton", background=[("active", "#1976D2")], foreground=[("active", "black")])

        menu_frame = ttk.Frame(self.root, style="Custom.TFrame")
        menu_frame.pack(fill="x", pady=5, padx=10)
        buttons = [
            ("File", self.file_menu),
            ("New Game", self.new_game),
            ("High Score", self.high_score),
            ("Options", self.options_menu),
            ("Help", self.help_menu),
        ]
        for text, command in buttons:
            ttk.Button(menu_frame, text=text, style="Custom.TButton", command=command).pack(side="left", padx=5)

        self.canvas = tk.Canvas(self.root, bg="#2E2E2E", highlightthickness=2, highlightbackground="#2196F3")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.canvas_click)

        self.save_button = ttk.Button(self.root, text="Save Zones", style="Custom.TButton", command=self.queue_save_zones, state="disabled")
        self.save_button.pack(pady=5)

        self.stats_frame = ttk.Frame(self.root, style="Custom.TFrame")
        self.stats_frame.pack(fill="x", padx=10, pady=5)
        self.balls_label = tk.Label(self.stats_frame, text="Balls: 0", font=("Helvetica", 12), bg="#2E2E2E", fg="white")
        self.balls_label.pack(side="left", padx=10)
        self.score_label = tk.Label(self.stats_frame, text="Score: 0", font=("Helvetica", 12), bg="#2E2E2E", fg="white")
        self.score_label.pack(side="left", padx=10)
        self.res_label = tk.Label(self.stats_frame, text="Res: 0x0", font=("Helvetica", 12), bg="#2E2E2E", fg="white")
        self.res_label.pack(side="right", padx=10)

        # Select the webcam dynamically
        webcam_index = select_webcam()
        if webcam_index is None:
            print("Error: No webcam selected. Exiting.")
            self.root.destroy()
            return

        # Use the selected webcam index
        self.cap = cv2.VideoCapture(webcam_index, WEBCAM_BACKEND)
        if not self.cap.isOpened():
            print("Error: Could not open webcam.")
            self.root.destroy()
            return
        
        self.width, self.height, initial_frame = set_webcam_resolution(self.cap)
        if self.width is None or self.height is None:
            print("Error: Could not set resolution.")
            self.cap.release()
            self.root.destroy()
            return

        global high_score, high_score_initials, current_score, scored_ball_ids
        high_score = load_high_score()
        current_score = 0
        self.point_zones = load_point_zones()
        self.calibrating = not self.point_zones
        self.zone_count = len(self.point_zones)
        self.paused = False
        self.save_triggered = False
        self.zone_circles = []
        self.zone_texts = []
        self.frame = initial_frame
        self.red_zone_circles = []
        self.red_zone_texts = []
        self.green_ball_circles = []
        self.tracker = CentroidTracker(max_disappeared=5)
        self.previous_balls = []  # Track previous balls to detect new ones
        self.last_red_score_time = 0.0  # Track the last time a red ball scored

        if self.calibrating:
            self.save_button.config(state="normal")

        # Play game start sound
        if self.game_start_sound and self.sound_effects_enabled:
            self.game_start_sound.play()

        self.root.after(100, self.update_frame)

    def file_menu(self):
        self.paused = True
        file_window = tk.Toplevel(self.root)
        file_window.title("File")
        file_window.geometry("300x200")
        file_window.configure(bg="#2E2E2E")

        frame = ttk.Frame(file_window, padding=10, style="Custom.TFrame")
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="File Options", font=("Helvetica", 14, "bold"), bg="#2E2E2E", fg="black").pack(pady=10)
        tk.Button(frame, text="Save", font=("Helvetica", 10), bg="#4CAF50", fg="black", 
                  command=lambda: self.save_file(file_window)).pack(pady=5)
        tk.Button(frame, text="Load", font=("Helvetica", 10), bg="#2196F3", fg="black", 
                  command=lambda: self.load_file(file_window)).pack(pady=5)

    def save_file(self, window):
        dialog = CustomDialog(window, "Save", "Enter filename:")
        filename = dialog.show()
        if filename:
            save_point_zones(self.point_zones, filename)
        window.destroy()
        self.paused = False
        self.update_frame()

    def load_file(self, window):
        dialog = CustomDialog(window, "Load", "Enter filename:")
        filename = dialog.show()
        if filename:
            loaded_zones = load_point_zones(filename)
            if loaded_zones:
                self.point_zones = loaded_zones
                self.zone_count = len(self.point_zones)
                self.update_frame()
        window.destroy()
        self.paused = False
        self.update_frame()

    def new_game(self):
        global current_score, scored_ball_ids
        current_score = 0
        scored_ball_ids.clear()  # Reset scored ball IDs
        self.tracker = CentroidTracker(max_disappeared=5)
        self.previous_balls = []  # Reset previous balls
        # Play game start sound
        if self.game_start_sound and self.sound_effects_enabled:
            self.game_start_sound.play()
        self.update_frame()

    def high_score(self):
        self.paused = True
        high_score_window = tk.Toplevel(self.root)
        high_score_window.title("High Score")
        high_score_window.geometry("200x100")
        high_score_window.configure(bg="#2E2E2E")

        frame = ttk.Frame(high_score_window, padding=10, style="Custom.TFrame")
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"High Score: {high_score} by {high_score_initials}", font=("Helvetica", 14), bg="#2E2E2E", fg="black").pack(pady=10)
        tk.Button(frame, text="Close", font=("Helvetica", 10), bg="#F44336", fg="black", 
                  command=lambda: self.close_high_score(high_score_window)).pack(pady=5)

    def close_high_score(self, window):
        window.destroy()
        self.paused = False
        self.update_frame()

    def options_menu(self):
        self.paused = True
        OptionsWindow(self.resume_frame, self)  # Pass self to access game instance

    def help_menu(self):
        self.paused = True
        HelpWindow(self.resume_frame)

    def resume_frame(self):
        self.paused = False
        self.update_frame()

    def queue_save_zones(self):
        if self.calibrating and self.point_zones:
            self.save_triggered = True

    def canvas_click(self, event):
        if not self.calibrating:
            return

        x, y = event.x, event.y
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
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
            adjusted_x = x - offset_x
            adjusted_y = y - offset_y
            scale_x = frame_width / new_width
            scale_y = frame_height / new_height
            x_frame = int(adjusted_x * scale_x)
            y_frame = int(adjusted_y * scale_y)
        else:
            x_frame = x
            y_frame = y

        radius = CALIBRATION_VISUAL_RADIUS
        circle_id = self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, 
                                           outline="blue", width=2)
        self.zone_circles.append(circle_id)

        self.paused = True
        dialog = CustomDialog(self.root, "Points", f"Points for zone at ({x_frame}, {y_frame}):")
        points = dialog.show()
        if points is not None and points.strip():
            try:
                points = int(points)
                self.point_zones.append((x_frame, y_frame, ZONE_RADIUS, points))
                self.zone_count += 1
                text_id = self.canvas.create_text(x, y + radius + 15, text=str(points), fill="white", font=("Helvetica", 10))
                self.zone_texts.append(text_id)
            except ValueError:
                self.canvas.delete(self.zone_circles.pop())
                if self.zone_texts:
                    self.canvas.delete(self.zone_texts.pop())
        self.paused = False

        if self.zone_count >= TOTAL_ZONES:
            self.save_triggered = True

    def update_frame(self):
        if self.paused:
            self.root.after(10, self.update_frame)
            return

        ret, self.frame = self.cap.read()
        if not ret:
            print("Failed to read frame.")
            self.root.destroy()
            return

        frame_rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width > 0 and canvas_height > 0:
            aspect_ratio = self.frame.shape[1] / self.frame.shape[0]
            new_height = int(canvas_width / aspect_ratio)
            if new_height > canvas_height:
                new_height = canvas_height
                new_width = int(canvas_height * aspect_ratio)
            else:
                new_width = canvas_width
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            new_width, new_height = self.frame.shape[1], self.frame.shape[0]
        
        offset_x = (canvas_width - new_width) // 2
        offset_y = (canvas_height - new_height) // 2

        self.photo = ImageTk.PhotoImage(image=img)
        self.canvas.create_image(offset_x, offset_y, image=self.photo, anchor="nw")

        for circle_id in self.red_zone_circles:
            self.canvas.delete(circle_id)
        for text_id in self.red_zone_texts:
            self.canvas.delete(text_id)
        for circle_id in self.green_ball_circles:
            self.canvas.delete(circle_id)
        self.red_zone_circles = []
        self.red_zone_texts = []
        self.green_ball_circles = []

        if self.save_triggered and self.calibrating:
            if self.point_zones:
                save_point_zones(self.point_zones)
            self.calibrating = False
            self.save_triggered = False
            self.save_button.config(state="disabled")

        if self.calibrating:
            cv2.putText(self.frame, f"Click to define zones ({self.zone_count}/{TOTAL_ZONES})", 
                        (10, self.frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            self.save_button.config(state="normal")
        else:
            self.save_button.config(state="disabled")
            tracked_balls = detect_and_track_balls(self.frame, self.tracker)
            total_balls = len(tracked_balls)

            # Detect new balls and play sound
            new_balls = [ball for ball in tracked_balls if ball[3] not in [pb[3] for pb in self.previous_balls]]
            if new_balls and self.ball_detected_sound and self.sound_effects_enabled:
                self.ball_detected_sound.play()

            round_score, self.last_red_score_time = calculate_score(tracked_balls, self.point_zones, self.last_red_score_time, RED_BALL_COOLDOWN)
            global current_score, high_score, high_score_initials, scored_ball_ids
            if round_score > 0 and self.score_sound and self.sound_effects_enabled:
                self.score_sound.play()  # Play sound when points are scored
            current_score += round_score  # Add only new scores

            # Check for new high score and prompt for initials
            if current_score > high_score:
                high_score = current_score
                self.paused = True
                dialog = CustomDialog(self.root, "New High Score!", "Enter your initials (3 letters):")
                initials = dialog.show()
                if initials and len(initials) > 0:
                    # Limit to 3 characters and uppercase
                    initials = initials.upper()[:3]
                    save_high_score(initials)
                else:
                    save_high_score("N/A")  # Default if no initials entered
                self.paused = False

            self.previous_balls = tracked_balls  # Update previous balls

            for (x, y, r, ball_id, color) in tracked_balls:
                x_canvas = int(x * (new_width / self.frame.shape[1]) + offset_x)
                y_canvas = int(y * (new_height / self.frame.shape[0]) + offset_y)
                r_canvas = int(r * (new_width / self.frame.shape[1]))
                outline_color = "red" if color == "red" else "green"
                circle_id = self.canvas.create_oval(x_canvas - r_canvas, y_canvas - r_canvas,
                                                    x_canvas + r_canvas, y_canvas + r_canvas,
                                                    outline=outline_color, width=2)
                self.green_ball_circles.append(circle_id)
                text_id = self.canvas.create_text(x_canvas, y_canvas - r_canvas - 10, 
                                                 text=f"ID: {ball_id} ({color})", fill="yellow", font=("Helvetica", 8))
                self.green_ball_circles.append(text_id)

            self.balls_label.config(text=f"Balls: {total_balls}")
            self.score_label.config(text=f"Score: {current_score}")
            self.res_label.config(text=f"Res: {self.width}x{self.height}")

        for x_frame, y_frame, r, points in self.point_zones:
            x_canvas = int(x_frame * (new_width / self.frame.shape[1]) + offset_x)
            y_canvas = int(y_frame * (new_height / self.frame.shape[0]) + offset_y)
            r_canvas = int(r * (new_width / self.frame.shape[1]))
            circle_id = self.canvas.create_oval(x_canvas - r_canvas, y_canvas - r_canvas, 
                                                x_canvas + r_canvas, y_canvas + r_canvas, 
                                                outline="red", width=2)
            self.red_zone_circles.append(circle_id)
            text_id = self.canvas.create_text(x_canvas, y_canvas, text=str(points), 
                                              fill="white", font=("Helvetica", 10))
            self.red_zone_texts.append(text_id)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            save_high_score(high_score_initials)
            self.root.destroy()
            return
        elif key == ord('c'):
            self.point_zones = []
            self.calibrating = True
            self.zone_count = 0
            global scored_ball_ids
            scored_ball_ids.clear()  # Reset scored ball IDs on calibration
            self.tracker = CentroidTracker(max_disappeared=5)
            for circle_id in self.zone_circles + self.red_zone_circles + self.green_ball_circles:
                self.canvas.delete(circle_id)
            for text_id in self.zone_texts + self.red_zone_texts:
                self.canvas.delete(text_id)
            self.zone_circles = []
            self.zone_texts = []
            self.red_zone_circles = []
            self.red_zone_texts = []
            self.green_ball_circles = []

        self.root.after(10, self.update_frame)

    def destroy(self):
        self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = WhiffleGame(root)
    root.mainloop()