Below is a `README.md` file for the Whiffle Tracker project, reflecting the updated project structure, changes made during the code review, and providing clear instructions for setup, usage, and development. The README includes an overview of the project, installation instructions, usage guide, project structure, dependencies, and additional notes for contributors.

---

# Whiffle Tracker

Whiffle Tracker is a computer vision-based game that tracks whiffle balls in real-time using a webcam, allowing players to score points by getting balls into designated scoring zones. The game features ball detection (white and red balls), tracking, scoring, a menu system with settings and leaderboard, and audio feedback. It uses OpenCV for computer vision, Pygame for audio, and Supabase for online leaderboard storage.

## Features
- **Ball Detection and Tracking**: Detects white and red whiffle balls using HSV color filtering and tracks them across frames with consistent IDs.
- **Scoring Zones**: Players can define scoring zones with custom point values, and balls entering these zones score points.
- **Menu System**: Interactive menu with options to start a new game, save/load scoring zones, toggle settings (e.g., sounds, music, ball detection), view help/FAQ, and check the leaderboard.
- **Leaderboard**: Supports both online (via Supabase) and local leaderboard storage, displaying the top 5 scores for each game mode.
- **Audio Feedback**: Plays background music and a sound effect when a ball scores.
- **Splash Screen**: Displays a splash screen with a fade effect on startup.
- **Debug Mode**: Toggle debug mode to log detailed information for development and troubleshooting.

## Installation

### Prerequisites
- **Python 3.8+**: Ensure Python is installed on your system.
- **Webcam**: A webcam is required for real-time video capture.
- **Assets**:
  - `background_music.mp3`: Background music file.
  - `logo.png`: Logo for the About menu.
  - `splash.png`: Splash screen image.
  - `ding.wav`: Sound played when a ball scores.
  Place these files in the project root directory.

### Dependencies
Install the required Python packages using `pip`:

```bash
pip install opencv-python pygame requests python-dotenv
```

### Setup
1. **Clone the Repository** (if applicable):
   ```bash
   git clone <repository-url>
   cd whiffle-tracker
   ```

2. **Set Up Environment Variables**:
   The project uses Supabase for online leaderboard storage. Create a `.env` file in the project root directory with your Supabase credentials:
   ```
   SUPABASE_URL=https://your-supabase-url.supabase.co
   SUPABASE_KEY=your-supabase-api-key
   ```
   Replace `your-supabase-url` and `your-supabase-api-key` with your actual Supabase URL and API key. If you don’t have a Supabase account, you can sign up at [Supabase](https://supabase.com/) and create a project. The leaderboard will fall back to local storage if online access fails.

3. **Ensure Assets Are Present**:
   Verify that the required assets (`background_music.mp3`, `logo.png`, `splash.png`, `ding.wav`) are in the project root directory. If any are missing, the game will log an error and may skip certain features (e.g., audio playback).

## Usage

1. **Run the Game**:
   From the project root directory, run:
   ```bash
   python game.py
   ```
   The game will start with a splash screen, then display the main game window.

2. **Controls**:
   - **q**: Quit the game.
   - **s**: Start drawing a scoring zone. Drag to define the zone, release to set points using the trackbar, press Enter to confirm, or 'c' to cancel.
   - **d**: Toggle debug mode (logs detailed information to the console).
   - **Escape**: Close the menu if it’s open.
   - **Mouse**:
     - Click "Click for Menu" to open the menu.
     - Drag the menu title bar to move the menu window.
     - Click menu items to access submenus (e.g., File, Settings, Help, FAQ, About, Leaderboard).
     - In the Settings submenu, toggle options like game sounds, background music, and ball detection.

3. **Gameplay**:
   - Define scoring zones using the 's' key.
   - Throw whiffle balls into the scoring zones to score points.
   - Check your score and high score in the top-left corner.
   - Use the menu to start a new game, save/load zones, or view the leaderboard.

## Project Structure

The project is organized into several modules, each handling a specific aspect of the game:

- **constants.py**: Centralized constants (colors, game settings, detection parameters, etc.).
- **detection.py**: Detects white and red balls using HSV color filtering and contour detection.
- **tracking.py**: Tracks balls across frames, assigning consistent IDs.
- **scoring.py**: Manages scoring zones (defining, validating, drawing).
- **menu.py**: Handles the menu system (resetting game, saving/loading zones, drawing menu).
- **leaderboard.py**: Manages the leaderboard (online via Supabase, local via JSON).
- **utils.py**: Utility functions (mouse event handling, clean exit).
- **game.py**: Main game loop, integrating all modules.
- **Assets**:
  - `scoring_zones.json`: Stores scoring zones (created/updated during gameplay).
  - `background_music.mp3`: Background music.
  - `logo.png`: Logo for the About menu.
  - `splash.png`: Splash screen image.
  - `ding.wav`: Sound played when a ball scores.
  - `whiffle_leaderboard.json`: Local leaderboard storage (created/updated during gameplay).

## Development

### Code Overview
- **Ball Detection**: Uses OpenCV’s HSV color filtering to detect white and red balls, with morphological operations to handle close balls and small ball tracking for consistency.
- **Tracking**: Assigns unique IDs to balls and tracks them across frames using proximity-based matching.
- **Scoring**: Players define scoring zones with point values; balls entering these zones score points once per ball.
- **Menu System**: An overlay menu with submenus for game control, settings, help, FAQ, about, and leaderboard.
- **Leaderboard**: Stores top 5 scores per mode (classic, timed) online via Supabase and locally in a JSON file.
- **Error Handling**: Improved error handling for camera failures, asset loading, and Supabase requests.
- **Performance**: Optimized by sharing HSV conversion between white and red ball detection, limiting ball trail lengths, and caching static UI elements where possible.

### Contributing
1. **Code Style**:
   - Follow PEP 8 guidelines for Python code.
   - Use type hints for function parameters and return values.
   - Add docstrings for all modules, classes, and functions.
   - Use the existing logger (`logging.getLogger(__name__)`) for logging.

2. **Adding Features**:
   - To add new menu items, update the `menu_items` list in `GameState` (consider making this data-driven in `constants.py`).
   - To add new settings, update the `settings_items` list in `menu.py`.
   - To add new game modes, extend the leaderboard logic in `leaderboard.py` and update the UI in `menu.py`.

3. **Testing**:
   - The project currently lacks unit tests. Consider adding tests using `unittest` or `pytest` for modules like `detection.py`, `tracking.py`, and `scoring.py`.
   - Test with different lighting conditions to ensure ball detection works reliably.

4. **Performance Optimization**:
   - Cache the splash image in `GameState` to avoid reloading.
   - Optimize ball trail rendering by using a more efficient data structure (e.g., `collections.deque`).
   - Use a spatial data structure (e.g., KD-tree) in `tracking.py` if the number of balls increases significantly.

## Known Issues
- **Red Ball Detection**: Currently disabled by default (`red_ball_detection_on = False`) as it’s noted as "coming soon" in the FAQ. Enable it in the Settings menu for testing, but it may require tuning for different lighting conditions.
- **Camera Failures**: If the webcam fails to initialize, the game will exit with an error. Future improvements could include retry logic or a fallback mode.
- **Asset Loading**: Missing assets (e.g., `ding.wav`, `splash.png`) will log errors and skip features. Ensure all assets are present before running.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details (you may need to create this file if licensing is required).

## Credits
- **Ideas**: Blake Weibling
- **Coding Assistance**: Grok (xAI)

---

This `README.md` provides a comprehensive guide for users and developers, covering setup, usage, project structure, and development notes. You can place this file in the project root directory. If you need a `LICENSE` file or further assistance with testing or additional features, let me know!