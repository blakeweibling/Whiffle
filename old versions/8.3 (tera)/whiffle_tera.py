import os
import sys
import time
import json
import logging
import pygame
import cv2
import numpy as np
from supabase import create_client, Client
import pygame.surfarray

# Set up logging to show DEBUG messages
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Supabase setup
SUPABASE_URL = "https://jtkbujumrobglftzokcs.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0a2J1anVtcm9iZ2xmdHpva2NzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMTM4NzcsImV4cCI6MjA1NzU4OTg3N30.OibLuqr3X922SUSBL8yGxDw8uwuTjivH97-2wNhJDqs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Pygame initialization
pygame.init()
pygame.mixer.init()
pygame.font.init()
pygame.display.set_caption("Whiffle Playfield")
screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
clock = pygame.time.Clock()

# Constants
SETTINGS = {
    "INITIAL_WIDTH": 1280,
    "INITIAL_HEIGHT": 720,
    "MENU_HEIGHT": 30,
    "STATUS_BAR_HEIGHT": 30,
    "COOLDOWN_FRAMES": 30,
    "CONFIRMATION_FRAMES": 10,
    "SOUND_COOLDOWN": 0.5,
    "CALIBRATION_FILE": "calibration.json"
}

COLORS = {
    "BLACK": (0, 0, 0),
    "WHITE": (255, 255, 255),
    "BLUE": (0, 0, 255),
    "RED": (255, 0, 0),
    "GREEN": (0, 255, 0),
    "YELLOW": (255, 255, 0),
    "GRAY": (200, 200, 200)
}

FONTS = {
    "ui": pygame.font.Font(None, 24),
    "menu": pygame.font.Font(None, 24)
}

cap = None
lower_white = np.array([0, 0, 200], dtype=np.uint8)
upper_white = np.array([180, 30, 255], dtype=np.uint8)
volume = 0.5
pygame.mixer.music.load("background_music.mp3")
pygame.mixer.music.set_volume(volume)
pygame.mixer.music.play(-1)
logger.info("Background music 'background_music.mp3' loaded and playing.")
score_sound = pygame.mixer.Sound("score.wav") if os.path.exists("score.wav") else None
if score_sound:
    score_sound.set_volume(volume)

key_sequence = []
SECRET_CODE = [pygame.K_UP, pygame.K_UP, pygame.K_DOWN, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_b, pygame.K_a]

# Updated splash image loading with fallback and logging
splash_image = pygame.image.load("splash.png") if os.path.exists("splash.png") else pygame.Surface((1280, 720))
if not os.path.exists("splash.png"):
    splash_image.fill(COLORS["RED"])
    logger.warning("splash.png not found. Using red fallback surface.")
else:
    logger.info("splash.png loaded successfully.")
secret_splash_surface = pygame.Surface((400, 200))
secret_splash_surface.fill(COLORS["GRAY"])
secret_splash_text = FONTS["ui"].render("Secret Splash Screen!", True, COLORS["BLACK"])
secret_splash_surface.blit(secret_splash_text, (100, 90))
secret_splash_active = False

class GameState:
    def __init__(self):
        self.mode = "Classic"
        self.score = 0
        self.balls = 10 if self.mode == "Classic" else float("inf")
        self.time = time.strftime("%H:%M:%S")
        self.time_left = 300 if self.mode == "Timed" else None
        self.hole_positions = []
        self.detected_positions = []
        self.confirming_balls = {}
        self.scored_balls = set()
        self.detection_cooldown = {}
        self.last_sound_time = 0
        self.just_reset = False

    def reset(self):
        self.score = 0
        self.balls = 10 if self.mode == "Classic" else float("inf")
        self.time = time.strftime("%H:%M:%S")
        self.time_left = 300 if self.mode == "Timed" else None
        self.detected_positions.clear()
        self.confirming_balls.clear()
        self.scored_balls.clear()
        self.detection_cooldown.clear()
        self.just_reset = True
        logger.info("Game state reset.")

    def set_mode(self, mode):
        self.mode = mode
        self.reset()
        logger.info(f"Game mode set to {mode}")

    def get_nearest_hole(self, ball_pos, scale_x=1.0, scale_y=1.0):
        ball_x, ball_y = ball_pos
        for x, y, radius, points, is_oblong, rect in self.hole_positions:
            scaled_x, scaled_y = int(x * scale_x), int(y * scale_y)
            scaled_radius = int(radius * scale_x)
            distance = np.hypot(ball_x - scaled_x, ball_y - scaled_y)
            if distance <= scaled_radius:
                return (scaled_x, scaled_y, scaled_radius, points, is_oblong, rect)
        return None

class Window:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.active = False
        self.surface = None
        self.font = FONTS["ui"]

    def draw_base(self, screen, title):
        if self.active:
            surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            surface.fill((200, 200, 200, 200))
            title_text = self.font.render(title, True, COLORS["BLACK"])
            surface.blit(title_text, (10, 10))
            screen.blit(surface, (screen.get_width() // 2 - self.width // 2, screen.get_height() // 2 - self.height // 2))

    def handle_base_input(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            logger.info(f"{self.__class__.__name__} closed via ESC key")
            return True
        return False

class Menu:
    def __init__(self):
        self.options = {
            "File": {
                "(C)alibrate": lambda: calibrate_holes(),
                "E(x)it": lambda: sys.exit()
            },
            "Game": {
                "(T)imed": lambda: game.set_mode("Timed"),
                "(C)lassic": lambda: game.set_mode("Classic")
            },
            "Leaderboard": {
                "(L)eaderboard": lambda: self.open_window(leaderboard_window)
            },
            "Settings": {
                "(S)ettings": lambda: self.open_window(settings_window)
            },
            "Help": {
                "(A)bout": lambda: self.open_window(about_window),
                "(T)utorial": lambda: None
            }
        }
        self.selected = None
        self.submenu = None
        self.fullscreen = False

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        pygame.display.set_mode((1280, 720), pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE)
        logger.info(f"Fullscreen toggled to {self.fullscreen}")

    def open_window(self, window):
        for w in [about_window, settings_window, leaderboard_window]:
            if w != window and w.active:
                w.deactivate()
                logger.debug(f"Closed {w.__class__.__name__} before opening {window.__class__.__name__}")
        if window.active:
            window.deactivate()
            logger.debug(f"Deactivated {window.__class__.__name__} via menu")
        else:
            window.activate()
            logger.debug(f"Activated {window.__class__.__name__} via menu")

    def draw(self, screen):
        menu_bar = pygame.Surface((screen.get_width(), SETTINGS["MENU_HEIGHT"]))
        menu_bar.fill(COLORS["GRAY"])
        x_offset = 10
        for option in self.options:
            color = COLORS["BLACK"] if option != self.selected else COLORS["BLUE"]
            text = FONTS["menu"].render(option, True, color)
            menu_bar.blit(text, (x_offset, 5))
            x_offset += text.get_width() + 20
        screen.blit(menu_bar, (0, 0))
        if self.selected and self.options[self.selected]:
            submenu_surface = pygame.Surface((150, len(self.options[self.selected]) * 30 + 10), pygame.SRCALPHA)
            submenu_surface.fill((200, 200, 200, 200))
            keys = list(self.options[self.selected].keys())
            for i, item in enumerate(keys):
                color = COLORS["BLACK"] if item != self.submenu else COLORS["BLUE"]
                text = FONTS["menu"].render(item, True, color)
                submenu_surface.blit(text, (10, 5 + i * 30))
            selected_idx = list(self.options.keys()).index(self.selected)
            x_pos = 10 + sum(FONTS["menu"].render(list(self.options.keys())[i], True, COLORS["BLACK"]).get_width() + 20 for i in range(selected_idx))
            screen.blit(submenu_surface, (x_pos, SETTINGS["MENU_HEIGHT"]))

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            logger.debug(f"Key pressed: {pygame.key.name(event.key)}, selected: {self.selected}, submenu: {self.submenu}")
            if event.key == pygame.K_DOWN:
                if self.selected and self.options[self.selected]:
                    if self.submenu is None:
                        self.submenu = list(self.options[self.selected].keys())[0]
                    else:
                        keys = list(self.options[self.selected].keys())
                        idx = keys.index(self.submenu)
                        self.submenu = keys[idx + 1] if idx < len(keys) - 1 else keys[0]
                    logger.debug(f"Submenu navigation: selected={self.selected}, submenu={self.submenu}")
                return True
            elif event.key == pygame.K_UP:
                if self.selected and self.options[self.selected]:
                    if self.submenu is None:
                        self.submenu = list(self.options[self.selected].keys())[-1]
                    else:
                        keys = list(self.options[self.selected].keys())
                        idx = keys.index(self.submenu)
                        self.submenu = keys[idx - 1] if idx > 0 else keys[-1]
                    logger.debug(f"Submenu navigation: selected={self.selected}, submenu={self.submenu}")
                return True
            elif event.key == pygame.K_RIGHT:
                if self.selected is None:
                    self.selected = list(self.options.keys())[0]
                else:
                    keys = list(self.options.keys())
                    idx = keys.index(self.selected)
                    self.selected = keys[idx + 1] if idx < len(keys) - 1 else keys[0]
                self.submenu = None
                logger.debug(f"Main menu navigation: selected={self.selected}, submenu={self.submenu}")
                pygame.display.flip()
                return True
            elif event.key == pygame.K_LEFT:
                if self.selected is None:
                    self.selected = list(self.options.keys())[-1]
                else:
                    keys = list(self.options.keys())
                    idx = keys.index(self.selected)
                    self.selected = keys[idx - 1] if idx > 0 else keys[-1]
                self.submenu = None
                logger.debug(f"Main menu navigation: selected={self.selected}, submenu={self.submenu}")
                pygame.display.flip()
                return True
            elif event.key == pygame.K_RETURN:
                if self.submenu and self.options[self.selected][self.submenu]:
                    self.options[self.selected][self.submenu]()
                    self.selected = None
                    self.submenu = None
                    logger.debug("Menu deselected after submenu action (RETURN)")
                    pygame.display.flip()
                    return True
                elif self.selected == "File" and "(C)alibrate" in self.options[self.selected]:
                    self.options[self.selected]["(C)alibrate"]()
                    self.selected = None
                    self.submenu = None
                    logger.debug("Menu deselected after calibrate action (RETURN)")
                    pygame.display.flip()
                    return True
            elif event.key == pygame.K_F11:
                self.toggle_fullscreen()
                return True
            elif event.key == pygame.K_c and self.selected == "File":
                self.options[self.selected]["(C)alibrate"]()
                self.selected = None
                self.submenu = None
                logger.debug("Menu deselected after 'c' key action")
                pygame.display.flip()
                return True
            elif event.key == pygame.K_a and self.selected == "Help":
                self.options[self.selected]["(A)bout"]()
                self.selected = None
                self.submenu = None
                logger.debug("Menu deselected after 'a' key action")
                pygame.display.flip()
                return True
            elif event.key == pygame.K_t and self.selected == "Help":
                self.options[self.selected]["(T)utorial"]()
                self.selected = None
                self.submenu = None
                logger.debug("Menu deselected after 't' key action")
                pygame.display.flip()
                return True
            elif event.key == pygame.K_l and self.selected == "Leaderboard":
                self.options[self.selected]["(L)eaderboard"]()
                self.selected = None
                self.submenu = None
                logger.debug("Menu deselected after 'l' key action")
                pygame.display.flip()
                return True
            elif event.key == pygame.K_s and self.selected == "Settings":
                self.options[self.selected]["(S)ettings"]()
                self.selected = None
                self.submenu = None
                logger.debug("Menu deselected after 's' key action")
                pygame.display.flip()
                return True
        return False

    def handle_mouse_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_x, mouse_y = event.pos
            if mouse_y <= SETTINGS["MENU_HEIGHT"]:
                x_offset = 10
                for option in self.options:
                    text = FONTS["menu"].render(option, True, COLORS["BLACK"])
                    if x_offset <= mouse_x <= x_offset + text.get_width():
                        self.selected = option
                        self.submenu = None
                        logger.debug(f"Mouse selected menu: {self.selected}")
                        return True
                    x_offset += text.get_width() + 20
            if self.selected and mouse_y > SETTINGS["MENU_HEIGHT"]:
                selected_idx = list(self.options.keys()).index(self.selected)
                x_pos = 10 + sum(FONTS["menu"].render(list(self.options.keys())[i], True, COLORS["BLACK"]).get_width() + 20 for i in range(selected_idx))
                submenu_width = 150
                submenu_height = len(self.options[self.selected]) * 30 + 10
                if x_pos <= mouse_x <= x_pos + submenu_width and SETTINGS["MENU_HEIGHT"] <= mouse_y <= SETTINGS["MENU_HEIGHT"] + submenu_height:
                    idx = int((mouse_y - SETTINGS["MENU_HEIGHT"]) // 30)
                    keys = list(self.options[self.selected].keys())
                    if 0 <= idx < len(keys):
                        self.submenu = keys[idx]
                        self.options[self.selected][self.submenu]()
                        self.selected = None
                        self.submenu = None
                        logger.debug("Mouse activated submenu action")
                        pygame.display.flip()
                        return True
        return False

# End of Block 1
class AboutWindow(Window):
    def __init__(self):
        super().__init__(600, 400)
        self.text = [
            "In 1931, Automatic Industries introduced the 'Whiffle Board,' a pinball machine",
            # ... (rest of the text unchanged)
        ]
        self.font = pygame.font.Font(None, 20)
        self.scroll_y = 0
        self.max_scroll = max(0, (len(self.text) * 20) - (self.height - 40))
        logger.info(f"AboutWindow initialized with {len(self.text)} lines of text, max_scroll: {self.max_scroll}")

    def activate(self):
        self.active = True
        logger.info("AboutWindow activated")

    def deactivate(self):
        self.active = False
        logger.info("AboutWindow deactivated")

    def draw(self, screen):
        # ... (unchanged)
        pass

    def handle_input(self, event):
        # ... (unchanged)
        pass

class SettingsWindow(Window):
    def __init__(self):
        super().__init__(400, 400)
        self.slider_values = {
            "lower_h": lower_white[0], "lower_s": lower_white[1], "lower_v": lower_white[2],
            "upper_h": upper_white[0], "upper_s": upper_white[1], "upper_v": upper_white[2],
            "volume": volume * 100
        }
        self.slider_positions = {}
        self.dragging_slider = None
        self.label_to_key = {
            "HSV Lower (H)": "lower_h", "HSV Lower (S)": "lower_s", "HSV Lower (V)": "lower_v",
            "HSV Upper (H)": "upper_h", "HSV Upper (S)": "upper_s", "HSV Upper (V)": "upper_v",
            "Volume": "volume"
        }
        self.font = pygame.font.Font(None, 20)
        logger.info(f"SettingsWindow initialized with slider_values: {self.slider_values}")

    def activate(self):
        self.active = True
        logger.info("SettingsWindow activated")

    def deactivate(self):
        self.active = False
        logger.info("SettingsWindow deactivated")

    def draw(self, screen):
        # ... (unchanged)
        pass

    def handle_input(self, event):
        # ... (unchanged)
        pass

class LeaderboardWindow(Window):
    def __init__(self):
        super().__init__(400, 300)
        self.scores = []
        self.view = "All-Time"
        self.font = pygame.font.Font(None, 20)
        self.load_scores()
        logger.info(f"LeaderboardWindow initialized with scores: {self.scores}")

    def activate(self):
        self.active = True
        logger.info("LeaderboardWindow activated")

    def deactivate(self):
        self.active = False
        logger.info("LeaderboardWindow deactivated")

    def load_scores(self):
        # ... (unchanged)
        pass

    def save_score(self, initials, score, date, mode="Classic"):
        # ... (unchanged)
        pass

    def clear_leaderboard(self):
        # ... (unchanged)
        pass

    def toggle_view(self):
        # ... (unchanged)
        pass

    def draw(self, screen):
        # ... (unchanged)
        pass

    def handle_input(self, event):
        # ... (unchanged)
        pass

about_window = AboutWindow()
settings_window = SettingsWindow()
leaderboard_window = LeaderboardWindow()

def reinitialize_camera():
    global cap
    if cap is not None and cap.isOpened():
        cap.release()
    time.sleep(1)
    backends = [cv2.CAP_MSMF, cv2.CAP_VFW, cv2.CAP_DSHOW, cv2.CAP_FFMPEG, cv2.CAP_ANY]
    indices = [0, 1]
    for backend in backends:
        for index in indices:
            logger.info(f"Trying backend {backend} and index {index}...")
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, SETTINGS["INITIAL_WIDTH"])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, SETTINGS["INITIAL_HEIGHT"])
                time.sleep(0.2)
                ret, frame = cap.read()
                if ret and frame is not None and frame.size != 0 and frame.shape == (SETTINGS["INITIAL_HEIGHT"], SETTINGS["INITIAL_WIDTH"], 3):
                    logger.info(f"Success with backend {backend} and index {index}. Shape: {frame.shape}")
                    return True
                cap.release()
    logger.error("Could not open video capture.")
    return False

def load_calibrated_holes():
    if os.path.exists(SETTINGS["CALIBRATION_FILE"]):
        with open(SETTINGS["CALIBRATION_FILE"], 'r') as f:
            try:
                data = json.load(f)
                logger.info("Loaded calibration data.")
                return [tuple(hole) if len(hole) > 4 else (hole[0], hole[1], hole[2], hole[3], False, None) for hole in data["holes"]]
            except Exception as e:
                logger.error(f"Error loading calibration: {e}")
    logger.info("No calibration file. Entering calibration mode.")
    return calibrate_holes()

def save_calibrated_holes(holes):
    with open(SETTINGS["CALIBRATION_FILE"], 'w') as f:
        json.dump({"holes": holes}, f)
        logger.info("Calibration saved.")

def calibrate_holes():
    # ... (unchanged for brevity)
    pass

# End of Block 2
def detect_ball_in_hole(image, hole_coords, game_state, frame_count, scale_x=1.0, scale_y=1.0):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    lower_red1 = np.array([0, 5, 30])
    upper_red1 = np.array([40, 255, 255])
    lower_red2 = np.array([140, 5, 30])
    upper_red2 = np.array([180, 255, 255])
    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    kernel = np.ones((5, 5), np.uint8)
    mask_white = cv2.dilate(cv2.erode(mask_white, kernel, iterations=1), kernel, iterations=1)
    mask_red = cv2.dilate(cv2.erode(mask_red, kernel, iterations=1), kernel, iterations=1)
    ball_positions, points_list, is_red_list = [], [], []  # Initialize as empty lists
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detected_balls = set()

    for contour in contours:
        area = cv2.contourArea(contour)
        min_area = 0.05 * np.pi * 20 * 20 * (scale_x * scale_y)
        if not (min_area < area < np.pi * 20 * 20 * (scale_x * scale_y)):
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        M = cv2.moments(contour)
        if M["m00"] == 0:
            continue
        ball_x = int(M["m10"] / M["m00"])
        ball_y = int(M["m01"] / M["m00"])
        ball_pos = (ball_x, ball_y)
        ball_id = f"{round(ball_x / 10) * 10},{round(ball_y / 10) * 10}"
        ball_y = max(2, min(ball_y, image.shape[0] - 3))
        ball_x = max(2, min(ball_x, image.shape[1] - 3))
        nearest_hole = game_state.get_nearest_hole(ball_pos, scale_x, scale_y)
        if nearest_hole:
            x, y, radius, points, is_oblong, rect = nearest_hole
            hole_pos = (x, y)
            if hole_pos in game_state.scored_balls:
                logger.debug(f"Hole {hole_pos} already scored, skipping detection for ball_id {ball_id}")
                continue
            if hole_pos in game_state.detection_cooldown:
                cooldown_remaining = SETTINGS["COOLDOWN_FRAMES"] - (frame_count - game_state.detection_cooldown[hole_pos])
                if cooldown_remaining > 0:
                    logger.debug(f"Hole {hole_pos} on cooldown for {cooldown_remaining} more frames, skipping detection for ball_id {ball_id}")
                    continue
            if ball_id in game_state.confirming_balls:
                current_data = game_state.confirming_balls[ball_id]
                current_pos = current_data["position"]
                frames = current_data["frames"]
                dist = np.hypot(ball_x - current_pos[0], ball_y - current_pos[1])
                if dist < 10:
                    game_state.confirming_balls[ball_id]["frames"] += 1
                    game_state.confirming_balls[ball_id]["position"] = (ball_x, ball_y)
                    game_state.confirming_balls[ball_id]["hole_pos"] = hole_pos
                    if frames + 1 >= SETTINGS["CONFIRMATION_FRAMES"]:
                        region = image[max(0, ball_y-10):min(image.shape[0], ball_y+10), max(0, ball_x-10):min(image.shape[1], ball_x+10)]
                        hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
                        red_mask_region = cv2.inRange(hsv_region, lower_red1, upper_red1) | cv2.inRange(hsv_region, lower_red2, upper_red2)
                        red_pixel_count = cv2.countNonZero(red_mask_region)
                        total_pixels = region.shape[0] * region.shape[1]
                        red_ratio = red_pixel_count / total_pixels if total_pixels > 0 else 0
                        logger.debug(f"Red detection: {red_pixel_count}/{total_pixels} pixels ({red_ratio:.2%})")
                        is_red = red_ratio > 0.2
                        final_points = points * 2 if is_red else points
                        if is_oblong and rect and rect[0] <= ball_x <= rect[2] and rect[1] <= ball_y <= rect[3]:
                            ball_positions.append(hole_pos)
                            points_list.append(final_points)
                            is_red_list.append(is_red)
                            game_state.scored_balls.add(hole_pos)
                            game_state.detection_cooldown[hole_pos] = frame_count
                            logger.info(f"Confirmed ball at {hole_pos}, Points: {final_points} (Oblong, Red: {is_red})")
                        elif circularity > 0.7:
                            ball_positions.append(hole_pos)
                            points_list.append(final_points)
                            is_red_list.append(is_red)
                            game_state.scored_balls.add(hole_pos)
                            game_state.detection_cooldown[hole_pos] = frame_count
                            logger.info(f"Confirmed ball at {hole_pos}, Points: {final_points} (Circular, Red: {is_red})")
                        del game_state.confirming_balls[ball_id]
                        if hole_pos in game_state.detected_positions:
                            game_state.detected_positions.remove(hole_pos)
                else:
                    game_state.confirming_balls[ball_id] = {"position": (ball_x, ball_y), "frames": 1, "hole_pos": hole_pos}
            else:
                game_state.confirming_balls[ball_id] = {"position": (ball_x, ball_y), "frames": 1, "hole_pos": hole_pos}
            if hole_pos not in game_state.detected_positions:
                game_state.detected_positions.append(hole_pos)
            detected_balls.add(ball_id)
        elif ball_id in game_state.confirming_balls:
            hole_pos = game_state.confirming_balls[ball_id]["hole_pos"]
            del game_state.confirming_balls[ball_id]
            if hole_pos in game_state.detected_positions:
                game_state.detected_positions.remove(hole_pos)
    for ball_id in list(game_state.confirming_balls.keys()):
        if ball_id not in detected_balls:
            hole_pos = game_state.confirming_balls[ball_id]["hole_pos"]
            logger.debug(f"Ball {ball_id} no longer detected at {hole_pos}, removing from confirming_balls")
            del game_state.confirming_balls[ball_id]
            if hole_pos in game_state.detected_positions:
                game_state.detected_positions.remove(hole_pos)
    return ball_positions, points_list, is_red_list

def draw_ui():
    status_bar = pygame.Surface((screen.get_width(), SETTINGS["STATUS_BAR_HEIGHT"]))
    status_bar.fill(COLORS["GRAY"])
    score_text = FONTS["ui"].render(f"Score: {game.score}", True, COLORS["BLACK"])
    balls_text = FONTS["ui"].render(f"Balls: {game.balls}" if game.mode == "Classic" else game.time, True, COLORS["BLACK"])
    status_bar.blit(score_text, (10, 5))
    status_bar.blit(balls_text, (screen.get_width() - balls_text.get_width() - 10, 5))
    screen.blit(status_bar, (0, screen.get_height() - SETTINGS["STATUS_BAR_HEIGHT"]))

def get_initials(screen, font):
    initials = ""
    input_active = True
    input_surface = pygame.Surface((200, 100), pygame.SRCALPHA)
    while input_active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and len(initials) > 0:
                    input_active = False
                elif event.key == pygame.K_BACKSPACE:
                    initials = initials[:-1]
                elif event.key in range(65, 91) or event.key in range(97, 123):
                    if len(initials) < 3:
                        initials += chr(event.key).upper()
        input_surface.fill((200, 200, 200, 200))
        text = font.render("Enter Initials: " + initials, True, COLORS["BLACK"])
        input_surface.blit(text, (10, 40))
        screen.blit(input_surface, (screen.get_width() // 2 - 100, screen.get_height() // 2 - 50))
        pygame.display.flip()
        clock.tick(30)
    return initials if initials else "AAA"

def open_window_exclusive(window):
    for w in [about_window, settings_window, leaderboard_window]:
        if w != window and w.active:
            w.deactivate()
            logger.debug(f"Closed {w.__class__.__name__} before opening {window.__class__.__name__}")
    if window.active:
        window.deactivate()
        logger.debug(f"Deactivated {window.__class__.__name__}")
    else:
        window.activate()
        logger.debug(f"Activated {window.__class__.__name__}")

def close_all_windows():
    for w in [about_window, settings_window, leaderboard_window]:
        if w.active:
            w.deactivate()
            logger.debug(f"Deactivated {w.__class__.__name__} via close_all_windows")

# Variable declarations
running = True
frame_count = 0
retry_count = 0
max_retries = 10
focus_lost = False
splash_screen_active = True
splash_alpha = 255
fade_duration = 5000  # Extended for testing; revert to 1000 once confirmed
FRAME_SKIP = 2
frame_skip_counter = 0
game = GameState()
menu = Menu()

logger.info("Initializing camera...")
if not reinitialize_camera():
    logger.error("Failed to initialize camera. Exiting...")
    sys.exit()

logger.info("Loading calibrated holes...")
game.hole_positions = load_calibrated_holes()

logger.info("Forcing camera reinitialization before game loop...")
if not reinitialize_camera():
    logger.error("Failed to reinitialize camera. Exiting...")
    sys.exit()

while running:
    if frame_count == 0:
        fade_start_time = pygame.time.get_ticks()
        logger.info("Splash screen fade started.")
    try:
        if focus_lost:
            pygame.display.set_caption("Whiffle Playfield - Click to Focus")
            for event in pygame.event.get():
                if event.type == pygame.ACTIVEEVENT and event.gain == 1:
                    focus_lost = False
                    pygame.display.set_caption("Whiffle Playfield")
                    logger.debug("Focus regained.")
                continue
        if not cap.isOpened():
            logger.warning("Camera not open. Reinitializing...")
            if not reinitialize_camera():
                logger.error("Failed to reinitialize camera. Exiting...")
                break
        ret, frame = cap.read()
        if not ret:
            logger.warning(f"Failed to capture frame. Retry {retry_count + 1}/{max_retries}")
            retry_count += 1
            if retry_count >= max_retries:
                logger.error("Max retries reached. Reinitializing camera...")
                if not reinitialize_camera():
                    logger.error("Failed to reinitialize camera. Exiting...")
                    break
            time.sleep(0.1)
            continue
        retry_count = 0
        if frame is None or frame.size == 0 or frame.shape != (SETTINGS["INITIAL_HEIGHT"], SETTINGS["INITIAL_WIDTH"], 3):
            logger.warning(f"Invalid frame: Shape: {frame.shape if frame is not None else 'None'}")
            frame = np.zeros((SETTINGS["INITIAL_HEIGHT"], SETTINGS["INITIAL_WIDTH"], 3), dtype=np.uint8)
        current_width, current_height = screen.get_size()
        aspect_ratio = SETTINGS["INITIAL_WIDTH"] / SETTINGS["INITIAL_HEIGHT"]
        target_height = current_height - SETTINGS["MENU_HEIGHT"] - SETTINGS["STATUS_BAR_HEIGHT"]
        target_width = int(target_height * aspect_ratio)
        if target_width > current_width:
            target_width = current_width
            target_height = int(target_width / aspect_ratio)
        scale_x = target_width / SETTINGS["INITIAL_WIDTH"]
        scale_y = target_height / SETTINGS["INITIAL_HEIGHT"]
        scaled_frame = cv2.resize(frame, (target_width, target_height))
        roi = scaled_frame
        for (x, y, radius, points, is_oblong, rect) in game.hole_positions:
            scaled_x, scaled_y = int(x * scale_x), int(y * scale_y)
            scaled_radius = int(radius * scale_x)
            cv2.circle(roi, (scaled_x, scaled_y), scaled_radius, COLORS["GREEN"], 2)
            cv2.putText(roi, str(points), (scaled_x - 20, scaled_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["GREEN"], 2)
            if is_oblong and rect:
                scaled_rect = (int(rect[0] * scale_x), int(rect[1] * scale_y), int(rect[2] * scale_x), int(rect[3] * scale_y))
                cv2.rectangle(roi, scaled_rect[:2], scaled_rect[2:], COLORS["GREEN"], 2)
        frame_skip_counter += 1
        if game.just_reset:
            game.just_reset = False
            game.detected_positions.clear()
            game.confirming_balls.clear()
        elif frame_skip_counter >= FRAME_SKIP and not game.confirming_balls:
            frame_skip_counter = 0
        else:
            frame_skip_counter = 0
            ball_positions, points_list, is_red_list = detect_ball_in_hole(roi, game.hole_positions, game, frame_count, scale_x, scale_y)
            for pos, points, is_red in zip(ball_positions, points_list, is_red_list):
                game.score += points
                if game.mode == "Classic":
                    game.balls -= 1
                logger.info(f"Ball scored at {pos}, Points: {points} (Red: {is_red}), Score: {game.score}, Balls: {game.balls}")
                current_time = time.time()
                if score_sound and (current_time - game.last_sound_time) >= SETTINGS["SOUND_COOLDOWN"]:
                    score_sound.play()
                    game.last_sound_time = current_time
        frame_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        pygame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
        scaled_surface = pygame.transform.scale(pygame_surface, (target_width, target_height))
        screen.fill(COLORS["BLACK"])
        playfield_offset_x = (current_width - target_width) // 2
        playfield_offset_y = SETTINGS["MENU_HEIGHT"]
        screen.blit(scaled_surface, (playfield_offset_x, playfield_offset_y))
        menu.draw(screen)
        draw_ui()
        for pos in game.detected_positions:
            adjusted_pos = (pos[0] + playfield_offset_x, pos[1] + playfield_offset_y)
            confirming = any(pos == game.confirming_balls[ball_id]["hole_pos"] for ball_id in game.confirming_balls if game.confirming_balls[ball_id]["frames"] < SETTINGS["CONFIRMATION_FRAMES"])
            pygame.draw.circle(screen, COLORS["YELLOW"] if confirming else COLORS["BLUE"] if cv2.mean(roi[max(0, int(pos[1]/scale_y)-2):min(roi.shape[0], int(pos[1]/scale_y)+3), max(0, int(pos[0]/scale_x)-2):min(roi.shape[1], int(pos[0]/scale_x)+3)])[2] > 100 else COLORS["RED"], adjusted_pos, int(20 * scale_x), 2)
        for (x, y, _, _, is_oblong, rect) in game.hole_positions:
            scaled_x = int(x * scale_x) + playfield_offset_x
            scaled_y = int(y * scale_y) + playfield_offset_y
            hole_pos = (int(x * scale_x), int(y * scale_y))
            if is_oblong and rect and hole_pos in game.scored_balls:
                scaled_rect = (int(rect[0] * scale_x) + playfield_offset_x, int(rect[1] * scale_y) + playfield_offset_y, int(rect[2] * scale_x) + playfield_offset_x, int(rect[3] * scale_y) + playfield_offset_y)
                pygame.draw.rect(screen, COLORS["RED"], (scaled_rect[0], scaled_rect[1], scaled_rect[2] - scaled_rect[0], scaled_rect[3] - scaled_rect[1]), 2)
        about_window.draw(screen)
        settings_window.draw(screen)
        leaderboard_window.draw(screen)
        if splash_screen_active:
            elapsed = pygame.time.get_ticks() - fade_start_time
            logger.debug(f"Splash screen active, elapsed: {elapsed}ms, alpha: {splash_alpha}")
            if elapsed >= fade_duration:
                splash_alpha = 0
                splash_screen_active = False
                logger.info("Splash screen faded out.")
            else:
                t = elapsed / fade_duration
                splash_alpha = 255 * (1 - t**2)
            splash_copy = splash_image.copy()
            splash_copy.set_alpha(int(splash_alpha))
            splash_copy = pygame.transform.smoothscale(splash_copy, (current_width, current_height))
            screen.blit(splash_copy, (0, 0))
        if secret_splash_active:
            screen.blit(secret_splash_surface, (current_width // 2 - 200, current_height // 2 - 100))
        pygame.display.flip()
        logger.debug("Screen redrawn in main loop")
        clock.tick(30)
        frame_count += 1
        if frame_count % 30 == 0:
            if game.mode == "Timed":
                game.time_left = max(0, game.time_left - 1)
                minutes, seconds = game.time_left // 60, game.time_left % 60
                game.time = f"{minutes}:{seconds:02d}"
                if game.time_left <= 0:
                    logger.info("Time's up! Saving score...")
                    initials = get_initials(screen, FONTS["ui"])
                    if initials:
                        leaderboard_window.save_score(initials, game.score, time.strftime("%Y-%m-%dT%H:%M:%S"), mode="Timed")
                        leaderboard_window.load_scores()
                    game.reset()
            else:
                game.time = time.strftime("%H:%M:%S")
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.ACTIVEEVENT:
                if event.gain == 0 and event.state == 2:
                    focus_lost = True
                    logger.info("Focus lost. Click to regain focus.")
            elif event.type == pygame.KEYDOWN:
                if secret_splash_active:
                    continue
                if about_window.active:
                    about_window.handle_input(event)
                elif settings_window.active:
                    settings_window.handle_input(event)
                elif leaderboard_window.active:
                    leaderboard_window.handle_input(event)
                else:
                    key_sequence.append(event.key)
                    if len(key_sequence) > len(SECRET_CODE):
                        key_sequence.pop(0)
                    if key_sequence == SECRET_CODE:
                        logger.info("Secret code entered! Showing splash screen.")
                        secret_splash_active = True
                        key_sequence.clear()
                    menu.handle_input(event)
                    if event.key == pygame.K_l:
                        open_window_exclusive(leaderboard_window)
                        pygame.display.flip()
                    elif event.key == pygame.K_a:
                        open_window_exclusive(about_window)
                        pygame.display.flip()
                    elif event.key == pygame.K_s:
                        open_window_exclusive(settings_window)
                        pygame.display.flip()
                    elif event.key == pygame.K_ESCAPE:
                        close_all_windows()
                        pygame.display.flip()
            elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
                if secret_splash_active and event.type == pygame.MOUSEBUTTONDOWN:
                    secret_splash_active = False
                    continue
                handled = menu.handle_mouse_input(event)
                if not handled:
                    if about_window.active:
                        about_window.handle_input(event)
                    elif settings_window.active:
                        settings_window.handle_input(event)
                    elif leaderboard_window.active:
                        leaderboard_window.handle_input(event)
        if game.mode == "Classic" and game.balls <= 0:
            logger.info("Saving score to leaderboard...")
            initials = get_initials(screen, FONTS["ui"])
            if initials:
                leaderboard_window.save_score(initials, game.score, time.strftime("%Y-%m-%dT%H:%M:%S"), mode="Classic")
                leaderboard_window.load_scores()
            game.reset()
    except cv2.error as e:
        logger.error(f"OpenCV error: {e}")
        if not reinitialize_camera():
            logger.error("Failed to reinitialize camera. Exiting...")
            break
    except pygame.error as e:
        logger.error(f"Pygame error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        break

pygame.mixer.music.stop()
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()

# End of Block 3