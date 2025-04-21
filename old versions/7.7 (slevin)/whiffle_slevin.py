import cv2
import numpy as np
import pygame
import sys
from pygame.locals import *
import time
import json
import os
from supabase import create_client, Client  # Add Supabase imports

# Logging Control
DEBUG = False

# Supabase credentials
SUPABASE_URL = "https://jtkbujumrobglftzokcs.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0a2J1anVtcm9iZ2xmdHpva2NzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMTM4NzcsImV4cCI6MjA1NzU4OTg3N30.OibLuqr3X922SUSBL8yGxDw8uwuTjivH97-2wNhJDqs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Pygame and display the splash screen immediately
pygame.init()
INITIAL_WIDTH, INITIAL_HEIGHT = 1280, 720
screen = pygame.display.set_mode((INITIAL_WIDTH, INITIAL_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Whiffle Playfield")

try:
    splash_image = pygame.image.load("whiffle_splash.jpg").convert_alpha()
    splash_image = pygame.transform.smoothscale(splash_image, (INITIAL_WIDTH, INITIAL_HEIGHT))
except FileNotFoundError:
    print("Splash screen image 'whiffle_splash.jpg' not found. Using a blank splash screen.")
    splash_image = pygame.Surface((INITIAL_WIDTH, INITIAL_HEIGHT), pygame.SRCALPHA)
    splash_image.fill((50, 50, 50))

screen.blit(splash_image, (0, 0))
pygame.display.flip()

pygame.mixer.init()
clock = pygame.time.Clock()

BACKGROUND_MUSIC_FILE = "background_music.mp3"
try:
    pygame.mixer.music.load(BACKGROUND_MUSIC_FILE)
    pygame.mixer.music.set_volume(0.5)
    pygame.mixer.music.play(-1)
    print(f"Background music '{BACKGROUND_MUSIC_FILE}' loaded and playing.")
except FileNotFoundError:
    print(f"Background music file '{BACKGROUND_MUSIC_FILE}' not found. Background music disabled.")
except Exception as e:
    print(f"Error loading background music: {e}")

COOLDOWN_FRAMES = 30
CONFIRMATION_FRAMES = 10
SOUND_COOLDOWN = 1.0
MENU_HEIGHT = 60
STATUS_BAR_HEIGHT = 50

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

lower_white = np.array([0, 0, 200])
upper_white = np.array([180, 30, 255])
lower_red = np.array([0, 100, 100])
upper_red = np.array([10, 255, 255])
volume = 0.5
pygame.mixer.music.set_volume(volume)

try:
    score_sound = pygame.mixer.Sound("score.wav")
except FileNotFoundError:
    print("Score sound file 'score.wav' not found. Sound effects disabled.")
    score_sound = None

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

    def reset(self):
        self.score = 0
        self.balls = 10
        self.power_up = None
        self.power_up_duration = 0
        self.time = "N/A"
        self.scored_balls.clear()
        self.detection_cooldown.clear()
        self.detected_positions.clear()
        self.confirming_balls.clear()
        self.just_reset = True
        print("Game reset: Score = 0, Balls = 10, Power-Up = None")

    def activate_power_up(self, power_up_name):
        if power_up_name == "Extra Ball":
            self.balls += 1
            self.power_up = "Extra Ball (Active)"
            self.power_up_duration = 60
            print("Power-Up: Extra Ball activated!")
        elif power_up_name == "Double Points":
            self.power_up = "Double Points"
            self.power_up_duration = 900
            print("Power-Up: Double Points activated for 30 seconds!")

    def update_power_up(self):
        if self.power_up_duration > 0:
            self.power_up_duration -= 1
            if self.power_up_duration <= 0:
                self.power_up = None
                print("Power-Up expired.")
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
class Menu:
    def __init__(self):
        self.active = True
        self.options = {
            "File": {
                "(C)alibrate": lambda: calibrate_holes(),
                "Start New Game": lambda: game.reset(),
            },
            "Settings": {
                "Adjust Settings": lambda: self.show_settings(),
            },
            "View": {
                "Toggle Fullscreen": lambda: self.toggle_fullscreen(),
            },
            "Help": {
                "(A)bout": lambda: self.show_about(),
                "(T)utorial": lambda: self.show_tutorial(),
            },
            "Leaderboard": {
                "(L)eaderboard": lambda: self.show_leaderboard(),
                "Clear Leaderboard": lambda: self.clear_leaderboard(),
            }
        }
        self.font = pygame.font.Font(None, 30)
        self.selected = None
        self.submenu = None
        self.menu_surface = pygame.Surface((INITIAL_WIDTH, MENU_HEIGHT), pygame.SRCALPHA)
        self.main_rects = {}
        self.sub_rects = {}
        self.hovered_main = None
        self.hovered_sub = None
        self.fullscreen = False
        self.button_height = 40
        self.button_padding = 10

    def show_about(self):
        global about_window
        about_window.active = True

    def show_settings(self):
        global settings_window
        settings_window.active = True

    def show_tutorial(self):
        print("Showing tutorial...")
        pygame.display.set_caption("Tutorial - Whiffle Playfield")
        time.sleep(2)
        pygame.display.set_caption("Whiffle Playfield")

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        global screen, INITIAL_WIDTH, INITIAL_HEIGHT
        if self.fullscreen:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            screen = pygame.display.set_mode((INITIAL_WIDTH, INITIAL_HEIGHT), pygame.RESIZABLE)
        return True

    def show_leaderboard(self):
        global leaderboard_window
        leaderboard_window.active = True

    def clear_leaderboard(self):
        global leaderboard_window
        leaderboard_window.clear_leaderboard()
        print("Leaderboard cleared.")

    def draw(self, screen):
        current_width, current_height = screen.get_size()
        max_submenu_items = max(len(sub_options) for sub_options in self.options.values())
        total_height = MENU_HEIGHT + max_submenu_items * (self.button_height + self.button_padding)
        menu_surface = pygame.Surface((current_width, total_height), pygame.SRCALPHA)
        pygame.draw.rect(menu_surface, DARK_GRAY, (0, 0, current_width, MENU_HEIGHT))
        pygame.draw.line(menu_surface, LIGHT_GRAY, (0, MENU_HEIGHT - 1), (current_width, MENU_HEIGHT - 1), 2)

        self.main_rects.clear()
        self.sub_rects.clear()

        x_offset = self.button_padding
        y_offset = (MENU_HEIGHT - self.button_height) // 2

        for main_option, sub_options in self.options.items():
            text_surface = self.font.render(main_option, True, WHITE)
            button_width = max(120, text_surface.get_width() + 20)
            if main_option == "Leaderboard":
                button_width += 20
            button_rect = pygame.Rect(x_offset, y_offset, button_width, self.button_height)
            color = YELLOW if main_option == self.hovered_main or main_option == self.selected else WHITE
            pygame.draw.rect(menu_surface, LIGHT_GRAY, button_rect)
            pygame.draw.rect(menu_surface, BUTTON_BORDER, button_rect, 2)
            text_rect = text_surface.get_rect(center=button_rect.center)
            menu_surface.blit(text_surface, text_rect)
            self.main_rects[main_option] = button_rect
            x_offset += button_width + self.button_padding

            if self.selected == main_option and sub_options:
                submenu_x = button_rect.left
                submenu_y = MENU_HEIGHT
                submenu_width = max(200, button_rect.width + 20)
                submenu_height = len(sub_options) * (self.button_height + self.button_padding)
                pygame.draw.rect(menu_surface, SUBMENU_BG, (submenu_x, submenu_y, submenu_width, submenu_height))
                sub_y = submenu_y
                for sub_option in sub_options:
                    sub_text_surface = self.font.render(sub_option, True, WHITE)
                    sub_button_width = max(200, sub_text_surface.get_width() + 20)
                    sub_button_rect = pygame.Rect(submenu_x, sub_y, sub_button_width, self.button_height)
                    color = YELLOW if sub_option == self.hovered_sub else WHITE
                    pygame.draw.rect(menu_surface, LIGHT_GRAY, sub_button_rect)
                    sub_text_rect = sub_text_surface.get_rect(center=sub_button_rect.center)
                    menu_surface.blit(sub_text_surface, sub_text_rect)
                    self.sub_rects[sub_option] = sub_button_rect
                    if DEBUG:
                        print(f"Drawing submenu: {sub_option} at {sub_button_rect}")
                    sub_y += self.button_height + self.button_padding

        screen.blit(menu_surface, (0, 0))

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                if self.selected and self.options[self.selected]:
                    if self.submenu is None:
                        self.submenu = list(self.options[self.selected].keys())[0]
                    else:
                        keys = list(self.options[self.selected].keys())
                        idx = keys.index(self.submenu)
                        if idx < len(keys) - 1:
                            self.submenu = keys[idx + 1]
                        else:
                            self.submenu = keys[0]
                return True
            elif event.key == pygame.K_UP:
                if self.selected and self.options[self.selected]:
                    if self.submenu is None:
                        self.submenu = list(self.options[self.selected].keys())[-1]
                    else:
                        keys = list(self.options[self.selected].keys())
                        idx = keys.index(self.submenu)
                        if idx > 0:
                            self.submenu = keys[idx - 1]
                        else:
                            self.submenu = keys[-1]
                return True
            elif event.key == pygame.K_RIGHT:
                if self.selected is None:
                    self.selected = list(self.options.keys())[0]
                else:
                    keys = list(self.options.keys())
                    idx = keys.index(self.selected)
                    if idx < len(keys) - 1:
                        self.selected = keys[idx + 1]
                    else:
                        self.selected = keys[0]
                self.submenu = None
                return True
            elif event.key == pygame.K_LEFT:
                if self.selected is None:
                    self.selected = list(self.options.keys())[-1]
                else:
                    keys = list(self.options.keys())
                    idx = keys.index(self.selected)
                    if idx > 0:
                        self.selected = keys[idx - 1]
                    else:
                        self.selected = keys[-1]
                self.submenu = None
                return True
            elif event.key == pygame.K_RETURN:
                if self.submenu and self.options[self.selected][self.submenu]:
                    self.options[self.selected][self.submenu]()
                    self.submenu = None
                    return True
                elif self.selected == "File" and self.options[self.selected]["(C)alibrate"]:
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
                    if DEBUG:
                        print(f"Hovered main option: {main_option}, Rect: {rect}, Mouse: {mouse_pos}")
                    break
            if self.selected:
                for sub_option, rect in self.sub_rects.items():
                    if rect.collidepoint(mouse_pos):
                        self.hovered_sub = sub_option
                        if DEBUG:
                            print(f"Hovered sub option: {sub_option}, Rect: {rect}, Mouse: {mouse_pos}")
                        break
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            if DEBUG:
                print(f"Mouse click at: {mouse_pos}, Main rects: {self.main_rects}, Sub rects: {self.sub_rects}")
            for main_option, rect in self.main_rects.items():
                if rect.collidepoint(mouse_pos):
                    if DEBUG:
                        print(f"Clicked main option: {main_option}, Rect: {rect}, Mouse: {mouse_pos}")
                    if self.selected == main_option:
                        self.selected = None
                        self.submenu = None
                    else:
                        self.selected = main_option
                        self.submenu = None
                    return True
            if self.selected and self.sub_rects:
                for sub_option, rect in self.sub_rects.items():
                    if rect.collidepoint(mouse_pos):
                        if sub_option in self.options[self.selected]:
                            if DEBUG:
                                print(f"Clicked sub option: {sub_option}, Rect: {rect}, Mouse: {mouse_pos}")
                            self.options[self.selected][sub_option]()
                            self.submenu = None
                            self.selected = None
                            return True
            if self.selected and not any(rect.collidepoint(mouse_pos) for rect in self.main_rects.values()) and not any(rect.collidepoint(mouse_pos) for rect in self.sub_rects.values()):
                if DEBUG:
                    print(f"Clicked outside menu, closing. Mouse: {mouse_pos}")
                self.selected = None
                self.submenu = None
                return True
            return False
        return False

menu = Menu()

class AboutWindow:
    def __init__(self):
        self.active = False
        self.font = pygame.font.Font(None, 24)
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
        self.window_surface = None
        self.close_button_rect = None
        self.scroll_y = 0
        self.window_width = 600
        self.window_height = 400
        self.max_scroll = max(0, (len(self.text) * 20) - (self.window_height - 40))

    def draw(self, screen):
        if not self.active:
            return
        if self.window_surface is None:
            self.window_surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
            self.window_surface.fill((200, 200, 200, 200))
            self.close_button_rect = pygame.Rect(self.window_width - 40, 10, 30, 30)
            pygame.draw.rect(self.window_surface, RED, self.close_button_rect)

        self.window_surface.fill((200, 200, 200, 200))
        pygame.draw.rect(self.window_surface, RED, self.close_button_rect)
        y_offset = 40 - self.scroll_y
        for line in self.text:
            text = self.font.render(line, True, BLACK)
            if 40 <= y_offset + 20 <= self.window_height - 20:
                self.window_surface.blit(text, (10, y_offset))
            y_offset += 20

        screen.blit(self.window_surface, ((screen.get_width() - self.window_width) // 2, (screen.get_height() - self.window_height) // 2))

    def handle_input(self, event):
        if not self.active:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            window_x = (screen.get_width() - self.window_width) // 2
            window_y = (screen.get_height() - self.window_height) // 2
            local_x = mouse_pos[0] - window_x
            local_y = mouse_pos[1] - window_y
            if self.close_button_rect.collidepoint(local_x, local_y):
                self.active = False
                return True
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_y -= event.y * 20
            self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            return True
        return False

about_window = AboutWindow()

class SettingsWindow:
    def __init__(self):
        self.active = False
        self.font = pygame.font.Font(None, 24)
        self.window_width = 400
        self.window_height = 300
        self.window_surface = None
        self.close_button_rect = None
        self.slider_values = {
            "lower_h": lower_white[0],
            "lower_s": lower_white[1],
            "lower_v": lower_white[2],
            "upper_h": upper_white[0],
            "upper_s": upper_white[1],
            "upper_v": upper_white[2],
            "volume": volume * 100
        }
        self.slider_positions = {}
        self.dragging_slider = None
        self.label_to_key = {
            "HSV Lower (H)": "lower_h",
            "HSV Lower (S)": "lower_s",
            "HSV Lower (V)": "lower_v",
            "HSV Upper (H)": "upper_h",
            "HSV Upper (S)": "upper_s",
            "HSV Upper (V)": "upper_v",
            "Volume": "volume"
        }

    def draw(self, screen):
        if not self.active:
            return
        if self.window_surface is None:
            self.window_surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
            self.window_surface.fill((200, 200, 200, 200))
            self.close_button_rect = pygame.Rect(self.window_width - 40, 10, 30, 30)
            pygame.draw.rect(self.window_surface, RED, self.close_button_rect)

        self.window_surface.fill((200, 200, 200, 200))
        pygame.draw.rect(self.window_surface, RED, self.close_button_rect)

        labels = [
            "HSV Lower (H)", "HSV Lower (S)", "HSV Lower (V)",
            "HSV Upper (H)", "HSV Upper (S)", "HSV Upper (V)",
            "Volume"
        ]
        y_offset = 40
        for label in labels:
            key = self.label_to_key[label]
            text = self.font.render(label + f": {int(self.slider_values[key])}", True, BLACK)
            self.window_surface.blit(text, (10, y_offset))

            slider_length = 200
            slider_x = 150
            slider_y = y_offset + 5
            pygame.draw.rect(self.window_surface, WHITE, (slider_x, slider_y, slider_length, 10))
            slider_value = self.slider_values[key]
            max_value = 180 if "h" in key else 255 if "s" in key or "v" in key else 100
            slider_pos = slider_x + (slider_length - 20) * (slider_value / max_value)
            pygame.draw.rect(self.window_surface, BLUE, (slider_pos, slider_y - 5, 20, 20))
            self.slider_positions[key] = (slider_x, slider_y, slider_length)
            y_offset += 40

        screen.blit(self.window_surface, ((screen.get_width() - self.window_width) // 2, (screen.get_height() - self.window_height) // 2))

    def handle_input(self, event):
        if not self.active:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            window_x = (screen.get_width() - self.window_width) // 2
            window_y = (screen.get_height() - self.window_height) // 2
            local_x = mouse_pos[0] - window_x
            local_y = mouse_pos[1] - window_y
            if self.close_button_rect.collidepoint(local_x, local_y):
                self.active = False
                return True
            for key, (slider_x, slider_y, slider_length) in self.slider_positions.items():
                slider_rect = pygame.Rect(slider_x + window_x, slider_y + window_y - 5, slider_length, 20)
                if slider_rect.collidepoint(mouse_pos):
                    self.dragging_slider = key
                    self.slider_start_x = mouse_pos[0] - (slider_x + window_x + (slider_length - 20) * (self.slider_values[key] / (180 if "h" in key else 255 if "s" in key or "v" in key else 100)))
                    return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_slider:
                slider_x, slider_y, slider_length = self.slider_positions[self.dragging_slider]
                window_x = (screen.get_width() - self.window_width) // 2
                mouse_x = max(slider_x + window_x, min(slider_x + window_x + slider_length - 20, event.pos[0]))
                max_value = 180 if "h" in self.dragging_slider else 255 if "s" in self.dragging_slider or "v" in self.dragging_slider else 100
                value = ((mouse_x - (slider_x + window_x)) / (slider_length - 20)) * max_value
                if "lower_h" in self.dragging_slider:
                    lower_white[0] = min(179, max(0, int(value)))
                elif "lower_s" in self.dragging_slider:
                    lower_white[1] = min(255, max(0, int(value)))
                elif "lower_v" in self.dragging_slider:
                    lower_white[2] = min(255, max(0, int(value)))
                elif "upper_h" in self.dragging_slider:
                    upper_white[0] = min(179, max(0, int(value)))
                elif "upper_s" in self.dragging_slider:
                    upper_white[1] = min(255, max(0, int(value)))
                elif "upper_v" in self.dragging_slider:
                    upper_white[2] = min(255, max(0, int(value)))
                elif "volume" in self.dragging_slider:
                    volume = min(1.0, max(0.0, value / 100))
                    pygame.mixer.music.set_volume(volume)
                    if score_sound:
                        score_sound.set_volume(volume)
                self.slider_values[self.dragging_slider] = value
                self.dragging_slider = None
                return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            return True
        return False

settings_window = SettingsWindow()
class LeaderboardWindow:
    def __init__(self):
        self.active = False
        self.font = pygame.font.Font(None, 24)
        self.window_width = 400
        self.window_height = 300
        self.window_surface = None
        self.close_button_rect = None
        self.scores = []
        self.load_scores()

    def load_scores(self):
        try:
            response = supabase.table("leaderboard").select("id, initials, score, created_at").order("score", desc=True).limit(10).execute()
            self.scores = [
                {"initials": entry["initials"], "score": entry["score"], "date": entry["created_at"]}
                for entry in response.data
            ]
            print("Loaded scores from Supabase:", self.scores)
        except Exception as e:
            print(f"Error fetching scores from Supabase: {e}")
            try:
                with open("leaderboard.json", "r") as f:
                    self.scores = json.load(f)
            except FileNotFoundError:
                self.scores = []
            self.scores = sorted(self.scores, key=lambda x: x["score"], reverse=True)[:10]

    def save_score(self, initials, score, date):
        try:
            response = supabase.table("leaderboard").insert({
                "initials": initials,
                "score": score,
                "created_at": date
            }).execute()
            print(f"Score saved to Supabase: {initials} - {score}")
            self.scores.append({"initials": initials, "score": score, "date": date})
            self.scores = sorted(self.scores, key=lambda x: x["score"], reverse=True)[:10]
            with open("leaderboard.json", "w") as f:
                json.dump(self.scores, f)
        except Exception as e:
            print(f"Error saving score to Supabase: {e}")
            entry = {"initials": initials, "score": score, "date": date}
            self.scores.append(entry)
            self.scores = sorted(self.scores, key=lambda x: x["score"], reverse=True)[:10]
            with open("leaderboard.json", "w") as f:
                json.dump(self.scores, f)

    def clear_leaderboard(self):
        try:
            supabase.table("leaderboard").delete().gt("score", -1).execute()
            print("Leaderboard cleared in Supabase.")
        except Exception as e:
            print(f"Error clearing Supabase leaderboard: {e}")
        self.scores = []
        with open("leaderboard.json", "w") as f:
            json.dump(self.scores, f)

    def draw(self, screen):
        if not self.active:
            return
        if self.window_surface is None:
            self.window_surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
            self.window_surface.fill((200, 200, 200, 200))
            self.close_button_rect = pygame.Rect(self.window_width - 40, 10, 30, 30)
            pygame.draw.rect(self.window_surface, RED, self.close_button_rect)

        self.window_surface.fill((200, 200, 200, 200))
        pygame.draw.rect(self.window_surface, RED, self.close_button_rect)

        title = self.font.render("Leaderboard (Online)", True, BLACK)
        self.window_surface.blit(title, (10, 10))

        y_offset = 40
        for i, entry in enumerate(self.scores):
            date_str = entry['date'][:10]  # YYYY-MM-DD
            text = f"{i+1}. {entry['initials']} - {entry['score']} ({date_str})"
            score_text = self.font.render(text, True, BLACK)
            self.window_surface.blit(score_text, (10, y_offset))
            y_offset += 30
            if y_offset > self.window_height - 20:
                break

        screen.blit(self.window_surface, ((screen.get_width() - self.window_width) // 2, (screen.get_height() - self.window_height) // 2))

    def handle_input(self, event):
        if not self.active:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            window_x = (screen.get_width() - self.window_width) // 2
            window_y = (screen.get_height() - self.window_height) // 2
            local_x = mouse_pos[0] - window_x
            local_y = mouse_pos[1] - window_y
            if self.close_button_rect.collidepoint(local_x, local_y):
                self.active = False
                return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            return True
        return False

leaderboard_window = LeaderboardWindow()
CALIBRATION_FILE = "calibration.json"

def reinitialize_camera():
    global cap
    if 'cap' in globals() and cap.isOpened():
        cap.release()
    time.sleep(1)
    backends = [cv2.CAP_MSMF, cv2.CAP_VFW, cv2.CAP_DSHOW, cv2.CAP_FFMPEG, cv2.CAP_ANY]
    indices = [0, 1]
    for backend in backends:
        for index in indices:
            print(f"Trying backend {backend} and index {index}...")
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, INITIAL_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, INITIAL_HEIGHT)
                time.sleep(0.2)
                ret, frame = cap.read()
                if ret and frame is not None and frame.size != 0 and frame.shape == (INITIAL_HEIGHT, INITIAL_WIDTH, 3):
                    print(f"Success with backend {backend} and index {index}. Shape: {frame.shape}")
                    return True
                cap.release()
    print("Error: Could not open video capture.")
    return False

def load_calibrated_holes():
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, 'r') as f:
            try:
                data = json.load(f)
                print("Loaded calibration data.")
                holes = []
                for hole in data["holes"]:
                    if len(hole) == 4:
                        x, y, radius, points = hole
                        holes.append((x, y, radius, points, False, None))
                    else:
                        holes.append(tuple(hole))
                return holes
            except Exception as e:
                print(f"Error loading calibration: {e}")
    print("No calibration file. Entering calibration mode.")
    return calibrate_holes()

def save_calibrated_holes(holes):
    with open(CALIBRATION_FILE, 'w') as f:
        json.dump({"holes": holes}, f)
        print("Calibration saved.")

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
    cv2.resizeWindow('Calibrate Holes', INITIAL_WIDTH, INITIAL_HEIGHT)

    def mouse_callback(event, x, y, flags, param):
        nonlocal input_active, current_pos, defining_rect, rect_points
        if event == cv2.EVENT_LBUTTONDOWN and not input_active and not asking_oblong and not defining_rect:
            input_active = True
            current_pos = (x, y)
            print(f"Selected hole at ({x}, {y}). Enter points.")
            if DEBUG:
                print(f"Mouse callback triggered, input_active: {input_active}")

    cv2.setMouseCallback('Calibrate Holes', mouse_callback)

    while calibrating:
        ret, frame = cap.read()
        if not ret:
            print(f"Failed to capture frame in calibration. Retry {retry_count + 1}/{max_retries}")
            retry_count += 1
            if retry_count >= max_retries:
                print("Max retries reached. Exiting calibration.")
                calibrating = False
                break
            time.sleep(0.1)
            continue

        retry_count = 0
        for i, (x, y, radius, points, is_oblong, rect) in enumerate(calibrated_holes):
            color = GREEN
            label = ""
            if i == 0:
                color = BLUE
                label = " (Extra Ball)"
            elif i == 1:
                color = RED
                label = " (Double Points)"
            cv2.circle(frame, (x, y), radius, color, 2)
            cv2.putText(frame, f"{points}{label}", (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if is_oblong and rect:
                x1, y1, x2, y2 = rect
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        if input_active and current_pos and not asking_oblong and not defining_rect:
            x, y = current_pos
            cv2.rectangle(frame, (x, y + 10), (x + 100, y + 40), (255, 255, 255), -1)
            cv2.putText(frame, current_input, (x + 5, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            cv2.circle(frame, (x, y), 20, (0, 255, 0), 2)

        if asking_oblong and current_pos:
            x, y = current_pos
            cv2.rectangle(frame, (x, y + 50), (x + 200, y + 80), (255, 255, 255), -1)
            cv2.putText(frame, "Oblong hole? (y/n): " + oblong_input, (x + 5, y + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            cv2.circle(frame, (x, y), 20, (0, 255, 0), 2)

        if defining_rect and current_pos:
            x, y = current_pos
            cv2.putText(frame, "Click top-left corner", (x, y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            if len(rect_points) == 1:
                x1, y1 = rect_points[0]
                cv2.putText(frame, "Click bottom-right corner", (x, y + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.circle(frame, (x1, y1), 5, (0, 255, 255), -1)

        cv2.imshow('Calibrate Holes', frame)
        key = cv2.waitKey(1) & 0xFF

        if cv2.getWindowProperty('Calibrate Holes', cv2.WND_PROP_VISIBLE) < 1:
            if DEBUG:
                print("Calibration window closed by user.")
            calibrating = False
            break

        if key == ord('c') and not input_active and not asking_oblong and not defining_rect:
            if DEBUG:
                print("Calibration exited via 'c' key.")
            calibrating = False
            break

        if input_active and not asking_oblong and not defining_rect:
            if key == 13:
                points = int(current_input) if current_input.isdigit() else 10
                if DEBUG:
                    print(f"Points entered: {points}")
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
                if DEBUG:
                    print(f"Adding hole at {current_pos} with points: {points}")
                calibrated_holes.append((current_pos[0], current_pos[1], 20, points, False, None))
                print(f"Added hole at {current_pos} with {points} points, Oblong: False")
                current_input = ""
                current_pos = None
                input_active = True
                if DEBUG:
                    print(f"State reset: Ready to select next hole, calibrating: {calibrating}")

        elif defining_rect:
            if len(rect_points) == 2:
                x1, y1 = rect_points[0]
                x2, y2 = rect_points[1]
                rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                if DEBUG:
                    print(f"Adding hole at {current_pos} with points: {points}")
                calibrated_holes.append((current_pos[0], current_pos[1], 20, points, True, rect))
                print(f"Added hole at {current_pos} with {points} points, Oblong: True, Rect: {rect}")
                current_input = ""
                current_pos = None
                defining_rect = False
                rect_points = []
                input_active = True
                cv2.setMouseCallback('Calibrate Holes', mouse_callback)
                if DEBUG:
                    print(f"State reset: Ready to select next hole, calibrating: {calibrating}")

        time.sleep(0.05)
        if DEBUG:
            print(f"Calibration loop iteration, calibrating: {calibrating}")

    if calibrated_holes:
        save_calibrated_holes(calibrated_holes)

    cv2.destroyAllWindows()
    print("Reinitializing camera after calibration...")
    if not reinitialize_camera():
        print("Failed to reinitialize camera. Exiting...")
        sys.exit()
    pygame.mixer.music.unpause()
    return calibrated_holes

def detect_ball_in_hole(image, hole_coords, game_state, frame_count, scale_x=1.0, scale_y=1.0):
    global lower_white, upper_white, lower_red, upper_red
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    mask_red = cv2.inRange(hsv, lower_red, upper_red)

    kernel = np.ones((5, 5), np.uint8)
    mask_white = cv2.erode(mask_white, kernel, iterations=1)
    mask_white = cv2.dilate(mask_white, kernel, iterations=1)
    mask_red = cv2.erode(mask_red, kernel, iterations=1)
    mask_red = cv2.dilate(mask_red, kernel, iterations=1)

    ball_positions = []
    points_list = []
    is_red_list = []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected_balls = set()
    for contour in contours:
        area = cv2.contourArea(contour)
        min_area = 0.05 * np.pi * 20 * 20 * (scale_x * scale_y)
        if min_area < area < np.pi * 20 * 20 * (scale_x * scale_y):
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(approx) > 4:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    ball_x = int(M["m10"] / M["m00"])
                    ball_y = int(M["m01"] / M["m00"])
                    ball_pos = (ball_x, ball_y)
                    rounded_x = round(ball_x / 10) * 10
                    rounded_y = round(ball_y / 10) * 10
                    ball_id = f"{rounded_x},{rounded_y}"

                    ball_y = max(2, min(ball_y, image.shape[0] - 3))
                    ball_x = max(2, min(ball_x, image.shape[1] - 3))

                    nearest_hole = game_state.get_nearest_hole(ball_pos, scale_x, scale_y)
                    if nearest_hole:
                        x, y, radius, points, is_oblong, rect = nearest_hole
                        hole_pos = (x, y)

                        if hole_pos in game_state.detection_cooldown:
                            if frame_count - game_state.detection_cooldown[hole_pos] < COOLDOWN_FRAMES:
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
                                if frames + 1 >= CONFIRMATION_FRAMES:
                                    region = image[max(0, ball_y-10):min(image.shape[0], ball_y+10),
                                                  max(0, ball_x-10):min(image.shape[1], ball_x+10)]
                                    hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
                                    red_mask_region = cv2.inRange(hsv_region, lower_red, upper_red)
                                    red_pixel_count = cv2.countNonZero(red_mask_region)
                                    total_pixels = region.shape[0] * region.shape[1]
                                    is_red = red_pixel_count > (total_pixels * 0.3)

                                    final_points = points * 2 if is_red or game_state.power_up == "Double Points" else points

                                    if is_oblong and rect:
                                        x1, y1, x2, y2 = rect
                                        if x1 <= ball_x <= x2 and y1 <= ball_y <= y2:
                                            ball_positions.append(hole_pos)
                                            points_list.append(final_points)
                                            is_red_list.append(is_red)
                                            game_state.scored_balls.add(hole_pos)
                                            game_state.detection_cooldown[hole_pos] = frame_count
                                            print(f"Confirmed ball at {hole_pos}, Points: {final_points} (Oblong, Red: {is_red})")
                                    else:
                                        if circularity > 0.7:
                                            ball_positions.append(hole_pos)
                                            points_list.append(final_points)
                                            is_red_list.append(is_red)
                                            game_state.scored_balls.add(hole_pos)
                                            game_state.detection_cooldown[hole_pos] = frame_count
                                            print(f"Confirmed ball at {hole_pos}, Points: {final_points} (Circular, Red: {is_red})")

                                    hole_index = next((i for i, h in enumerate(game_state.hole_positions) if h[0] == x and h[1] == y), -1)
                                    if hole_index == 0 and not is_red:
                                        game_state.activate_power_up("Extra Ball")
                                    elif hole_index == 1 and is_red:
                                        game_state.activate_power_up("Double Points")

                                    del game_state.confirming_balls[ball_id]
                            else:
                                game_state.confirming_balls[ball_id] = {
                                    "position": (ball_x, ball_y), "frames": 1, "hole_pos": hole_pos
                                }
                        else:
                            game_state.confirming_balls[ball_id] = {
                                "position": (ball_x, ball_y), "frames": 1, "hole_pos": hole_pos
                            }

                        if hole_pos not in game_state.detected_positions:
                            game_state.detected_positions.append(hole_pos)
                        detected_balls.add(ball_id)
                    else:
                        if ball_id in game_state.confirming_balls:
                            hole_pos = game_state.confirming_balls[ball_id]["hole_pos"]
                            del game_state.confirming_balls[ball_id]
                            if hole_pos in game_state.detected_positions:
                                game_state.detected_positions.remove(hole_pos)
                else:
                    continue

    for ball_id in list(game_state.confirming_balls.keys()):
        if ball_id not in detected_balls:
            hole_pos = game_state.confirming_balls[ball_id]["hole_pos"]
            del game_state.confirming_balls[ball_id]
            if hole_pos in game_state.detected_positions:
                game_state.detected_positions.remove(hole_pos)

    return ball_positions, points_list, is_red_list

font = pygame.font.Font(None, 36)
def draw_ui():
    current_width, current_height = screen.get_size()
    status_surface = pygame.Surface((current_width, STATUS_BAR_HEIGHT))
    status_surface.fill(GRAY)
    score_text = font.render(f"Balls: {game.balls}  Score: {game.score}  Time: {game.time}  Power-Up: {game.power_up or 'None'}", True, WHITE)
    status_surface.blit(score_text, (10, 10))
    screen.blit(status_surface, (0, current_height - STATUS_BAR_HEIGHT))

def get_initials(screen, font):
    initials = ""
    input_active = True
    input_surface = pygame.Surface((200, 100), pygame.SRCALPHA)
    input_surface.fill((200, 200, 200, 200))
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
        text = font.render("Enter Initials: " + initials, True, BLACK)
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
fade_start_time = None
camera_ready = False
first_frame = None

print("Initializing camera...")
if not reinitialize_camera():
    print("Failed to initialize camera. Exiting...")
    sys.exit()

print("Loading calibrated holes...")
game.hole_positions = load_calibrated_holes()

print("Forcing camera reinitialization before game loop...")
if not reinitialize_camera():
    print("Failed to reinitialize camera. Exiting...")
    sys.exit()

camera_ready = True
fade_start_time = pygame.time.get_ticks()

while running:
    try:
        if focus_lost:
            pygame.display.set_caption("Whiffle Playfield - Click to Focus")
            for event in pygame.event.get():
                if event.type == pygame.ACTIVEEVENT and event.gain == 1:
                    focus_lost = False
                    pygame.display.set_caption("Whiffle Playfield")
                    if DEBUG:
                        print("Focus regained.")
                continue

        if not cap.isOpened():
            print("Camera not open. Reinitializing...")
            if not reinitialize_camera():
                print("Failed to reinitialize camera. Exiting...")
                break
            retry_count = 0

        ret, frame = cap.read()
        if not ret:
            print(f"Failed to capture frame. Retry {retry_count + 1}/{max_retries}")
            retry_count += 1
            if retry_count >= max_retries:
                print("Max retries reached. Reinitializing camera...")
                if not reinitialize_camera():
                    print("Failed to reinitialize camera. Exiting...")
                    break
            time.sleep(0.1)
            continue

        retry_count = 0
        if frame is None or frame.size == 0 or frame.shape != (INITIAL_HEIGHT, INITIAL_WIDTH, 3) or frame.mean() < 1:
            print(f"Invalid frame: Shape: {frame.shape if frame is not None else 'None'}, Mean: {frame.mean() if frame is not None else 'N/A'}")
            frame = np.zeros((INITIAL_HEIGHT, INITIAL_WIDTH, 3), dtype=np.uint8)

        if first_frame is None:
            first_frame = frame.copy()

        current_width, current_height = screen.get_size()
        aspect_ratio = INITIAL_WIDTH / INITIAL_HEIGHT
        target_height = current_height - MENU_HEIGHT - STATUS_BAR_HEIGHT
        target_width = int(target_height * aspect_ratio)
        if target_width > current_width:
            target_width = current_width
            target_height = int(target_width / aspect_ratio)
        scale_x = target_width / INITIAL_WIDTH
        scale_y = target_height / INITIAL_HEIGHT
        scaled_frame = cv2.resize(frame, (target_width, target_height))
        roi = scaled_frame
        for (x, y, radius, points, is_oblong, rect) in game.hole_positions:
            scaled_x = int(x * scale_x)
            scaled_y = int(y * scale_y)
            scaled_radius = int(radius * scale_x)
            cv2.circle(roi, (scaled_x, scaled_y), scaled_radius, (0, 255, 0), 2)
            cv2.putText(roi, str(points), (scaled_x - 20, scaled_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            if is_oblong and rect:
                x1, y1, x2, y2 = rect
                scaled_x1 = int(x1 * scale_x)
                scaled_y1 = int(y1 * scale_y)
                scaled_x2 = int(x2 * scale_x)
                scaled_y2 = int(y2 * scale_y)
                cv2.rectangle(roi, (scaled_x1, scaled_y1), (scaled_x2, scaled_y2), (0, 255, 0), 2)

        if game.just_reset:
            game.just_reset = False
            game.detected_positions.clear()
            game.confirming_balls.clear()
        else:
            ball_positions, points_list, is_red_list = detect_ball_in_hole(roi, game.hole_positions, game, frame_count, scale_x, scale_y)
            for pos, points, is_red in zip(ball_positions, points_list, is_red_list):
                game.score += points
                game.balls -= 1
                print(f"Ball scored at {pos}, Points: {points} (Red: {is_red}), Score: {game.score}, Balls: {game.balls}")
                current_time = time.time()
                if score_sound and (current_time - game.last_sound_time) >= SOUND_COOLDOWN:
                    score_sound.play()
                    game.last_sound_time = current_time

        frame_to_display = roi if roi is not None else np.zeros((target_height, target_width, 3), dtype=np.uint8)
        if frame_to_display.size == 0 or frame_to_display.shape != (target_height, target_width, 3):
            print("Frame invalid, using fallback...")
            frame_to_display = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        frame_rgb = cv2.cvtColor(frame_to_display, cv2.COLOR_BGR2RGB)
        pygame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
        scaled_surface = pygame.transform.scale(pygame_surface, (target_width, target_height))

        screen.fill(BLACK)
        playfield_offset_x = (current_width - target_width) // 2
        playfield_offset_y = MENU_HEIGHT
        screen.blit(scaled_surface, (playfield_offset_x, playfield_offset_y))

        menu.draw(screen)
        draw_ui()

        for pos in game.detected_positions:
            adjusted_pos = (pos[0] + playfield_offset_x, pos[1] + playfield_offset_y)
            if any(pos == game.confirming_balls[ball_id]["hole_pos"] for ball_id in game.confirming_balls
                   if game.confirming_balls[ball_id]["frames"] < CONFIRMATION_FRAMES):
                pygame.draw.circle(screen, YELLOW, adjusted_pos, int(20 * scale_x), 2)
            else:
                pygame.draw.circle(screen, BLUE if any(pos == game.confirming_balls[ball_id]["hole_pos"] for ball_id in game.confirming_balls
                                                    if cv2.mean(roi[max(0, int(pos[1]/scale_y)-2):min(roi.shape[0], int(pos[1]/scale_y)+3),
                                                                  max(0, int(pos[0]/scale_x)-2):min(roi.shape[1], int(pos[0]/scale_x)+3)])[2] > 100) else RED,
                                 adjusted_pos, int(20 * scale_x), 2)

        for (x, y, _, points, is_oblong, rect) in game.hole_positions:
            scaled_x = int(x * scale_x)
            scaled_y = int(y * scale_y)
            hole_pos = (scaled_x, scaled_y)
            if is_oblong and rect and hole_pos in game.scored_balls:
                x1, y1, x2, y2 = rect
                scaled_x1 = int(x1 * scale_x) + playfield_offset_x
                scaled_y1 = int(y1 * scale_y) + playfield_offset_y
                scaled_x2 = int(x2 * scale_x) + playfield_offset_x
                scaled_y2 = int(y2 * scale_y) + playfield_offset_y
                pygame.draw.rect(screen, RED, (scaled_x1, scaled_y1, scaled_x2 - scaled_x1, scaled_y2 - scaled_y1), 2)

        about_window.draw(screen)
        settings_window.draw(screen)
        leaderboard_window.draw(screen)

        if splash_screen_active:
            current_time = pygame.time.get_ticks()
            elapsed = current_time - fade_start_time
            if elapsed >= fade_duration:
                splash_alpha = 0
                splash_screen_active = False
            else:
                splash_alpha = 255 * (1 - elapsed / fade_duration)
            splash_copy = splash_image.copy()
            splash_copy.set_alpha(int(splash_alpha))
            splash_copy = pygame.transform.smoothscale(splash_copy, (current_width, current_height))
            screen.blit(splash_copy, (0, 0))

        pygame.display.flip()
        clock.tick(30)

        frame_count += 1
        if frame_count % 30 == 0:
            game.time = time.strftime("%H:%M:%S")
        
        game.update_power_up()

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == pygame.ACTIVEEVENT:
                if event.gain == 0 and event.state == 2:
                    focus_lost = True
                    print("Focus lost. Click to regain focus.")
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

        if game.balls <= 0:
            print("Saving score to leaderboard...")
            initials = get_initials(screen, font)
            if initials:
                score = game.score
                date = time.strftime("%Y-%m-%dT%H:%M:%S")
                leaderboard_window.save_score(initials, score, date)
                leaderboard_window.load_scores()  # Refresh leaderboard after saving
            game.reset()

    except Exception as e:
        print(f"Crash occurred: {e}")
        import traceback
        traceback.print_exc()
        break

pygame.mixer.music.stop()
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()