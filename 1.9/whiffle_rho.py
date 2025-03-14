import cv2
import numpy as np
import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog
from PIL import Image, ImageTk

# Fixed radius for scoring zones
ZONE_RADIUS = 30  # Scoring radius
CALIBRATION_VISUAL_RADIUS = 15  # Visual feedback radius
TOTAL_ZONES = 21  # Number of zones to trigger automatic save

# Files
CALIBRATION_FILE = "whiffle_zones.json"
HIGH_SCORE_FILE = "whiffle_high_score.json"

# Detection settings
BALL_COLOR_RANGE = {"lower_white": [0, 0, 200], "upper_white": [180, 50, 255]}

# Game state
current_score = 0
high_score = 0

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
    print(f"Zones saved to {filename}")  # Debug output

def load_high_score():
    global high_score
    if os.path.exists(HIGH_SCORE_FILE):
        with open(HIGH_SCORE_FILE, 'r') as f:
            high_score = json.load(f).get("high_score", 0)
    print(f"Loaded high score: {high_score}")  # Debug output
    return high_score

def save_high_score():
    with open(HIGH_SCORE_FILE, 'w') as f:
        json.dump({"high_score": high_score}, f)
    print(f"Saved high score: {high_score}")  # Debug output

def set_webcam_resolution(cap):
    resolutions = [
        (1920, 1080),
        (1280, 720),
        (640, 480),
    ]
    for width, height in resolutions:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        for _ in range(5):  # Retry up to 5 times
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"Successfully set resolution to {actual_width}x{actual_height}")  # Debug output
                return actual_width, actual_height, frame
            time.sleep(0.1)
        print(f"Failed to read frame at {width}x{height}, trying next resolution")  # Debug output
    print("Failed to set a working resolution.")  # Debug output
    return None, None, None

def detect_balls(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_white = np.array(BALL_COLOR_RANGE["lower_white"])
    upper_white = np.array(BALL_COLOR_RANGE["upper_white"])
    mask = cv2.inRange(hsv, lower_white, upper_white)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    balls = []
    for contour in contours:
        ((x, y), radius) = cv2.minEnclosingCircle(contour)
        if radius > 10:
            balls.append((int(x), int(y), int(radius)))
    return balls

def calculate_score(balls, point_zones):
    total_score = 0
    for ball_x, ball_y, _ in balls:
        for zone_x, zone_y, zone_radius, points in point_zones:
            distance = np.sqrt((ball_x - zone_x)**2 + (ball_y - zone_y)**2)
            if distance <= zone_radius:
                total_score += points
                break
    return total_score

class OptionsWindow:
    def __init__(self, on_close_callback):
        self.root = tk.Toplevel()
        self.root.title("Options")
        self.root.geometry("400x400")
        self.root.configure(bg="#2E2E2E")
        self.root.resizable(True, True)
        self.on_close_callback = on_close_callback

        # Frame for styling
        self.frame = ttk.Frame(self.root, padding=10, style="Custom.TFrame")
        self.frame.pack(fill="both", expand=True)

        # Style for frame and buttons
        style = ttk.Style()
        style.configure("Custom.TFrame", background="#2E2E2E")
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#4CAF50", foreground="white")
        style.map("Custom.TButton", background=[("active", "#45A049")])

        # Title
        tk.Label(self.frame, text="Options", font=("Helvetica", 14, "bold"), bg="#2E2E2E", fg="white").pack(pady=10)

        # Fields for HSV values
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
            tk.Label(self.frame, text=label, font=("Helvetica", 10), bg="#2E2E2E", fg="white").pack()
            entry = ttk.Entry(self.frame, font=("Helvetica", 10))
            entry.insert(0, str(value))
            entry.pack(pady=2)
            self.entries.append(entry)

        # Buttons
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
            print("Options saved")
        except ValueError:
            print("Invalid input in options")
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

        # Frame for styling
        self.frame = ttk.Frame(self.root, padding=10, style="Custom.TFrame")
        self.frame.pack(fill="both", expand=True)

        # Style
        style = ttk.Style()
        style.configure("Custom.TFrame", background="#2E2E2E")
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#F44336", foreground="white")
        style.map("Custom.TButton", background=[("active", "#D32F2F")])

        # Title
        tk.Label(self.frame, text="Help", font=("Helvetica", 14, "bold"), bg="#2E2E2E", fg="white").pack(pady=10)

        # Help text
        help_lines = [
            "Hotkeys: 'q' to quit, 'c' to calibrate",
            "Menu: File (save/load)",
            "New Game (reset), High Score (view)",
            "Options (settings)",
        ]
        for line in help_lines:
            tk.Label(self.frame, text=line, font=("Helvetica", 10), bg="#2E2E2E", fg="white").pack(pady=5)

        # Close button
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

        # Style for buttons
        style = ttk.Style()
        style.configure("Custom.TButton", font=("Helvetica", 10), background="#2196F3", foreground="black")
        style.map("Custom.TButton", background=[("active", "#1976D2")])

        # Menu bar
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

        # Canvas for webcam feed
        self.canvas = tk.Canvas(self.root, bg="#2E2E2E", highlightthickness=2, highlightbackground="#2196F3")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.canvas_click)

        # Save button for manual save
        self.save_button = ttk.Button(self.root, text="Save Zones", style="Custom.TButton", command=self.save_zones, state="disabled")
        self.save_button.pack(pady=5)

        # Labels for game stats
        self.stats_frame = ttk.Frame(self.root, style="Custom.TFrame")
        self.stats_frame.pack(fill="x", padx=10, pady=5)
        self.balls_label = tk.Label(self.stats_frame, text="Balls: 0", font=("Helvetica", 12), bg="#2E2E2E", fg="white")
        self.balls_label.pack(side="left", padx=10)
        self.score_label = tk.Label(self.stats_frame, text="Score: 0", font=("Helvetica", 12), bg="#2E2E2E", fg="white")
        self.score_label.pack(side="left", padx=10)
        self.res_label = tk.Label(self.stats_frame, text="Res: 0x0", font=("Helvetica", 12), bg="#2E2E2E", fg="white")
        self.res_label.pack(side="right", padx=10)

        # Initialize webcam
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            print("Error: Could not open webcam.")
            self.root.destroy()
            return
        
        self.width, self.height, initial_frame = set_webcam_resolution(self.cap)
        if self.width is None or self.height is None:
            print("Error: Could not set a working resolution for the webcam.")
            self.cap.release()
            self.root.destroy()
            return

        # Load game state
        global high_score, current_score
        high_score = load_high_score()
        current_score = 0
        self.point_zones = load_point_zones()
        self.calibrating = not self.point_zones
        self.zone_count = len(self.point_zones)
        self.paused = False
        self.zone_circles = []
        self.zone_texts = []
        self.frame = initial_frame  # Initialize with the first frame

        # Enable save button during calibration
        if self.calibrating:
            self.save_button.config(state="normal")

        # Start video loop
        self.update_frame()

    def file_menu(self):
        print("File menu clicked")
        self.paused = True
        file_window = tk.Toplevel(self.root)
        file_window.title("File")
        file_window.geometry("300x200")
        file_window.configure(bg="#2E2E2E")

        frame = ttk.Frame(file_window, padding=10, style="Custom.TFrame")
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="File Options", font=("Helvetica", 14, "bold"), bg="#2E2E2E", fg="white").pack(pady=10)

        tk.Button(frame, text="Save", font=("Helvetica", 10), bg="#4CAF50", fg="white", 
                  command=lambda: self.save_file(file_window)).pack(pady=5)
        tk.Button(frame, text="Load", font=("Helvetica", 10), bg="#2196F3", fg="white", 
                  command=lambda: self.load_file(file_window)).pack(pady=5)

    def save_file(self, window):
        filename = simpledialog.askstring("Save", "Enter filename:", parent=window)
        if filename:
            save_point_zones(self.point_zones, filename)
        window.destroy()
        self.paused = False
        self.update_frame()

    def load_file(self, window):
        filename = simpledialog.askstring("Load", "Enter filename:", parent=window)
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
        print("New Game clicked")
        global current_score
        current_score = 0
        self.update_frame()

    def high_score(self):
        print("High Score clicked")
        self.paused = True
        high_score_window = tk.Toplevel(self.root)
        high_score_window.title("High Score")
        high_score_window.geometry("200x100")
        high_score_window.configure(bg="#2E2E2E")

        frame = ttk.Frame(high_score_window, padding=10, style="Custom.TFrame")
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"High Score: {high_score}", font=("Helvetica", 14), bg="#2E2E2E", fg="white").pack(pady=10)
        tk.Button(frame, text="Close", font=("Helvetica", 10), bg="#F44336", fg="white", 
                  command=lambda: self.close_high_score(high_score_window)).pack(pady=5)

    def close_high_score(self, window):
        window.destroy()
        self.paused = False
        self.update_frame()

    def options_menu(self):
        print("Options clicked")
        self.paused = True
        OptionsWindow(self.resume_frame)

    def help_menu(self):
        print("Help clicked")
        self.paused = True
        HelpWindow(self.resume_frame)

    def resume_frame(self):
        self.paused = False
        self.update_frame()

    def save_zones(self):
        if self.calibrating and self.point_zones:
            save_point_zones(self.point_zones)
            print("Zones saved manually, transitioning to scoring mode")
            self.calibrating = False
            self.save_button.config(state="disabled")
            self.update_frame()

    def canvas_click(self, event):
        if not self.calibrating:
            return

        print(f"Canvas clicked at ({event.x}, {event.y})")
        x, y = event.x, event.y

        # Adjust coordinates based on canvas scaling for OpenCV frame
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if self.frame is not None:
            frame_width, frame_height = self.frame.shape[1], self.frame.shape[0]
            scale_x = frame_width / canvas_width
            scale_y = frame_height / canvas_height
            x_frame = int(x * scale_x)
            y_frame = int(y * scale_y)
        else:
            x_frame = x
            y_frame = y

        # Draw blue circle on canvas using canvas coordinates
        radius = CALIBRATION_VISUAL_RADIUS
        circle_id = self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, 
                                           outline="blue", width=2)
        self.zone_circles.append(circle_id)

        # Pause video updates while dialog is open
        self.paused = True
        self.current_entry = simpledialog.askstring("Points", f"Points for zone at ({x_frame}, {y_frame}):", parent=self.root)
        if self.current_entry:
            try:
                points = int(self.current_entry)
                self.point_zones.append((x_frame, y_frame, ZONE_RADIUS, points))
                self.zone_count += 1
                print(f"Zone added, total zones: {self.zone_count}")  # Debug
                # Draw text on canvas using canvas coordinates
                text_id = self.canvas.create_text(x, y + radius + 15, text=str(points), fill="white", font=("Helvetica", 10))
                self.zone_texts.append(text_id)
            except ValueError:
                self.canvas.delete(self.zone_circles.pop())
                if self.zone_texts:
                    self.canvas.delete(self.zone_texts.pop())
        self.paused = False

        # Check for automatic save after 21 zones
        if self.zone_count >= TOTAL_ZONES:
            save_point_zones(self.point_zones)
            print("Reached 21 zones, saved zones, transitioning to scoring mode")
            self.calibrating = False
            self.save_button.config(state="disabled")
            self.update_frame()

    def update_frame(self):
        try:
            ret, self.frame = self.cap.read()
            if not ret:
                print("Failed to read frame after retries, exiting.")
                self.root.destroy()
                return
        except Exception as e:
            print(f"Error reading frame: {e}")
            self.root.destroy()
            return

        if self.paused:
            self.root.after(10, self.update_frame)
            return

        if self.calibrating:
            cv2.putText(self.frame, f"Click to define zones ({self.zone_count}/{TOTAL_ZONES})", 
                        (10, self.frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            self.save_button.config(state="normal")
        else:
            self.save_button.config(state="disabled")
            balls = detect_balls(self.frame)
            total_balls = len(balls)
            round_score = calculate_score(balls, self.point_zones)
            global current_score, high_score
            current_score = max(current_score, round_score)
            high_score = max(high_score, current_score)

            for (x, y, r) in balls:
                cv2.circle(self.frame, (x, y), r, (0, 255, 0), 2)
            
            for (x, y, r, points) in self.point_zones:
                cv2.circle(self.frame, (x, y), r, (0, 0, 255), 2)
                cv2.putText(self.frame, str(points), (x - 10, y), cv2.FONT_HERSHEY_SIMPLEX, 
                            0.5, (255, 255, 255), 2)

            self.balls_label.config(text=f"Balls: {total_balls}")
            self.score_label.config(text=f"Score: {current_score}")
            self.res_label.config(text=f"Res: {self.width}x{self.height}")

        # Convert frame to RGB and display on canvas
        frame_rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        img = img.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image=img)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        # Handle key presses
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            save_high_score()
            self.root.destroy()
            return
        elif key == ord('c'):
            self.point_zones = []
            self.calibrating = True
            self.zone_count = 0
            # Clear existing circles and text from canvas
            for circle_id in self.zone_circles:
                self.canvas.delete(circle_id)
            for text_id in self.zone_texts:
                self.canvas.delete(text_id)
            self.zone_circles = []
            self.zone_texts = []

        self.root.after(10, self.update_frame)

    def destroy(self):
        self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = WhiffleGame(root)
    root.mainloop()