import cv2
import numpy as np
import pygame
import sys
from pygame.locals import *
import time
import json
import os
import random
from supabase import create_client, Client
import logging
from config import COLORS, SETTINGS, FONT_SIZES, SUPABASE

DEBUG = False
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

pygame.init()
screen = pygame.display.set_mode((SETTINGS["INITIAL_WIDTH"], SETTINGS["INITIAL_HEIGHT"]), pygame.RESIZABLE)
pygame.display.set_caption("Whiffle Playfield")
supabase: Client = create_client(SUPABASE["URL"], SUPABASE["KEY"])

FONTS = {
    "menu": pygame.font.Font(None, FONT_SIZES["MENU"]),
    "ui": pygame.font.Font(None, FONT_SIZES["UI"]),
    "window": pygame.font.Font(None, FONT_SIZES["WINDOW"]),
}

try:
    splash_image = pygame.image.load(SETTINGS["SPLASH_IMAGE_FILE"]).convert_alpha()
    splash_image = pygame.transform.smoothscale(splash_image, (SETTINGS["INITIAL_WIDTH"], SETTINGS["INITIAL_HEIGHT"]))
except FileNotFoundError:
    logger.warning(f"Splash screen image '{SETTINGS['SPLASH_IMAGE_FILE']}' not found. Using blank splash.")
    splash_image = pygame.Surface((SETTINGS["INITIAL_WIDTH"], SETTINGS["INITIAL_HEIGHT"]), pygame.SRCALPHA)
    splash_image.fill(COLORS["DARK_GRAY"])

screen.blit(splash_image, (0, 0))
pygame.display.flip()

pygame.mixer.init()
clock = pygame.time.Clock()
try:
    pygame.mixer.music.load(SETTINGS["BACKGROUND_MUSIC_FILE"])
    pygame.mixer.music.set_volume(0.5)
    pygame.mixer.music.play(-1)
    logger.info(f"Background music '{SETTINGS['BACKGROUND_MUSIC_FILE']}' loaded and playing.")
except FileNotFoundError:
    logger.warning(f"Background music file '{SETTINGS['BACKGROUND_MUSIC_FILE']}' not found.")
except Exception as e:
    logger.error(f"Error loading background music: {e}")

try:
    score_sound = pygame.mixer.Sound(SETTINGS["SCORE_SOUND_FILE"])
except FileNotFoundError:
    logger.warning(f"Score sound file '{SETTINGS['SCORE_SOUND_FILE']}' not found.")
    score_sound = None

lower_white = np.array([0, 0, 200])
upper_white = np.array([180, 30, 255])
lower_red = np.array([0, 100, 100])
upper_red = np.array([10, 255, 255])
volume = 0.5
pygame.mixer.music.set_volume(volume)

class GameState:
    def __init__(self):
        self.score = 0
        self.balls = 10
        self.power_up = None
        self.power_up_duration = 0
        self.time = "N/A"
        self.hole_positions = []
        self.running = True
        self.show_leaderboard = False
        self.scored_balls = set()
        self.detection_cooldown = {}
        self.detected_positions = []
        self.confirming_balls = {}
        self.just_reset = False
        self.last_sound_time = 0
        self.mode = "Classic"
        self.time_left = 60

    def reset(self):
        self.score = 0
        self.balls = 10 if self.mode == "Classic" else float('inf')
        self.power_up = None
        self.power_up_duration = 0
        self.time = "N/A" if self.mode == "Classic" else "1:00"
        self.time_left = 60 if self.mode == "Timed" else 0
        self.scored_balls.clear()
        self.detection_cooldown.clear()
        self.detected_positions.clear()
        self.confirming_balls.clear()
        self.just_reset = True
        logger.info(f"Game reset: Mode = {self.mode}, Score = 0, Balls = {self.balls}, Power-Up = None")

    def activate_power_up(self, power_up_name):
        if power_up_name == "Extra Ball":
            self.balls += 1
            self.power_up = "Extra Ball (Active)"
            self.power_up_duration = 60
            logger.info("Power-Up: Extra Ball activated!")
        elif power_up_name == "Double Points":
            self.power_up = "Double Points"
            self.power_up_duration = 900
            logger.info("Power-Up: Double Points activated for 30 seconds!")

    def update_power_up(self):
        if self.power_up_duration > 0:
            self.power_up_duration -= 1
            if self.power_up_duration <= 0:
                self.power_up = None
                logger.info("Power-Up expired.")
        elif self.power_up == "Extra Ball (Active)":
            self.power_up = None

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
particles = []

class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.size = random.randint(3, 6)
        self.life = random.randint(20, 40)
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-3, 1)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        self.size = max(1, self.size - 0.2)

    def draw(self, screen, offset_x, offset_y):
        if self.life > 0:
            pygame.draw.circle(screen, self.color, (int(self.x + offset_x), int(self.y + offset_y)), int(self.size))

class Window:
    def __init__(self, width, height):
        self.active = False
        self.font = FONTS["window"]
        self.width = width
        self.height = height
        self.surface = None
        self.close_button_rect = None

    def draw_base(self, screen, title):
        if not self.active:
            return
        if self.surface is None:
            self.surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.close_button_rect = pygame.Rect(self.width - 40, 10, 30, 30)
        self.surface.fill((200, 200, 200, 200))
        pygame.draw.rect(self.surface, COLORS["RED"], self.close_button_rect)
        if title:
            title_text = self.font.render(title, True, COLORS["BLACK"])
            self.surface.blit(title_text, (10, 10))
        screen.blit(self.surface, (screen.get_width() // 2 - self.width // 2, screen.get_height() // 2 - self.height // 2))

    def handle_base_input(self, event):
        if not self.active:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            window_x = (screen.get_width() - self.width) // 2
            window_y = (screen.get_height() - self.height) // 2
            local_x = mouse_pos[0] - window_x
            local_y = mouse_pos[1] - window_y
            if self.close_button_rect.collidepoint(local_x, local_y):
                self.active = False
                return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            return True
        return False

    def activate(self):
        self.active = True

class Menu:
    def __init__(self):
        self.active = True
        self.options = {
            "File": {
                "(C)alibrate": lambda: calibrate_holes(),
                "Start New Game": lambda: game.reset(),
            },
            "Settings": {
                "Adjust Settings": lambda: settings_window.activate(),
                "Toggle Mode (Classic/Timed)": lambda: self.toggle_mode(),
            },
            "View": {
                "Toggle Fullscreen": lambda: self.toggle_fullscreen(),
            },
            "Help": {
                "(A)bout": lambda: about_window.activate(),
                "(T)utorial": lambda: self.show_tutorial(),
            },
            "Leaderboard": {
                "(L)eaderboard": lambda: leaderboard_window.activate(),
                "Clear Leaderboard": lambda: leaderboard_window.clear_leaderboard(),
                "Toggle View (All/Daily)": lambda: leaderboard_window.toggle_view(),
            }
        }
        self.font = FONTS["menu"]
        self.selected = None
        self.submenu = None
        self.surface = pygame.Surface((SETTINGS["INITIAL_WIDTH"], SETTINGS["MENU_HEIGHT"]), pygame.SRCALPHA)
        self.main_rects = {}
        self.sub_rects = {}
        self.hovered_main = None
        self.hovered_sub = None
        self.fullscreen = False
        self.button_height = 40
        self.button_padding = 10

    def show_tutorial(self):
        logger.info("Showing tutorial...")
        pygame.display.set_caption("Tutorial - Whiffle Playfield")
        time.sleep(2)
        pygame.display.set_caption("Whiffle Playfield")

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        global screen
        if self.fullscreen:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            screen = pygame.display.set_mode((SETTINGS["INITIAL_WIDTH"], SETTINGS["INITIAL_HEIGHT"]), pygame.RESIZABLE)
        return True

    def toggle_mode(self):
        game.mode = "Timed" if game.mode == "Classic" else "Classic"
        game.reset()
        logger.info(f"Switched to {game.mode} Mode")

    def draw(self, screen):
        current_width, current_height = screen.get_size()
        max_submenu_items = max(len(sub_options) for sub_options in self.options.values())
        total_height = SETTINGS["MENU_HEIGHT"] + max_submenu_items * (self.button_height + self.button_padding)
        if self.surface.get_size() != (current_width, total_height):
            self.surface = pygame.Surface((current_width, total_height), pygame.SRCALPHA)
        self.surface.fill((0, 0, 0, 0))
        pygame.draw.rect(self.surface, COLORS["DARK_GRAY"], (0, 0, current_width, SETTINGS["MENU_HEIGHT"]))
        pygame.draw.line(self.surface, COLORS["LIGHT_GRAY"], (0, SETTINGS["MENU_HEIGHT"] - 1), (current_width, SETTINGS["MENU_HEIGHT"] - 1), 2)
        self.main_rects.clear()
        self.sub_rects.clear()
        x_offset = self.button_padding
        y_offset = (SETTINGS["MENU_HEIGHT"] - self.button_height) // 2
        for main_option, sub_options in self.options.items():
            text_surface = self.font.render(main_option, True, COLORS["WHITE"])
            button_width = max(120, text_surface.get_width() + 20)
            if main_option == "Leaderboard":
                button_width += 20
            button_rect = pygame.Rect(x_offset, y_offset, button_width, self.button_height)
            color = COLORS["YELLOW"] if main_option == self.hovered_main or main_option == self.selected else COLORS["WHITE"]
            pygame.draw.rect(self.surface, COLORS["LIGHT_GRAY"], button_rect)
            pygame.draw.rect(self.surface, COLORS["BUTTON_BORDER"], button_rect, 2)
            text_rect = text_surface.get_rect(center=button_rect.center)
            self.surface.blit(text_surface, text_rect)
            self.main_rects[main_option] = button_rect
            x_offset += button_width + self.button_padding
            if self.selected == main_option and sub_options:
                submenu_x = button_rect.left
                submenu_y = SETTINGS["MENU_HEIGHT"]
                submenu_width = max(200, button_rect.width + 20)
                submenu_height = len(sub_options) * (self.button_height + self.button_padding)
                pygame.draw.rect(self.surface, COLORS["SUBMENU_BG"], (submenu_x, submenu_y, submenu_width, submenu_height))
                sub_y = submenu_y
                for sub_option in sub_options:
                    sub_text_surface = self.font.render(sub_option, True, COLORS["WHITE"])
                    sub_button_width = max(200, sub_text_surface.get_width() + 20)
                    sub_button_rect = pygame.Rect(submenu_x, sub_y, sub_button_width, self.button_height)
                    color = COLORS["YELLOW"] if sub_option == self.hovered_sub else COLORS["WHITE"]
                    pygame.draw.rect(self.surface, COLORS["LIGHT_GRAY"], sub_button_rect)
                    sub_text_rect = sub_text_surface.get_rect(center=sub_button_rect.center)
                    self.surface.blit(sub_text_surface, sub_text_rect)
                    self.sub_rects[sub_option] = sub_button_rect
                    logger.debug(f"Drawing submenu: {sub_option} at {sub_button_rect}")
                    sub_y += self.button_height + self.button_padding
        screen.blit(self.surface, (0, 0))

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                if self.selected and self.options[self.selected]:
                    if self.submenu is None:
                        self.submenu = list(self.options[self.selected].keys())[0]
                    else:
                        keys = list(self.options[self.selected].keys())
                        idx = keys.index(self.submenu)
                        self.submenu = keys[idx + 1] if idx < len(keys) - 1 else keys[0]
                return True
            elif event.key == pygame.K_UP:
                if self.selected and self.options[self.selected]:
                    if self.submenu is None:
                        self.submenu = list(self.options[self.selected].keys())[-1]
                    else:
                        keys = list(self.options[self.selected].keys())
                        idx = keys.index(self.submenu)
                        self.submenu = keys[idx - 1] if idx > 0 else keys[-1]
                return True
            elif event.key == pygame.K_RIGHT:
                if self.selected is None:
                    self.selected = list(self.options.keys())[0]
                else:
                    keys = list(self.options.keys())
                    idx = keys.index(self.selected)
                    self.selected = keys[idx + 1] if idx < len(keys) - 1 else keys[0]
                self.submenu = None
                return True
            elif event.key == pygame.K_LEFT:
                if self.selected is None:
                    self.selected = list(self.options.keys())[-1]
                else:
                    keys = list(self.options.keys())
                    idx = keys.index(self.selected)
                    self.selected = keys[idx - 1] if idx > 0 else keys[-1]
                self.submenu = None
                return True
            elif event.key == pygame.K_RETURN:
                if self.submenu and self.options[self.selected][self.submenu]:
                    self.options[self.selected][self.submenu]()
                    self.submenu = None
                    return True
                elif self.selected == "File" and "(C)alibrate" in self.options[self.selected]:
                    self.options[self.selected]["(C)alibrate"]()
                    return True
            elif event.key == pygame.K_F11:
                self.toggle_fullscreen()
                return True
            elif event.key == pygame.K_c and self.selected == "File":
                self.options[self.selected]["(C)alibrate"]()
                return True
            elif event.key == pygame.K_a and self.selected == "Help":
                self.options[self.selected]["(A)bout"]()
                return True
            elif event.key == pygame.K_t and self.selected == "Help":
                self.options[self.selected]["(T)utorial"]()
                return True
            elif event.key == pygame.K_l and self.selected == "Leaderboard":
                self.options[self.selected]["(L)eaderboard"]()
                return True
        return False

    def handle_mouse_input(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered_main = None
            self.hovered_sub = None
            mouse_pos = event.pos
            for main_option, rect in self.main_rects.items():
                if rect.collidepoint(mouse_pos):
                    self.hovered_main = main_option
                    logger.debug(f"Hovered main option: {main_option}, Rect: {rect}, Mouse: {mouse_pos}")
                    break
            if self.selected:
                for sub_option, rect in self.sub_rects.items():
                    if rect.collidepoint(mouse_pos):
                        self.hovered_sub = sub_option
                        logger.debug(f"Hovered sub option: {sub_option}, Rect: {rect}, Mouse: {mouse_pos}")
                        break
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            logger.debug(f"Mouse click at: {mouse_pos}, Main rects: {self.main_rects}, Sub rects: {self.sub_rects}")
            for main_option, rect in self.main_rects.items():
                if rect.collidepoint(mouse_pos):
                    logger.debug(f"Clicked main option: {main_option}, Rect: {rect}, Mouse: {mouse_pos}")
                    self.selected = None if self.selected == main_option else main_option
                    self.submenu = None
                    return True
            if self.selected and self.sub_rects:
                for sub_option, rect in self.sub_rects.items():
                    if rect.collidepoint(mouse_pos):
                        if sub_option in self.options[self.selected]:
                            logger.debug(f"Clicked sub option: {sub_option}, Rect: {rect}, Mouse: {mouse_pos}")
                            self.options[self.selected][sub_option]()
                            self.submenu = None
                            self.selected = None
                            return True
            if self.selected and not any(rect.collidepoint(mouse_pos) for rect in self.main_rects.values()) and not any(rect.collidepoint(mouse_pos) for rect in self.sub_rects.values()):
                logger.debug(f"Clicked outside menu, closing. Mouse: {mouse_pos}")
                self.selected = None
                self.submenu = None
                return True
            return False
        return False

menu = Menu()
class AboutWindow(Window):
    def __init__(self):
        super().__init__(600, 400)
        self.text = [
            "In 1931, Automatic Industries introduced the 'Whiffle Board,' a pinball machine",
            "considered by many to be the first true pinball machine, featuring an",
            "electrically-powered scoring mechanism and the iconic plunger for launching",
            "the ball. Here's a more detailed look at the history:",
            "",
            "• Early Pinball Origins: Before the Whiffle Board, pinball-like games existed,",
            "  such as bagatelle, which involved players using a cue stick to shoot balls",
            "  across a table into scoring holes. [2, 3]",
            "• Automatic Industries' Innovation: In 1931, Automatic Industries, founded by",
            "  Arthur Paulin, Earl Froom, Myrl Park, and William Howell, introduced the",
            "  'Whiffle Board'. [2, 4]",
            "• Key Features: The Whiffle Board was notable for its electrically-powered",
            "  scoring mechanism and the introduction of the plunger, a key feature of",
            "  modern pinball machines. [1, 2]",
            "• Coin-Operated: The Whiffle Board was also one of the first coin-operated",
            "  pinball machines. [3]",
            "• 'Pinball' Term: The term 'pinball' emerged in 1936, referencing the nature",
            "  of the game's playing field and the pins that held the scoring holes. [1, 3]",
            "• Other games invented in the 1930s: Bingo by Bingo Novelty Company and",
            "  Baffle Ball by D. Gottlieb & Co. [1]",
            "• Golden Age of Pinball: Pinball experienced a temporary decline in popularity",
            "  during World War II, but interest rebounded after the war, especially after",
            "  D. Gottlieb & Co. invented flippers in 1947. The 'Golden Age' of pinball",
            "  lasted from 1948 until 1958. [1]",
            "",
            "Generative AI is experimental.",
            "[1] https://www.betson.com/history-of-pinball/",
            "[2] https://www.arcade92.com/post/pinball-wizards-tracing-the-evolution-of-the-world-s-first-pinball-machine",
            "[3] https://www.videoamusement.com/news/the-history-of-pinball/",
            "[4] https://pinballnirvana.com/forums/threads/the-very-first-whiffle-board-automatic-industries-1931.21197/"
        ]
        self.scroll_y = 0
        self.max_scroll = max(0, (len(self.text) * 20) - (self.height - 40))

    def activate(self):
        self.active = True

    def draw(self, screen):
        self.draw_base(screen, "About")
        if not self.active:
            return
        y_offset = 40 - self.scroll_y
        for line in self.text:
            text = self.font.render(line, True, COLORS["BLACK"])
            if 40 <= y_offset + 20 <= self.height - 20:
                self.surface.blit(text, (10, y_offset))
            y_offset += 20

    def handle_input(self, event):
        if self.handle_base_input(event):
            return True
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_y -= event.y * 20
            self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
            return True
        return False

class SettingsWindow(Window):
    def __init__(self):
        super().__init__(400, 300)
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

    def activate(self):
        self.active = True

    def draw(self, screen):
        self.draw_base(screen, "Settings")
        if not self.active:
            return
        labels = list(self.label_to_key.keys())
        y_offset = 40
        for label in labels:
            key = self.label_to_key[label]
            text = self.font.render(f"{label}: {int(self.slider_values[key])}", True, COLORS["BLACK"])
            self.surface.blit(text, (10, y_offset))
            slider_length = 200
            slider_x, slider_y = 150, y_offset + 5
            pygame.draw.rect(self.surface, COLORS["WHITE"], (slider_x, slider_y, slider_length, 10))
            slider_value = self.slider_values[key]
            max_value = 180 if "h" in key else 255 if "s" in key or "v" in key else 100
            slider_pos = slider_x + (slider_length - 20) * (slider_value / max_value)
            pygame.draw.rect(self.surface, COLORS["BLUE"], (slider_pos, slider_y - 5, 20, 20))
            self.slider_positions[key] = (slider_x, slider_y, slider_length)
            y_offset += 40

    def handle_input(self, event):
        if self.handle_base_input(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            window_x = (screen.get_width() - self.width) // 2
            window_y = (screen.get_height() - self.height) // 2
            local_x = mouse_pos[0] - window_x
            local_y = mouse_pos[1] - window_y
            for key, (slider_x, slider_y, slider_length) in self.slider_positions.items():
                slider_rect = pygame.Rect(slider_x + window_x, slider_y + window_y - 5, slider_length, 20)
                if slider_rect.collidepoint(mouse_pos):
                    self.dragging_slider = key
                    self.slider_start_x = mouse_pos[0] - (slider_x + window_x + (slider_length - 20) * (self.slider_values[key] / (180 if "h" in key else 255 if "s" in key or "v" in key else 100)))
                    return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_slider:
                slider_x, slider_y, slider_length = self.slider_positions[self.dragging_slider]
                window_x = (screen.get_width() - self.width) // 2
                mouse_x = max(slider_x + window_x, min(slider_x + window_x + slider_length - 20, event.pos[0]))
                max_value = 180 if "h" in self.dragging_slider else 255 if "s" in self.dragging_slider or "v" in self.dragging_slider else 100
                value = ((mouse_x - (slider_x + window_x)) / (slider_length - 20)) * max_value
                if "lower_" in self.dragging_slider:
                    lower_white[["h", "s", "v"].index(self.dragging_slider[-1])] = min(max_value - 1, max(0, int(value)))
                elif "upper_" in self.dragging_slider:
                    upper_white[["h", "s", "v"].index(self.dragging_slider[-1])] = min(max_value - 1, max(0, int(value)))
                elif "volume" in self.dragging_slider:
                    volume = min(1.0, max(0.0, value / 100))
                    pygame.mixer.music.set_volume(volume)
                    if score_sound:
                        score_sound.set_volume(volume)
                self.slider_values[self.dragging_slider] = value
                self.dragging_slider = None
                return True
        return False

class LeaderboardWindow(Window):
    def __init__(self):
        super().__init__(400, 300)
        self.scores = []
        self.view = "All-Time"
        self.load_scores()

    def activate(self):
        self.active = True

    def load_scores(self):
        try:
            if self.view == "Daily":
                today = time.strftime("%Y-%m-%d")
                response = supabase.table("leaderboard").select("id, initials, score, created_at").gte("created_at", f"{today}T00:00:00").lte("created_at", f"{today}T23:59:59").order("score", desc=True).limit(10).execute()
            else:
                response = supabase.table("leaderboard").select("id, initials, score, created_at").order("score", desc=True).limit(10).execute()
            self.scores = [{"initials": entry["initials"], "score": entry["score"], "date": entry["created_at"]} for entry in response.data]
            logger.info(f"Loaded {self.view} scores from Supabase: {self.scores}")
        except Exception as e:
            logger.error(f"Error fetching {self.view} scores from Supabase: {e}")
            try:
                with open("leaderboard.json", "r") as f:
                    self.scores = json.load(f)
            except FileNotFoundError:
                self.scores = []
            self.scores = sorted(self.scores, key=lambda x: x["score"], reverse=True)[:10]

    def save_score(self, initials, score, date, mode="Classic"):
        try:
            response = supabase.table("leaderboard").insert({"initials": initials, "score": score, "created_at": date, "mode": mode}).execute()
            logger.info(f"Score saved to Supabase: {initials} - {score} (Mode: {mode})")
            self.scores.append({"initials": initials, "score": score, "date": date})
            self.scores = sorted(self.scores, key=lambda x: x["score"], reverse=True)[:10]
            with open("leaderboard.json", "w") as f:
                json.dump(self.scores, f)
        except Exception as e:
            logger.error(f"Error saving score to Supabase: {e}")
            entry = {"initials": initials, "score": score, "date": date}
            self.scores.append(entry)
            self.scores = sorted(self.scores, key=lambda x: x["score"], reverse=True)[:10]
            with open("leaderboard.json", "w") as f:
                json.dump(self.scores, f)

    def clear_leaderboard(self):
        try:
            supabase.table("leaderboard").delete().gt("score", -1).execute()
            logger.info("Leaderboard cleared in Supabase.")
        except Exception as e:
            logger.error(f"Error clearing Supabase leaderboard: {e}")
        self.scores = []
        with open("leaderboard.json", "w") as f:
            json.dump(self.scores, f)

    def toggle_view(self):
        self.view = "Daily" if self.view == "All-Time" else "All-Time"
        self.load_scores()
        logger.info(f"Switched leaderboard view to {self.view}")

    def draw(self, screen):
        self.draw_base(screen, f"Leaderboard ({self.view})")
        if not self.active:
            return
        y_offset = 40
        for i, entry in enumerate(self.scores):
            date_str = entry['date'][:10]
            text = f"{i+1}. {entry['initials']} - {entry['score']} ({date_str})"
            score_text = self.font.render(text, True, COLORS["BLACK"])
            self.surface.blit(score_text, (10, y_offset))
            y_offset += 30
            if y_offset > self.height - 20:
                break

    def handle_input(self, event):
        if self.handle_base_input(event):
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_v:
                self.toggle_view()
                return True
        return False

about_window = AboutWindow()
settings_window = SettingsWindow()
leaderboard_window = LeaderboardWindow()

def reinitialize_camera():
    global cap
    if 'cap' in globals() and cap.isOpened():
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
    global cap
    pygame.mixer.music.pause()
    calibrated_holes = []
    calibrating = True
    input_active = False
    current_input = ""
    current_pos = None
    retry_count = 0
    max_retries = 10
    asking_oblong = False
    oblong_input = ""
    defining_rect = False
    rect_points = []
    points = 0
    cv2.namedWindow('Calibrate Holes', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Calibrate Holes', SETTINGS["INITIAL_WIDTH"], SETTINGS["INITIAL_HEIGHT"])
    def mouse_callback(event, x, y, flags, param):
        nonlocal input_active, current_pos, defining_rect, rect_points
        if event == cv2.EVENT_LBUTTONDOWN and not input_active and not asking_oblong and not defining_rect:
            input_active = True
            current_pos = (x, y)
            logger.info(f"Selected hole at ({x}, {y}). Enter points.")
            logger.debug(f"Mouse callback triggered, input_active: {input_active}")
    cv2.setMouseCallback('Calibrate Holes', mouse_callback)
def calibrate_holes():
    # ... (previous setup from Chunk 2)
    while calibrating:
        ret, frame = cap.read()
        if not ret:
            logger.warning(f"Failed to capture frame in calibration. Retry {retry_count + 1}/{max_retries}")
            retry_count += 1
            if retry_count >= max_retries:
                logger.error("Max retries reached. Exiting calibration.")
                calibrating = False
                break
            time.sleep(0.1)
            continue
        retry_count = 0
        for i, (x, y, radius, points, is_oblong, rect) in enumerate(calibrated_holes):
            color = COLORS["GREEN"]
            label = ""
            if i == 0:
                color = COLORS["BLUE"]
                label = " (Extra Ball)"
            elif i == 1:
                color = COLORS["RED"]
                label = " (Double Points)"
            cv2.circle(frame, (x, y), radius, color, 2)
            cv2.putText(frame, f"{points}{label}", (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if is_oblong and rect:
                cv2.rectangle(frame, rect[:2], rect[2:], color, 2)
        if input_active and current_pos and not asking_oblong and not defining_rect:
            x, y = current_pos
            cv2.rectangle(frame, (x, y + 10), (x + 100, y + 40), COLORS["WHITE"], -1)
            cv2.putText(frame, current_input, (x + 5, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["BLACK"], 2)
            cv2.circle(frame, (x, y), 20, COLORS["GREEN"], 2)
        if asking_oblong and current_pos:
            x, y = current_pos
            cv2.rectangle(frame, (x, y + 50), (x + 200, y + 80), COLORS["WHITE"], -1)
            cv2.putText(frame, "Oblong hole? (y/n): " + oblong_input, (x + 5, y + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["BLACK"], 2)
            cv2.circle(frame, (x, y), 20, COLORS["GREEN"], 2)
        if defining_rect and current_pos:
            x, y = current_pos
            cv2.putText(frame, "Click top-left corner", (x, y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["YELLOW"], 2)
            if len(rect_points) == 1:
                x1, y1 = rect_points[0]
                cv2.putText(frame, "Click bottom-right corner", (x, y + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["YELLOW"], 2)
                cv2.circle(frame, (x1, y1), 5, COLORS["YELLOW"], -1)
        cv2.imshow('Calibrate Holes', frame)
        key = cv2.waitKey(1) & 0xFF
        if cv2.getWindowProperty('Calibrate Holes', cv2.WND_PROP_VISIBLE) < 1:
            logger.debug("Calibration window closed by user.")
            calibrating = False
            break
        if key == ord('c') and not input_active and not asking_oblong and not defining_rect:
            logger.debug("Calibration exited via 'c' key.")
            calibrating = False
            break
        if input_active and not asking_oblong and not defining_rect:
            if key == 13:
                points = int(current_input) if current_input.isdigit() else 10
                logger.debug(f"Points entered: {points}")
                asking_oblong = True
                input_active = False
            elif key == 8:
                current_input = current_input[:-1]
            elif key in range(48, 58):
                current_input += chr(key)
        elif asking_oblong:
            if key == ord('y'):
                oblong_input = "y"
                asking_oblong = False
                defining_rect = True
                cv2.setMouseCallback('Calibrate Holes', lambda event, x, y, flags, param: None)
                def rect_callback(event, x, y, flags, param):
                    nonlocal rect_points
                    if event == cv2.EVENT_LBUTTONDOWN and len(rect_points) < 2:
                        rect_points.append((x, y))
                        if len(rect_points) == 2:
                            cv2.setMouseCallback('Calibrate Holes', mouse_callback)
                cv2.setMouseCallback('Calibrate Holes', rect_callback)
            elif key == ord('n'):
                oblong_input = "n"
                asking_oblong = False
                calibrated_holes.append((current_pos[0], current_pos[1], 20, points, False, None))
                logger.info(f"Added hole at {current_pos} with {points} points, Oblong: False")
                current_input = ""
                current_pos = None
                input_active = True
        elif defining_rect:
            if len(rect_points) == 2:
                x1, y1 = rect_points[0]
                x2, y2 = rect_points[1]
                rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                calibrated_holes.append((current_pos[0], current_pos[1], 20, points, True, rect))
                logger.info(f"Added hole at {current_pos} with {points} points, Oblong: True, Rect: {rect}")
                current_input = ""
                current_pos = None
                defining_rect = False
                rect_points = []
                input_active = True
                cv2.setMouseCallback('Calibrate Holes', mouse_callback)
        time.sleep(0.05)
    if calibrated_holes:
        save_calibrated_holes(calibrated_holes)
    cv2.destroyAllWindows()
    logger.info("Reinitializing camera after calibration...")
    if not reinitialize_camera():
        logger.error("Failed to reinitialize camera. Exiting...")
        sys.exit()
    pygame.mixer.music.unpause()
    return calibrated_holes

def detect_ball_in_hole(image, hole_coords, game_state, frame_count, scale_x=1.0, scale_y=1.0):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    mask_red = cv2.inRange(hsv, lower_red, upper_red)
    kernel = np.ones((5, 5), np.uint8)
    mask_white = cv2.dilate(cv2.erode(mask_white, kernel, iterations=1), kernel, iterations=1)
    mask_red = cv2.dilate(cv2.erode(mask_red, kernel, iterations=1), kernel, iterations=1)
    ball_positions, points_list, is_red_list = [], [], []
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
            if hole_pos in game_state.detection_cooldown and frame_count - game_state.detection_cooldown[hole_pos] < SETTINGS["COOLDOWN_FRAMES"]:
                continue
            if hole_pos in game_state.scored_balls:
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
                        red_mask_region = cv2.inRange(hsv_region, lower_red, upper_red)
                        is_red = cv2.countNonZero(red_mask_region) > (region.shape[0] * region.shape[1] * 0.3)
                        final_points = points * 2 if is_red or game_state.power_up == "Double Points" else points
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
                        for _ in range(10):
                            particles.append(Particle(hole_pos[0], hole_pos[1], COLORS["YELLOW"] if final_points > points else COLORS["GREEN"]))
                        hole_index = next((i for i, h in enumerate(game_state.hole_positions) if h[0] == x and h[1] == y), -1)
                        if hole_index == 0 and not is_red:
                            game_state.activate_power_up("Extra Ball")
                        elif hole_index == 1 and is_red:
                            game_state.activate_power_up("Double Points")
                        del game_state.confirming_balls[ball_id]
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
            del game_state.confirming_balls[ball_id]
            if hole_pos in game_state.detected_positions:
                game_state.detected_positions.remove(hole_pos)
    return ball_positions, points_list, is_red_list

def draw_ui():
    global status_surface
    current_width, current_height = screen.get_size()
    if 'status_surface' not in globals() or status_surface.get_size() != (current_width, SETTINGS["STATUS_BAR_HEIGHT"]):
        status_surface = pygame.Surface((current_width, SETTINGS["STATUS_BAR_HEIGHT"]))
    status_surface.fill(COLORS["GRAY"])
    score_text = FONTS["ui"].render(f"Balls: {game.balls if game.mode == 'Classic' else '∞'}  Score: {game.score}  Time: {game.time}  Power-Up: {game.power_up or 'None'}", True, COLORS["WHITE"])
    status_surface.blit(score_text, (10, 10))
    screen.blit(status_surface, (0, current_height - SETTINGS["STATUS_BAR_HEIGHT"]))

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

running = True
frame_count = 0
retry_count = 0
max_retries = 10
focus_lost = False
splash_screen_active = True
splash_alpha = 255
fade_duration = 1000
fade_start_time = pygame.time.get_ticks()
FRAME_SKIP = 2
frame_skip_counter = 0

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
        for particle in particles[:]:
            particle.update()
            particle.draw(screen, playfield_offset_x, playfield_offset_y)
            if particle.life <= 0:
                particles.remove(particle)
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
            if elapsed >= fade_duration:
                splash_alpha = 0
                splash_screen_active = False
            else:
                t = elapsed / fade_duration
                splash_alpha = 255 * (1 - t**2)
            splash_copy = splash_image.copy()
            splash_copy.set_alpha(int(splash_alpha))
            splash_copy = pygame.transform.smoothscale(splash_copy, (current_width, current_height))
            screen.blit(splash_copy, (0, 0))
        pygame.display.flip()
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
        game.update_power_up()
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == pygame.ACTIVEEVENT:
                if event.gain == 0 and event.state == 2:
                    focus_lost = True
                    logger.info("Focus lost. Click to regain focus.")
            elif event.type == KEYDOWN:
                if about_window.active:
                    about_window.handle_input(event)
                elif settings_window.active:
                    settings_window.handle_input(event)
                elif leaderboard_window.active:
                    leaderboard_window.handle_input(event)
                else:
                    menu.handle_input(event)
                    if event.key == pygame.K_l:
                        game.show_leaderboard = not game.show_leaderboard
                    elif event.key == pygame.K_r:
                        game.reset()
                    elif event.key == pygame.K_c:
                        game.hole_positions = calibrate_holes()
            elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
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