# Whiffle Tracker

## Description

Whiffle Tracker is a computer vision-based application designed to detect, track, and score Whiffle balls using a camera feed. It includes features for managing scoring zones, tracking player scores, managing achievements, and displaying leaderboards. The application uses the YOLOv8 model for ball detection and OpenCV for video processing. The game supports multiple resolutions and dynamic window sizing for optimal display.

## Features

* **Ball Detection:** Detects white, red, and half-red/half-white Whiffle balls using a YOLOv8 model.
* **Ball Tracking:** Assigns unique IDs to balls and tracks their movement across frames.
* **Scoring Zones:** Allows users to define rectangular scoring zones with specific point values. Zones can be added, cleared, saved, loaded, and edited (points, position, size).
* **Scoring Logic:** Awards points when a ball comes to rest stably within a scoring zone, considering zone cooldowns and ball types (red/half give multipliers). Includes a 'Special Hole' mechanic (leftmost zone).
* **Game Modes:** Supports multiple game modes:
  * Classic Mode: First to reach 2000 points wins
  * Timed Mode: 90-second time limit, first to 2000 points wins
  * Survival Mode: Starts with 45 seconds, gain 10 seconds per score, first to 2000 points wins
  * Retro Mode: Play with classic gameplay style
* **Player Management:** Supports multiple players, allowing name editing and selection.
* **Leaderboard:** Submits scores to an online Supabase leaderboard and maintains a local fallback.
* **Achievements:** Tracks and notifies users about unlocked achievements.
* **Menu System:** Provides an interactive menu for settings, zone management, game modes, players, leaderboard, achievements, help, and about sections.
* **Resolution Support:** Dynamic window sizing with support for multiple resolutions (1080p, 720p).
* **Configuration:** Uses environment variables (`.env` file) for Supabase credentials and optional camera configuration.
* **Setup Script:** Includes a `setup.py` for building an executable using `cx_Freeze`.
* **Video Recording:** Capture gameplay videos of high scores.
* **Social Integration:** Ability to upload gameplay videos to YouTube and Google Drive.
* **Screenshot Utility:** Take and save screenshots during gameplay.
* **Score Verification:** Submit screenshot proof with high scores.
* **Statistics & Heatmaps:** Track and visualize gameplay statistics.

## Key Files & Modules

* `game.py`: Main entry point for the application.
* `constants.py`: Defines game constants, colors, file paths, and configurations.
* `game_state.py`: Manages the overall state of the game (scores, zones, players, modes, etc.).
* `game_loop.py`: Contains the main game loop logic (frame capture, processing, rendering, input).
* `game_input.py`: Handles keyboard input for different game states.
* `detection.py`: Implements ball detection using YOLOv8.
* `tracking.py`: Implements ball tracking logic.
* `scoring.py`: Handles scoring zone definition and checks.
* `leaderboard.py`: Manages online (Supabase) and local leaderboards.
* `player.py`: Defines the `Player` class.
* `achievement.py`: Defines the `Achievement` class.
* `menu.py`, `submenus.py`, `menu_utils.py`, `submenu_draw_functions.py`: Handle menu rendering and logic.
* `ui.py`, `ui_elements.py`, `ui_screens.py`, `ui_utils.py`: Manage UI drawing for different game states and elements.
* `utils.py`: Contains utility functions, including the main mouse callback.
* `cleanup_utils.py`: Provides the `clean_exit` function for resource cleanup.
* `game_state_utils.py`: Utility functions specifically for `GameState` initialization and state management.
* `youtube_utils.py`: Handles YouTube video uploads.
* `google_drive_utils.py`: Manages Google Drive integration for file sharing.
* `screenshot_utils.py`: Handles screen capture functionality.
* `heatmap_utils.py`: Generates heatmaps of gameplay.
* `stats_calculator.py`: Calculates and tracks gameplay statistics.
* `replay_manager.py`: Manages gameplay recording and replay features.

## Installation & Setup

1. **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-folder>
    ```

2. **Install Dependencies:** Make sure you have Python installed. Then, install the required libraries using pip:
    ```bash
    pip install -r requirements.txt
    ```

3. **Configure Supabase:**
    * Create a `.env` file in the root directory.
    * Add your Supabase URL and Key:
        ```env
        SUPABASE_URL=https://your-supabase-url.supabase.co
        SUPABASE_KEY=your-supabase-anon-key
        ```
    * Make sure your Supabase project has a table named `whifflescores` with columns like `player_name` (text), `score` (integer), `mode` (text), and `created_at` (timestamp).

4. **Configure Google APIs (Optional):**
    * For YouTube uploads: Place your `client_secrets.json` file in the `configs/` directory.
    * For Google Drive integration: Place your Google API credentials in `configs/google_credentials.json`.

5. **YOLO Model:** Ensure the YOLO model file (`data/whiffle_new_best.pt`) is present in the data directory.

6. **Assets:** Ensure all required asset files (images like `assets/splash.png`, `assets/game_over.png`, sound files in the `data/sounds/` directory) are present.

## How to Run

Execute the main game script from the root directory:

```bash
python game.py
```

## Game Controls

* Press 'q' to quit at any time
* Press 'm' during gameplay to open the menu
* Use the resolution button to switch between different display resolutions
* Use the mouse to interact with menus and edit scoring zones