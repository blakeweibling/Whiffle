# Whiffle Tracker

## Description

Whiffle Tracker is a computer vision-based application designed to detect, track, and score Whiffle balls using a camera feed. It includes features for managing scoring zones, tracking player scores, managing achievements, and displaying leaderboards. The application uses the YOLOv8 model for ball detection and OpenCV for video processing.

## Features

* **Ball Detection:** Detects white, red, and half-red/half-white Whiffle balls using a YOLOv8 model.
* **Ball Tracking:** Assigns unique IDs to balls and tracks their movement across frames.
* **Scoring Zones:** Allows users to define rectangular scoring zones with specific point values. Zones can be added, cleared, saved, loaded, and edited (points, position, size).
* **Scoring Logic:** Awards points when a ball comes to rest stably within a scoring zone, considering zone cooldowns and ball types (red/half give multipliers). Includes a 'Special Hole' mechanic (leftmost zone).
* **Game Modes:** Supports different game modes like Classic and Timed.
* **Player Management:** Supports multiple players, allowing name editing and selection.
* **Leaderboard:** Submits scores to an online Supabase leaderboard and maintains a local fallback.
* **Achievements:** Tracks and notifies users about unlocked achievements.
* **Menu System:** Provides an interactive menu for settings, zone management, game modes, players, leaderboard, achievements, help, and about sections.
* **Configuration:** Uses environment variables (`.env` file) for Supabase credentials and optional camera configuration.
* **Setup Script:** Includes a `setup.py` for building an executable using `cx_Freeze`.

## Key Files & Modules

* `game.py`: Main entry point for the application.
* `constants.txt`: Defines game constants, colors, file paths, and configurations.
* `game_state.txt`: Manages the overall state of the game (scores, zones, players, modes, etc.).
* `game_loop.txt`: Contains the main game loop logic (frame capture, processing, rendering, input).
* `game_input.txt`: Handles keyboard input for different game states.
* `detection.txt`: Implements ball detection using YOLOv8.
* `tracking.txt`: Implements ball tracking logic.
* `scoring.txt`: Handles scoring zone definition and checks.
* `leaderboard.txt`: Manages online (Supabase) and local leaderboards.
* `player.txt`: Defines the `Player` class.
* `achievement.txt`: Defines the `Achievement` class.
* `menu.txt`, `submenus.txt`, `menu_utils.txt`, `submenu_draw_functions.txt`: Handle menu rendering and logic.
* `ui.txt`, `ui_elements.txt`, `ui_screens.txt`, `ui_utils.txt`: Manage UI drawing for different game states and elements.
* `utils.txt`: Contains utility functions, including the main mouse callback.
* `cleanup_utils.txt`: Provides the `clean_exit` function for resource cleanup.
* `game_state_utils.txt`: Utility functions specifically for `GameState` initialization and state management.
* `setup.txt`: Script to build the application into an executable using `cx_Freeze`.

## Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-folder>
    ```
2.  **Install Dependencies:** Make sure you have Python installed. Then, install the required libraries using pip:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Supabase:**
    * Create a `.env` file in the root directory.
    * Add your Supabase URL and Key:
        ```env
        SUPABASE_URL=[https://your-supabase-url.supabase.co](https://www.google.com/search?q=https://your-supabase-url.supabase.co)
        SUPABASE_KEY=your-supabase-anon-key
        ```
    * Make sure your Supabase project has a table named `whifflescores` (or adjust `TABLE_NAME` in `constants.txt`) with columns like `player_name` (text), `score` (integer), `mode` (text), and `created_at` (timestamp).
4.  **YOLO Model:** Ensure the YOLO model file (`whiffle_new_best.pt` as mentioned in `detection.txt`) is present in the root directory.
5.  **Assets:** Ensure all required asset files (images like `splash.png`, `game_over.png`, sound files in the `sounds/` directory) are present.

## How to Run

Execute the main game script from the root directory:

```bash
python game.py