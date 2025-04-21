import cv2
import numpy as np
import pygame
import sys
from pygame.locals import *
import time
import json
import os
from picamera2 import Picamera2  # For Raspberry Pi camera module

# Logging Control
DEBUG = False

# Initialize Pygame
pygame.init()
INITIAL_WIDTH, INITIAL_HEIGHT = 1280, 720  # Restored to original resolution
screen = pygame.display.set_mode((INITIAL_WIDTH, INITIAL_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Whiffle Playfield (RPi5)")

# Load splash screen
try:
    splash_image = pygame.image.load("whiffle_splash.jpg").convert_alpha()
    splash_image = pygame.transform.smoothscale(splash_image, (INITIAL_WIDTH, INITIAL_HEIGHT))
except FileNotFoundError:
    print("Splash screen 'whiffle_splash.jpg' not found. Using blank.")
    splash_image = pygame.Surface((INITIAL_WIDTH, INITIAL_HEIGHT), pygame.SRCALPHA)
    splash_image.fill((50, 50, 50))

screen.blit(splash_image, (0, 0))
pygame.display.flip()

# Audio initialization (optimized for Pi)
pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
clock = pygame.time.Clock()

# Background Music
BACKGROUND_MUSIC_FILE = "background_music.mp3"
try:
    pygame.mixer.music.load(BACKGROUND_MUSIC_FILE)
    pygame.mixer.music.set_volume(0.5)
    pygame.mixer.music.play(-1)
    print(f"Background music '{BACKGROUND_MUSIC_FILE}' playing.")
except FileNotFoundError:
    print(f"Music file '{BACKGROUND_MUSIC_FILE}' not found.")
except Exception as e:
    print(f"Error loading music: {e}")

# Constants
COOLDOWN_FRAMES = 30
CONFIRMATION_FRAMES = 10
SOUND_COOLDOWN = 1.0
MENU_HEIGHT = 60  # Restored original menu height
STATUS_BAR_HEIGHT = 50  # Restored original status bar height

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)
LIGHT_GRAY = (100, 100, 100)
BUTTON_BORDER = (0, 0, 0)
SUBMENU_BG = (50, 50, 50, 200)

# HSV and Volume Settings
lower_white = np.array([0, 0, 200])
upper_white = np.array([180, 30, 255])
lower_red = np.array([0, 100, 100])
upper_red = np.array([10, 255, 255])
volume = 0.5
pygame.mixer.music.set_volume(volume)

# Load sound effect
try:
    score_sound = pygame.mixer.Sound("score.wav")
except FileNotFoundError:
    print("Sound 'score.wav' not found.")
    score_sound = None

# Game State
class GameState:
    def __init__(self):
        self.score = 0
        self.balls = 10
        self.power_up = None
        self.time = "N/A"
        self.hole_positions = []
        self.running = True
        self.scored_balls = set()
        self.detection_cooldown = {}
        self.detected_positions = []
        self.confirming_balls = {}
        self.just_reset = False
        self.last_sound_time = 0

    def reset(self):
        self.score = 0
        self.balls = 10
        self.power_up = None
        self.time = "N/A"
        self.scored_balls.clear()
        self.detection_cooldown.clear()
        self.detected_positions.clear()
        self.confirming_balls.clear()
        self.just_reset = True
        print("Game reset: Score = 0, Balls = 10")

    def get_nearest_hole(self, pos, scale_x=1.0, scale_y=1.0):
        min_dist = float('inf')
        nearest_hole = None
        for hole in self.hole_positions:
            x, y, radius, points, is_oblong, rect = hole
            scaled_x = int(x * scale_x)
            scaled_y = int(y * scale_y)
            scaled_radius = int(radius * scale_x)
            if is_oblong and rect:
                x1, y1, x2, y2 = rect
                scaled_x1 = int(x1 * scale_x)
                scaled_y1 = int(y1 * scale_y)
                scaled_x2 = int(x2 * scale_x)
                scaled_y2 = int(y2 * scale_y)
                if scaled_x1 <= pos[0] <= scaled_x2 and scaled_y1 <= pos[1] <= scaled_y2:
                    nearest_hole = (scaled_x, scaled_y, scaled_radius, points, is_oblong, (scaled_x1, scaled_y1, scaled_x2, scaled_y2))
                    break
            else:
                dist = np.hypot(pos[0] - scaled_x, pos[1] - scaled_y)
                if dist < min_dist and dist <= scaled_radius:
                    min_dist = dist
                    nearest_hole = (scaled_x, scaled_y, scaled_radius, points, is_oblong, None)
        return nearest_hole

game = GameState()

# Simplified Menu System (restored some functionality)
class Menu:
    def __init__(self):
        self.active = True
        self.options = {
            "File": {"(C)alibrate": lambda: calibrate_holes()},
            "Settings": {"Adjust": lambda: settings_window.active = True},
            "Help": {"(A)bout": lambda: about_window.active = True},
            "Leaderboard": {"(L)eaderboard": lambda: leaderboard_window.active = True}
        }
        self.font = pygame.font.Font(None, 30)  # Restored original font size
        self.selected = None
        self.submenu = None
        self.hovered_main = None
        self.hovered_sub = None

    def draw(self, screen):
        current_width, _ = screen.get_size()
        menu_surface = pygame.Surface((current_width, MENU_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(menu_surface, DARK_GRAY, (0, 0, current_width, MENU_HEIGHT))
        x_offset = 10
        for main_option in self.options:
            text = self.font.render(main_option, True, WHITE if main_option != self.hovered_main else YELLOW)
            rect = text.get_rect(topleft=(x_offset, 5))
            menu_surface.blit(text, rect)
            x_offset += rect.width + 20
        screen.blit(menu_surface, (0, 0))

    def handle_mouse_input(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered_main = None
            mouse_pos = event.pos
            x_offset = 10
            for main_option in self.options:
                text = self.font.render(main_option, True, WHITE)
                rect = text.get_rect(topleft=(x_offset, 5))
                if rect.collidepoint(mouse_pos):
                    self.hovered_main = main_option
                x_offset += rect.width + 20
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered_main and list(self.options[self.hovered_main].values())[0]():
                return True
        return False

menu = Menu()

# About Window (restored some detail)
class AboutWindow:
    def __init__(self):
        self.active = False
        self.font = pygame.font.Font(None, 24)
        self.text = [
            "Whiffle Board - 1931",
            "First Pinball Machine",
            "By Automatic Industries",
            "Electrically-powered scoring",
            "Press ESC to close"
        ]
        self.window_width, self.window_height = 400, 200

    def draw(self, screen):
        if not self.active:
            return
        surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        surface.fill((200, 200, 200, 200))
        for i, line in enumerate(self.text):
            text = self.font.render(line, True, BLACK)
            surface.blit(text, (10, 10 + i * 30))
        screen.blit(surface, ((screen.get_width() - self.window_width) // 2, (screen.get_height() - self.window_height) // 2))

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            return True
        return False

about_window = AboutWindow()

# Settings Window (restored volume control)
class SettingsWindow:
    def __init__(self):
        self.active = False
        self.font = pygame.font.Font(None, 24)
        self.window_width, self.window_height = 400, 200
        self.slider_values = {"volume": volume * 100}
        self.slider_positions = {}

    def draw(self, screen):
        if not self.active:
            return
        surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        surface.fill((200, 200, 200, 200))
        text = self.font.render(f"Volume: {int(self.slider_values['volume'])}", True, BLACK)
        surface.blit(text, (10, 10))
        slider_x, slider_y, slider_length = 100, 40, 200
        pygame.draw.rect(surface, WHITE, (slider_x, slider_y, slider_length, 10))
        slider_pos = slider_x + (slider_length - 20) * (self.slider_values["volume"] / 100)
        pygame.draw.rect(surface, BLUE, (slider_pos, slider_y - 5, 20, 20))
        self.slider_positions["volume"] = (slider_x, slider_y, slider_length)
        screen.blit(surface, ((screen.get_width() - self.window_width) // 2, (screen.get_height() - self.window_height) // 2))

    def handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            window_x = (screen.get_width() - self.window_width) // 2
            window_y = (screen.get_height() - self.window_height) // 2
            slider_x, slider_y, slider_length = self.slider_positions["volume"]
            slider_rect = pygame.Rect(slider_x + window_x, slider_y + window_y - 5, slider_length, 20)
            if slider_rect.collidepoint(mouse_pos):
                value = ((mouse_pos[0] - (slider_x + window_x)) / (slider_length - 20)) * 100
                self.slider_values["volume"] = min(100, max(0, value))
                volume = self.slider_values["volume"] / 100
                pygame.mixer.music.set_volume(volume)
                if score_sound:
                    score_sound.set_volume(volume)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            return True
        return False

settings_window = SettingsWindow()

# Leaderboard Window
class LeaderboardWindow:
    def __init__(self):
        self.active = False
        self.font = pygame.font.Font(None, 24)
        self.window_width, self.window_height = 400, 200
        self.scores = []
        self.load_scores()

    def load_scores(self):
        try:
            with open("leaderboard.json", "r") as f:
                self.scores = json.load(f)[:10]  # Restored to top 10
        except FileNotFoundError:
            self.scores = []

    def save_score(self, initials, score, date):
        self.scores.append({"initials": initials, "score": score, "date": date})
        self.scores = sorted(self.scores, key=lambda x: x["score"], reverse=True)[:10]
        with open("leaderboard.json", "w") as f:
            json.dump(self.scores, f)

    def draw(self, screen):
        if not self.active:
            return
        surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        surface.fill((200, 200, 200, 200))
        for i, entry in enumerate(self.scores):
            text = self.font.render(f"{i+1}. {entry['initials']} - {entry['score']}", True, BLACK)
            surface.blit(text, (10, 10 + i * 20))
        screen.blit(surface, ((screen.get_width() - self.window_width) // 2, (screen.get_height() - self.window_height) // 2))

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            return True
        return False

leaderboard_window = LeaderboardWindow()

# Calibration
CALIBRATION_FILE = "calibration.json"

def load_calibrated_holes():
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, 'r') as f:
            data = json.load(f)
            return [tuple(hole) for hole in data["holes"]]
    return calibrate_holes()

def save_calibrated_holes(holes):
    with open(CALIBRATION_FILE, 'w') as f:
        json.dump({"holes": holes}, f)

def calibrate_holes():
    pygame.mixer.music.pause()
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (INITIAL_WIDTH, INITIAL_HEIGHT)})
    picam2.configure(config)
    picam2.start()
    calibrated_holes = []
    calibrating = True
    current_pos = None
    points = 0

    while calibrating:
        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                current_pos = event.pos
                points = int(input("Enter points (default 10): ") or 10)
                calibrated_holes.append((current_pos[0], current_pos[1], 20, points, False, None))
                print(f"Added hole at {current_pos} with {points} points")
            if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                calibrating = False
        screen.blit(pygame.surfarray.make_surface(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).swapaxes(0, 1)), (0, 0))
        pygame.display.flip()
    picam2.stop()
    picam2.close()
    if calibrated_holes:
        save_calibrated_holes(calibrated_holes)
    pygame.mixer.music.unpause()
    return calibrated_holes

# Ball Detection (restored red ball detection)
def detect_ball_in_hole(image, game_state, frame_count, scale_x=1.0, scale_y=1.0):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    mask_red = cv2.inRange(hsv, lower_red, upper_red)
    contours, _ = cv2.findContours(mask_white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ball_positions = []
    points_list = []
    is_red_list = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if 100 < area < 1000:  # Adjusted for 1280x720
            M = cv2.moments(contour)
            if M["m00"] != 0:
                ball_x = int(M["m10"] / M["m00"])
                ball_y = int(M["m01"] / M["m00"])
                nearest_hole = game_state.get_nearest_hole((ball_x, ball_y), scale_x, scale_y)
                if nearest_hole and nearest_hole[:2] not in game_state.scored_balls:
                    x, y, _, points = nearest_hole[:4]
                    region_hsv = hsv[max(0, ball_y-2):min(hsv.shape[0], ball_y+3), max(0, ball_x-2):min(hsv.shape[1], ball_x+3)]
                    is_red = cv2.mean(region_hsv)[0] > 100 and cv2.mean(mask_red[max(0, ball_y-2):min(mask_red.shape[0], ball_y+3), max(0, ball_x-2):min(mask_red.shape[1], ball_x+3)])[0] > 50
                    ball_positions.append((x, y))
                    points_list.append(points * 2 if is_red else points)
                    is_red_list.append(is_red)
                    game_state.scored_balls.add((x, y))
                    game_state.detection_cooldown[(x, y)] = frame_count
    return ball_positions, points_list, is_red_list

# UI (restored time display)
font = pygame.font.Font(None, 36)
def draw_ui():
    current_width, current_height = screen.get_size()
    status_surface = pygame.Surface((current_width, STATUS_BAR_HEIGHT))
    status_surface.fill(GRAY)
    score_text = font.render(f"Balls: {game.balls} Score: {game.score} Time: {game.time}", True, WHITE)
    status_surface.blit(score_text, (10, 10))
    screen.blit(status_surface, (0, current_height - STATUS_BAR_HEIGHT))

# Main Loop
running = True
frame_count = 0
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (INITIAL_WIDTH, INITIAL_HEIGHT)})
picam2.configure(config)
picam2.start()
game.hole_positions = load_calibrated_holes()
splash_screen_active = True
fade_start_time = pygame.time.get_ticks()
fade_duration = 1000

while running:
    frame = picam2.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    current_width, current_height = screen.get_size()
    target_height = current_height - MENU_HEIGHT - STATUS_BAR_HEIGHT
    target_width = int(target_height * (INITIAL_WIDTH / INITIAL_HEIGHT))
    scale_x = target_width / INITIAL_WIDTH
    scale_y = target_height / INITIAL_HEIGHT
    roi = cv2.resize(frame, (target_width, target_height))

    for (x, y, radius, points, _, _) in game.hole_positions:
        scaled_x = int(x * scale_x)
        scaled_y = int(y * scale_y)
        cv2.circle(roi, (scaled_x, scaled_y), int(radius * scale_x), GREEN, 2)
        cv2.putText(roi, str(points), (scaled_x - 20, scaled_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, GREEN, 2)

    ball_positions, points_list, is_red_list = detect_ball_in_hole(roi, game, frame_count, scale_x, scale_y)
    for pos, points, is_red in zip(ball_positions, points_list, is_red_list):
        game.score += points
        game.balls -= 1
        print(f"Ball scored at {pos}, Points: {points} (Red: {is_red})")
        if score_sound and (time.time() - game.last_sound_time) >= SOUND_COOLDOWN:
            score_sound.play()
            game.last_sound_time = time.time()

    frame_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    pygame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
    screen.fill(BLACK)
    playfield_offset_x = (current_width - target_width) // 2
    screen.blit(pygame_surface, (playfield_offset_x, MENU_HEIGHT))
    menu.draw(screen)
    draw_ui()
    about_window.draw(screen)
    settings_window.draw(screen)
    leaderboard_window.draw(screen)

    if splash_screen_active:
        elapsed = pygame.time.get_ticks() - fade_start_time
        if elapsed >= fade_duration:
            splash_screen_active = False
        else:
            splash_copy = splash_image.copy()
            splash_copy.set_alpha(int(255 * (1 - elapsed / fade_duration)))
            splash_copy = pygame.transform.smoothscale(splash_copy, (current_width, current_height))
            screen.blit(splash_copy, (0, 0))

    pygame.display.flip()
    clock.tick(30)  # Restored to 30 FPS

    frame_count += 1
    if frame_count % 30 == 0:
        game.time = time.strftime("%H:%M:%S")

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
        elif event.type == KEYDOWN:
            if event.key == pygame.K_r:
                game.reset()
            elif event.key == pygame.K_c:
                game.hole_positions = calibrate_holes()
            elif about_window.active:
                about_window.handle_input(event)
            elif settings_window.active:
                settings_window.handle_input(event)
            elif leaderboard_window.active:
                leaderboard_window.handle_input(event)
        elif event.type in (MOUSEMOTION, MOUSEBUTTONDOWN):
            menu.handle_mouse_input(event)
            if settings_window.active:
                settings_window.handle_input(event)

    if game.balls <= 0:
        leaderboard_window.save_score("RPI", game.score, time.strftime("%Y-%m-%d"))
        game.reset()

# Cleanup
pygame.mixer.music.stop()
picam2.stop()
picam2.close()
pygame.quit()
sys.exit()