# Whiffle Tracker

A computer vision application using Python, OpenCV, and YOLOv8 to detect and track whiffle balls for scoring purposes in various game modes.

## Overview

Whiffle Tracker uses a camera (or a static image fallback) to monitor a playfield. It employs a YOLOv8 model to detect different types of whiffle balls (white, red, half-red/half-white). Detected balls are tracked across frames, and scores are calculated when balls enter user-defined scoring zones. The application features multiple game modes, player management, configurable settings, an achievement system, and integrates with Supabase for online leaderboards.

## Features

* **Real-time Ball Detection:** Utilizes a custom-trained YOLOv8 model (`whiffle_new_best.pt`) to detect white, red, and half-red/half-white balls[cite: 151, 175, 176].
* **Ball Tracking:** Assigns persistent IDs to detected balls and tracks their movement across frames[cite: 581]. Optionally uses SciPy's KDTree for efficient matching if available[cite: 587].
* **Dynamic Scoring Zones:** Users can define rectangular scoring zones directly on the video feed using mouse clicks and drags [cite: 113, 381-386]. Zones can be saved, loaded, cleared, and edited (points value) via the menu [cite: 209, 210, 404-407, 528-536].
* **Multiple Game Modes:** Includes 'Classic', 'Timed', and 'Practice' modes affecting gameplay rules (e.g., timers, win conditions)[cite: 207, 408, 474, 481].
* **Scoring System:** Calculates scores based on which zone a ball enters and remains stable within[cite: 503]. Supports point multipliers for different ball types (Red x2, Half x1.5) [cite: 512, 513] and a 'Special Hole' bonus (leftmost zone) that doubles the final score if hit[cite: 116, 384, 509, 510].
* **Player Management:** Supports up to two players, allowing adding, selecting the current player, and editing player names [cite: 223, 411-419].
* **Online Leaderboard:** Integrates with Supabase to submit scores and retrieve top scores for different game modes[cite: 652, 679, 687]. Includes batch submission for efficiency[cite: 684].
* **Local Leaderboard Fallback:** Saves scores locally (`whiffle_leaderboard.json`) and uses this if the online leaderboard is unavailable[cite: 656, 692].
* **Achievement System:** Tracks and unlocks achievements based on game events (e.g., first score, creating zones)[cite: 199, 480, 500]. Status is saved locally (`achievements_status.json`)[cite: 481, 566].
* **Configuration Menu:** Allows users to toggle game sounds, background music, and visual/general debug modes via an in-game menu [cite: 201, 202-206].
* **Persistent Settings:** Saves/loads scoring zones, achievement status, high scores, and HSV color ranges locally using JSON files[cite: 465, 481, 482, 528, 566, 568].
* **UI Elements:** Displays scores, high scores, game mode, timers, player names, notifications, splash screens, and game over screens using OpenCV drawing functions[cite: 327].
* **Debug Overlays:** Optional overlays to visualize tracked balls, IDs, types, FPS, and game state for debugging[cite: 345, 366].

## Technology Stack

* **Python 3:** Core programming language.
* **OpenCV (`opencv-python`):** For camera interaction, image processing, UI drawing, and window management[cite: 178].
* **YOLOv8 (`ultralytics`):** For object (ball) detection[cite: 151].
* **Pygame:** For sound effect and background music playback[cite: 474, 553].
* **NumPy:** For numerical operations, especially with coordinates and image data.
* **Supabase:** Cloud backend for the online leaderboard (interacted with via Python `requests`).
* **python-dotenv:** For managing environment variables (Supabase credentials)[cite: 178].
* **Requests:** For making HTTP requests to the Supabase API[cite: 652].
* **(Optional) SciPy:** For potentially faster ball tracking using KDTree[cite: 581].

## Setup & Installation

1.  **Clone Repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```
2.  **Create Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
3.  **Install Dependencies:**
    * Create a `requirements.txt` file with the following contents:
        ```txt
        opencv-python
        ultralytics
        pygame
        numpy
        python-dotenv
        requests
        # scipy # Uncomment if you want to use KDTree tracking
        ```
    * Install using pip:
        ```bash
        pip install -r requirements.txt
        ```
4.  **YOLOv8 Model:** Obtain the trained model file `whiffle_new_best.pt` [cite: 151] and place it in the project's root directory (or update the path in `detection.py`).
5.  **Supabase Setup:**
    * Create a Supabase project.
    * Create a table (e.g., named `whifflescores` [cite: 655]) with columns like `player_name` (text), `score` (integer), `mode` (text), and `created_at` (timestamp with timezone). Ensure appropriate Row Level Security (RLS) policies are set if needed.
    * Create a `.env` file in the project root directory.
    * Add your Supabase URL and Anon Key to the `.env` file[cite: 178]:
        ```dotenv
        SUPABASE_URL=[https://your-project-ref.supabase.co](https://www.google.com/search?q=https://your-project-ref.supabase.co)
        SUPABASE_KEY=your-anon-key
        ```
6.  **Assets:** Ensure the following asset files are present:
    * `splash.png` (for the startup splash screen) [cite: 350]
    * `game_over.png` (for the game over screen) [cite: 339]
    * `sounds/ding.wav` (score sound) [cite: 554]
    * `sounds/background_music.mp3` (background music) [cite: 554]
    * (Optional) `last_frame.png` (if `USE_CAMERA` is False in `constants.py`) [cite: 465]

## Configuration

* **Core Settings:** Many game parameters (frame rate, colors, file paths, thresholds, volumes) can be adjusted in `constants.py`[cite: 624].
* **Camera:** Camera index and backend preference are automatically detected but can be overridden via environment variables (`WHIFFLE_CAMERA_INDEX`, `WHIFFLE_CAMERA_BACKEND`) or modified in `constants.py`.
* **Saved Data:** The application saves and loads data from JSON files:
    * `scoring_zones.json` [cite: 465]
    * `achievements_status.json` [cite: 465]
    * `hsv_ranges.json` [cite: 465]
    * `high_scores.json` [cite: 465]
    * `whiffle_leaderboard.json` (local fallback) [cite: 655]

## Usage

1.  Activate your virtual environment (if using one).
2.  Run the main script:
    ```bash
    python game.py
    ```
3.  **Key Controls:**
    * `m`: Toggle the main menu.
    * `s`: Start/Stop drawing a new scoring zone (when not in menu). Click and drag to define the rectangle, release to finish.
    * `p`: Pause/Resume the game (when playing).
    * `d`: Toggle general debug logging verbosity.
    * `b`: Toggle the visual debug overlay (bounding boxes, IDs).
    * `q` or `ESC`: Quit the application (or navigate back/cancel in menus).
    * `BACKSPACE`: Navigate back in menus or close the main menu.
    * `0-9`: Input points when editing scoring zones via the menu[cite: 269].
    * `A-Z, 0-9, Space`: Input characters when editing player names via the menu[cite: 284].
    * `ENTER`: Confirm input (zone points, player name)[cite: 273, 287].
    * `n`: Start a New Game from the Game Over screen[cite: 313].
    * `l`: Go to Leaderboard from the Game Over screen[cite: 315].

## Project Structure (Simplified)