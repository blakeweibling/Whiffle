"""
Game state management for the Whiffle Tracker project.
Defines the GameState class to manage game variables and state transitions.
"""

import cv2
import logging
import pygame
import time
import json
import os
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum

from constants import UIConstants, GameConstants, GameSpecificConstants  # Import classes
from detection import detect_white_balls
from tracking import track_balls
from menu import load_zones  # Updated to import from menu.py
from leaderboard import Leaderboard
from player import Player  # Import Player class
from achievement import Achievement  # Import Achievement class

logger = logging.getLogger(__name__)

class MenuState(Enum):
    CLOSED = "closed"
    MAIN = "main"
    SUBMENU = "submenu"

class GameState:
    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        self.cap: Optional[cv2.VideoCapture] = cv2.VideoCapture(0)
        self.camera_available: bool = True  # Flag to indicate if camera is available
        self.static_frame: Optional[np.ndarray] = None  # Store the static image if camera fails

        # Attempt to set camera properties and check resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, UIConstants.WINDOW_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, UIConstants.WINDOW_HEIGHT)
        width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if width != UIConstants.WINDOW_WIDTH or height != UIConstants.WINDOW_HEIGHT:
            logger.warning(f"Camera resolution {width}x{height} does not match {UIConstants.WINDOW_WIDTH}x{UIConstants.WINDOW_HEIGHT}")
        logger.info(f"Camera resolution: {width}x{height}")

        # Check if camera opened successfully
        if not self.cap.isOpened():
            logger.error("Failed to open camera, attempting to load static image")
            self.camera_available = False
            # Load static image as fallback
            self.static_frame = cv2.imread("last_frame.png")
            if self.static_frame is None:
                logger.error("Failed to load last_frame.png, cannot proceed without camera or static image")
                raise RuntimeError("Camera initialization failed and no static image available")
            # Resize static image to match window dimensions
            self.static_frame = cv2.resize(self.static_frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
            logger.info("Loaded static image last_frame.png as fallback")

        self.score: int = 0  # This will now be managed by the Player class
        self.high_score: int = 0
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = []
        self.tracked_balls: List[Tuple[int, int, float, int, int]] = []
        self.scored_balls: set = set()
        self.scored_positions: Dict[Tuple[int, int], int] = {}
        self.potential_small_balls_white: Dict[Tuple[int, int], Tuple[int, int]] = {}
        self.potential_small_balls_red: Dict[Tuple[int, int], Tuple[int, int]] = {}
        self.next_ball_id: int = 0
        self.frame_count: int = 0
        self.balls_in_zone: Dict[int, Optional[Tuple[int, int, int, int, int]]] = {}
        self.time_limit: int = GameConstants.DEFAULT_TIME_LIMIT
        self.game_timer: Optional[float] = None
        self.start_time: Optional[float] = None
        self.ball_trails: Dict[int, List[Tuple[int, int, int]]] = {}

        # Multiplayer support
        self.players: List[Player] = [Player("Player 1")]  # Start with one default player
        self.current_player_index: int = 0  # Index of the current player

        # Achievements support
        self.achievements: List[Achievement] = []
        self.achievement_notification: Optional[str] = None
        self.achievement_notification_timer: float = 0
        self._initialize_achievements()
        self._load_achievements()

        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self._initialize_sounds()

        self.leaderboard: Leaderboard = Leaderboard(supabase_url, supabase_key)

        self.game_sounds_on: bool = True
        self.background_music_on: bool = True
        self.red_ball_detection_on: bool = False
        self.white_ball_detection_on: bool = True

        self.toggle_background_music()

        self.drawing: bool = False
        self.start_x: int = -1
        self.start_y: int = -1
        self.temp_zone: Optional[Tuple[int, int, int]] = None
        self.drawing_mode: bool = False

        self.menu_state: MenuState = MenuState.CLOSED
        self.submenu_active: Optional[str] = None
        self.menu_items: List[Tuple[int, int, int, int, str, Optional[Callable[[], None]]]] = [
            (10, 140, 60, 30, "File", None),
            (90, 140, 80, 30, "Players", None),
            (190, 140, 80, 30, "Settings", None),
            (290, 140, 60, 30, "Help", None),
            (370, 140, 60, 30, "About", None),
            (450, 140, 100, 30, "Leaderboard", None),
            (570, 140, 100, 30, "Achievements", None)
        ]
        self.submenu_items: List[Any] = []
        self.menu_width: int = UIConstants.MENU_WIDTH
        self.menu_height: int = UIConstants.MENU_HEIGHT
        self.menu_pos_x: int = (UIConstants.WINDOW_WIDTH - self.menu_width) // 2
        self.menu_pos_y: int = (UIConstants.WINDOW_HEIGHT - self.menu_height) // 2
        self.dragging_menu: bool = False
        self.drag_start_x: int = 0
        self.drag_start_y: int = 0
        self.menu_active: bool = False  # Added menu_active attribute

        self.debug_mode: bool = False
        self.excluded_positions: List[Tuple[int, int]] = GameSpecificConstants.EXCLUDED_POSITIONS

        self.scoring_zones = load_zones(self.scoring_zones)
        self._initialize_balls_in_zone()

    def _initialize_sounds(self) -> None:
        pygame.mixer.init()
        try:
            self.score_sound = pygame.mixer.Sound("ding.wav")
        except pygame.error as e:
            logger.error(f"Failed to load score sound (ding.wav): {e}")
            self.game_sounds_on = False
        try:
            self.background_music = pygame.mixer.Sound("background_music.mp3")
            self.background_music.set_volume(GameConstants.DEFAULT_MUSIC_VOLUME)
        except pygame.error as e:
            logger.error(f"Failed to load background music (background_music.mp3): {e}")
            self.background_music_on = False

    def _initialize_balls_in_zone(self) -> None:
        if self.camera_available:
            ret, frame = self.cap.read()
            if not ret:
                logger.error("Failed to read initial frame for ball initialization")
                return
        else:
            frame = self.static_frame
            logger.info("Using static frame for ball initialization")

        detected_balls = detect_white_balls(frame, self.frame_count, self.potential_small_balls_white,
                                            self.excluded_positions, self.debug_mode)
        tracked_detected_balls, self.next_ball_id = track_balls(detected_balls, self.tracked_balls,
                                                               self.next_ball_id, self.frame_count,
                                                               self.scored_positions, self.debug_mode)
        self.tracked_balls = [(x, y, radius, ball_id, self.frame_count)
                              for x, y, radius, ball_id in tracked_detected_balls]
        for x, y, radius, ball_id, _ in self.tracked_balls:
            ball = (x, y, radius, ball_id)
            for zone in self.scoring_zones:
                if is_in_scoring_zone(ball, zone):
                    self.balls_in_zone[ball_id] = zone
                    if self.debug_mode:
                        logger.info(f"Ball ID {ball_id} at ({x}, {y}) already in zone {zone} at startup")
                    break
            if ball_id not in self.balls_in_zone:
                self.balls_in_zone[ball_id] = None

    def _initialize_achievements(self) -> None:
        """Initialize the list of achievements."""
        self.achievements = [
            Achievement("First Score", "Score your first points", lambda gs: gs.get_current_player().score >= 100),
            Achievement("High Roller", "Score 1000 points in one game", lambda gs: gs.get_current_player().score >= 1000),
            Achievement("Zone Master", "Create 5 scoring zones", lambda gs: len(gs.scoring_zones) >= 5),
            Achievement("Marathon", "Play 10 games", lambda gs: gs.get_current_player().games_played >= 10)
        ]

    def _load_achievements(self) -> None:
        """Load unlocked achievements from a file."""
        try:
            if os.path.exists("achievements.json"):
                with open("achievements.json", "r", encoding='utf-8') as f:
                    data = json.load(f)
                    for achievement in self.achievements:
                        if achievement.name in data and data[achievement.name]["unlocked"]:
                            achievement.unlocked = True
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load achievements: {e}")

    def _save_achievements(self) -> None:
        """Save unlocked achievements to a file."""
        try:
            data = {a.name: {"unlocked": a.unlocked} for a in self.achievements}
            with open("achievements.json", "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to save achievements: {e}")

    def get_current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    def switch_player(self) -> None:
        """Switch to the next player, saving the current player's score."""
        current_player = self.get_current_player()
        self.save_score(current_player.name, mode="classic")  # Save the current player's score
        current_player.reset_score()  # Reset score for the next game
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.scored_balls.clear()  # Clear scored balls for the new player
        self.scored_positions.clear()
        self.tracked_balls.clear()
        self.balls_in_zone.clear()
        self.ball_trails.clear()
        logger.info(f"Switched to player: {self.get_current_player().name}")

    def add_player(self, name: str) -> None:
        """Add a new player to the game."""
        self.players.append(Player(name))
        logger.info(f"Added player: {name}")

    def check_achievements(self) -> None:
        """Check all achievements and display notifications for newly unlocked ones."""
        for achievement in self.achievements:
            if achievement.check(self):
                self.achievement_notification = f"Achievement Unlocked: {achievement.name}"
                self.achievement_notification_timer = 3.0  # Display for 3 seconds
                self._save_achievements()
                if self.game_sounds_on and self.score_sound:
                    self.score_sound.play()
                logger.info(f"Achievement unlocked: {achievement.name}")

    def update_achievement_notification(self, delta_time: float) -> None:
        """Update the achievement notification timer."""
        if self.achievement_notification:
            self.achievement_notification_timer -= delta_time
            if self.achievement_notification_timer <= 0:
                self.achievement_notification = None
                self.achievement_notification_timer = 0

    def load_high_score(self) -> None:
        scores, _ = self.leaderboard.get_top_scores("classic", 1)
        self.high_score = scores[0]["score"] if scores else 0

    def save_score(self, player_name: str, mode: str = "classic") -> None:
        current_player = self.get_current_player()
        self.leaderboard.submit_score(player_name, current_player.score, mode)
        if current_player.score > self.high_score:
            self.high_score = current_player.score

    def toggle_background_music(self) -> None:
        if self.background_music is None:
            logger.warning("Background music not loaded, skipping toggle")
            return
        if self.background_music_on:
            if not pygame.mixer.get_busy():
                self.background_music.play(-1)
        else:
            self.background_music.stop()

    def update_timer(self) -> None:
        if self.game_timer is not None and self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.game_timer = max(0, self.time_limit - elapsed)