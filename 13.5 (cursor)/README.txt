# Whiffle Tracker

## Description

Whiffle Tracker is a computer vision-based application designed to detect, track, and score Whiffle balls using a camera feed[cite: 88, 243, 57]. It includes features for managing scoring zones, tracking player scores, managing achievements, and displaying leaderboards[cite: 52, 414, 448]. The application uses the YOLOv8 model for ball detection [cite: 57, 58] and OpenCV for video processing[cite: 3, 20, 243].

## Features

* **Ball Detection:** Detects white, red, and half-red/half-white Whiffle balls using a YOLOv8 model[cite: 57, 71].
* **Ball Tracking:** Assigns unique IDs to balls and tracks their movement across frames[cite: 713, 745].
* **Scoring Zones:** Allows users to define rectangular scoring zones with specific point values[cite: 561, 512]. Zones can be added, cleared, saved, loaded, and edited (points, position, size)[cite: 52, 691].
* **Scoring Logic:** Awards points when a ball comes to rest stably within a scoring zone, considering zone cooldowns and ball types (red/half give multipliers)[cite: 360, 373, 382]. Includes a 'Special Hole' mechanic (leftmost zone)[cite: 406].
* **Game Modes:** Supports different game modes like Classic and Timed[cite: 50, 613].
* **Player Management:** Supports multiple players, allowing name editing and selection[cite: 314, 640].
* **Leaderboard:** Submits scores to an online Supabase leaderboard and maintains a local fallback[cite: 448, 449].
* **Achievements:** Tracks and notifies users about unlocked achievements[cite: 1, 414, 355].
* **Menu System:** Provides an interactive menu for settings, zone management, game modes, players, leaderboard, achievements, help, and about sections[cite: 496, 52].
* **Configuration:** Uses environment variables (`.env` file) for Supabase credentials and optional camera configuration[cite: 88, 30].
* **Setup Script:** Includes a `setup.py` for building an executable using `cx_Freeze`[cite: 596].

## Key Files & Modules

* `game.py`: Main entry point for the application[cite: 88].
* `constants.txt`: Defines game constants, colors, file paths, and configurations[cite: 20].
* `game_state.txt`: Manages the overall state of the game (scores, zones, players, modes, etc.)[cite: 291].
* `game_loop.txt`: Contains the main game loop logic (frame capture, processing, rendering, input)[cite: 243].
* `game_input.txt`: Handles keyboard input for different game states[cite: 104].
* `detection.txt`: Implements ball detection using YOLOv8[cite: 57].
* `tracking.txt`: Implements ball tracking logic[cite: 713].
* `scoring.txt`: Handles scoring zone definition and checks[cite: 561].
* `leaderboard.txt`: Manages online (Supabase) and local leaderboards[cite: 448].
* `player.txt`: Defines the `Player` class[cite: 552].
* `achievement.txt`: Defines the `Achievement` class[cite: 1].
* `menu.txt`, `submenus.txt`, `menu_utils.txt`, `submenu_draw_functions.txt`: Handle menu rendering and logic[cite: 496, 600, 532, 629].
* `ui.txt`, `ui_elements.txt`, `ui_screens.txt`, `ui_utils.txt`: Manage UI drawing for different game states and elements[cite: 763, 800, 817, 886].
* `utils.txt`: Contains utility functions, including the main mouse callback[cite: 900].
* `cleanup_utils.txt`: Provides the `clean_exit` function for resource cleanup[cite: 3].
* `game_state_utils.txt`: Utility functions specifically for `GameState` initialization and state management[cite: 405].
* `setup.txt`: Script to build the application into an executable using `cx_Freeze`[cite: 596].

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
    * Make sure your Supabase project has a table named `whifflescores` (or adjust `TABLE_NAME` in `constants.txt` [cite: 50]) with columns like `player_name` (text), `score` (integer), `mode` (text), and `created_at` (timestamp).
4.  **YOLO Model:** Ensure the YOLO model file (`data/whiffle_new_best.pt` as mentioned in `detection.txt` [cite: 57, 58]) is present in the data directory.
5.  **Assets:** Ensure all required asset files (images like `assets/splash.png`, `assets/game_over.png`, sound files in the `data/sounds/` directory) are present.

## How to Run

Execute the main game script from the root directory:

```bash
python game.py