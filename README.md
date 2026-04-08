# Whiffle Tracker — v15.7

## Description

Whiffle Tracker is a computer vision-based application designed to detect, track, and score Whiffle balls using a camera feed. It features advanced ball detection, multiple game modes and layouts (Whiffle and Five Star), a robust replay system, online and local leaderboards, per-player achievements, and social sharing. The application uses YOLOv8 models for ball detection and OpenCV for video processing. The game supports multiple resolutions and dynamic window sizing for optimal display.

## Features

* **Ball Detection:** Detects white, red, and half-red/half-white Whiffle balls using YOLOv8 or Silver and Gold balls for Fivestar (separate models for Whiffle and Five Star layouts).
* **Ball Tracking:** Assigns unique IDs to balls and tracks their movement across frames.
* **Scoring Zones:** Define, edit, and manage rectangular scoring zones with specific point values.
* **Scoring Logic:** Awards points when a ball comes to rest in a scoring zone, with multipliers for special ball types and a "Special Hole" mechanic.
* **Layouts:** Switch between Whiffle and Five Star from the menu (Layout). When you change layout, the correct YOLO model and scoring zones are reloaded so scoring stays correct after switching back.
  * **Whiffle:** Standard playfield; win score 2000 in classic/timed/survival.
  * **Five Star:** Alternate playfield; win score 5000. Uses dedicated zones (`data/game/fivestar_scoring_zones.json`) and model (`data/whiffle_new_best_fivestar.pt`). Static image (`assets/static_fivestar.png`) when no camera.
* **Game Modes:**
  * **Classic Mode:** First to reach the layout win score (2000 Whiffle / 5000 Five Star) wins. No game-over screen; win is recorded and game continues.
  * **Timed Mode:** 90-second time limit. **Game over only when time runs out** (not when reaching win score).
  * **Survival Mode:** Starts with 45 seconds, gain 10 seconds per score; same win score rules. Game over when time runs out.
  * **Retro Mode:** Classic gameplay with retro visuals and effects.
  * **Fun Mode:** Enhanced visuals and effects.
  * **Practice Mode:** Play without score limits or time pressure.
  * **Versus Mode:** Two players alternate turns; highest score wins, with results screen and stats comparison.
* **Replay System:** Record, browse, play back, and manage replays; share to YouTube, Google Drive, and Discord; highlight extraction and storage management. Delete requires confirmation (click Delete twice).
* **Player Management:** Multiple players with name editing and selection. Achievements and play history are stored **per player** (`data/achievements/achievements_status.json`, `data/achievements/play_dates.json`).
* **Leaderboard:** Online Supabase leaderboard with local fallback.
* **Achievements:** Per-player achievement tracking. Achievements list is **scrollable with the mouse wheel**; a scroll indicator appears on the side when there are more achievements than fit on screen. Unlocked achievements show the layout they were earned in (Whiffle or Five Star). Includes Victory Lap, Legend (3000 pts), Lucky Shot, Hole Hunter (special hole 2 times in one game), Architect, Tinkerer, Dual Threat, Against the Clock, Survivor, Mode Hopper, Triple Crown, Regular, Dedicated, Week Warrior, Recorded, Show Off, Highlight Reel, On the Board, Proof, Analyst, Inclusive, Take a Breather, Red Hot, Split Decision, Multiplier Master, and more.
* **High-Score Proof:** Screenshots for score verification; only the **last 5** proof images are kept (`high_score_proof` folder).
* **Menu System:** Interactive menus for settings, zone management, game modes, layouts, players, leaderboard, achievements (scrollable, mouse wheel), help, and about.
* **Resolution Support:** Dynamic window sizing; bottom-bar "1080p (click)" / "720p (click)" button cycles between 1080p and 720p.
* **Configuration:** `.env` for Supabase; `configs/` for HSV, settings, Google credentials.
* **Session Logging & Statistics:** Session stats, heatmaps, and data logging.
* **Operator Remote:** Built-in local-network web remote with PIN login, live status polling, round controls, player management, setup toggles, leaderboard and heatmap access, and installable PWA support for phones/tablets. Sessions expire automatically and access is limited to loopback/private-network clients.
* **Building:** **PyInstaller** (`game.spec`) produces a minimal "Whiffle" folder (onedir) with `Whiffle.exe` and `_internal` (Python runtime, torch, ultralytics, PIL, matplotlib, bundled data). See `BUILD_WHIFFLE.md`. **Inno Setup** (`WhiffleSetup.iss`) copies the entire folder and runs `icacls` so the install directory is read/write for saving configs, scores, and zones.
* **Video Recording, Social Integration, Screenshot Utility:** Capture and share gameplay; upload to YouTube, Google Drive, Discord; score verification with screenshots.
* **Loading Screen:** Loading screen during initialization (Windows); skipped on Linux/macOS.
* **XP System:** Player XP and leveling (`xp_system.py`, `player_xp.json`).

## Key Files & Modules

| File | Purpose |
|------|---------|
| `game.py` | Main entry point |
| `constants.py` | Game constants, file paths (e.g. `FIVESTAR_ZONES_FILE`, `FIVESTAR_MODEL_PATH`, `STATIC_FIVESTAR_FRAME_FILE`), win scores |
| `game_state.py` | Game state (scores, zones, players, modes, layouts, `win_score`); `set_playfield()` reloads detector and zones when switching layouts |
| `game_loop.py` | Main loop (frame capture, processing, input) |
| `game_input.py` | Keyboard and pygame input |
| `utils.py` | Mouse callback (including OpenCV mouse wheel for achievements submenu) |
| `detection.py` | YOLOv8 ball detection (Whiffle and Five Star models) |
| `tracking.py` | Ball tracking |
| `scoring.py`, `scoring_logic.py` | Zone checks and scoring; win condition sets `win_condition_met` and saves score but does **not** trigger game over |
| `game_state_utils.py` | `update_scoring`, `update_timers_and_state` (timer expiry → GAME_OVER only in timed mode), `reset_game` (win_score by layout), achievements load/save per player, `record_game_completed`, play_dates for Week Warrior |
| `game_state_helpers.py` | Notifications, sound, zone save/load, screenshot upload |
| `achievement.py` | Achievement definitions and check; `unlocked_layout` (Whiffle/Five Star) for display |
| `leaderboard.py` | Supabase and local leaderboards |
| `player.py` | Player class; XP integration (`xp_system`) |
| `menu.py`, `submenus.py`, `menu_utils.py`, `submenu_draw_functions.py` | Menu and submenu drawing; achievements submenu scroll (mouse wheel, scroll indicator) |
| `interaction_utils.py` | Menu/modal clicks and actions |
| `ui.py`, `ui_elements.py`, `ui_screens.py`, `ui_utils.py` | UI and game-over screen |
| `cleanup_utils.py` | `clean_exit` |
| `youtube_utils.py`, `google_drive_utils.py` | YouTube and Google Drive |
| `screenshot_utils.py` | Screenshots and high_score_proof purge (keep last 5) |
| `heatmap_utils.py`, `stats_calculator.py`, `data_logger.py` | Heatmaps, stats, logging |
| `replay_manager.py`, `versus_mode.py` | Replays and versus mode |
| `operator_remote.py` | Local operator web server, PIN auth, remote status snapshot, and browser-based game controls |
| `loading_screen.py` | Loading screen wrapper |
| `xp_system.py` | Player XP and levels |
| `extract_frames.py`, `create_yolo_dataset.py`, `prepare_yolo_dataset.py` | Video frame extraction and YOLO dataset preparation for training |
| `train_yolo_model.py` | YOLOv8 training (detect or segment); supports `--task segment`, `--device 0` for GPU |

## Data & Config Files

* `data/achievements/achievements_status.json` — Per-player achievement state (unlocked, layout)
* `data/achievements/play_dates.json` — Per-player play dates (e.g. Week Warrior)
* `data/game/scoring_zones.json` — Whiffle zones
* `data/game/fivestar_scoring_zones.json`, `scoring_zones_fivestar.json` — Five Star zones
* `data/whiffle_new_best.pt` — Whiffle YOLO model
* `data/whiffle_new_best_fivestar.pt` — Five Star YOLO model
* `data/scores/` — `high_scores.json`, `whiffle_leaderboard.json`
* `data/sounds/` — Sound and music files
* `configs/` — `hsv_ranges.json`, `settings.json`, Google credentials, `token.pickle`
* `configs/settings.json` — Includes `operator_remote_enabled`, `operator_remote_port`, and `operator_remote_pin` for the local web remote
* `assets/` — Splash, `game_over`, `static_fivestar`, menu/top bar images, `pinball_icon`

## Installation & Setup

1. **Clone and install:**
   * Python 3.10 or higher required.
   ```bash
   git clone <your-repository-url>
   cd <repository-folder>
   pip install -r requirements.txt
   ```

2. **Supabase:** Create `.env` with `SUPABASE_URL` and `SUPABASE_KEY`. Ensure table `whifflescores` with columns `player_name`, `score`, `mode`, `created_at`.

3. **Google APIs (optional):** `configs/client_secrets.json` for YouTube; `configs/google_credentials.json` for Drive.

4. **Discord (optional):** Add `discord_webhook_url` to `configs/settings.json`.

5. **YOLO models:** `data/whiffle_new_best.pt` (Whiffle); `data/whiffle_new_best_fivestar.pt` (Five Star).

6. **Assets:** Include all assets (splash, game_over, static_fivestar, etc.) and `data/sounds/`.

7. **Operator Remote (optional):** The remote starts automatically when `operator_remote_enabled` is `true`. Configure the listening port with `operator_remote_port` and set a non-default PIN with `operator_remote_pin` before using it on your local network.

8. **Platform notes (Raspberry Pi / Linux):** Runs without a camera; uses static frame (`assets/last_frame.png` or `assets/static_fivestar.png`) as fallback. Optional env vars: `WHIFFLE_CAMERA_INDEX`, `WHIFFLE_CAMERA_BACKEND`. Set `WHIFFLE_DEBUG=1` for verbose logging.

## How to Run

From the project root:

```bash
python game.py
```

**Launch flow:** After entering your player name, you'll see a **Select Playfield** screen. Press **1** or **W** for Whiffle, **2** or **F** for Five Star; **Enter**/**Esc** defaults to Whiffle. You can also switch layouts later from the menu (Layout).

## Operator Remote

When the game is running and the remote is enabled, Whiffle starts a small local web server for operator controls. Open the URL shown by the app, or browse to `http://<host-local-ip>:8765` if you are using the default port. Sign in with the configured operator PIN.

The remote is intended for phones, tablets, or another computer on the same LAN and includes:

* **Live Status:** Current player, score, state, mode, playfield, source, last remote action, and session countdown.
* **Round Control:** Update player name, add/select players, start or resume, pause, restart, open/close menu, show leaderboard, reset for next player.
* **Setup Controls:** Change game mode, playfield, music track, leaderboard mode, and toggle auto-record, debug overlay, colorblind mode, scoring UI, music, and sound effects.
* **Session Stats:** View duration, score rate, ball-type points, top scoring zones, and open/close the live-session heatmap when available.
* **Installable App:** Mobile browsers can install it as a standalone web app; an offline shell is cached so the UI can reopen cleanly while the host reconnects.

Security notes:

* Access is limited to loopback and private-network clients.
* Login uses a PIN stored in `configs/settings.json`.
* Sessions expire after 30 minutes of inactivity.
* Failed logins are rate-limited after repeated incorrect PIN attempts.

## Building the Whiffle Folder (for Installer)

```bash
pyinstaller game.spec --clean
```

Output: `dist/Whiffle/` with `Whiffle.exe` and `_internal/` (all dependencies). Use this entire folder as the "Whiffle" source for `WhiffleSetup.iss`; the installer copies everything including `_internal` and sets read/write permissions on the install dir. See `BUILD_WHIFFLE.md` for size-reduction options and openh264 DLL.

## Game Controls

* **q** — Quit
* **m** — Open menu during gameplay
* **Select Playfield (at launch):** **1** or **W** — Whiffle; **2** or **F** — Five Star; **Enter**/**Esc** — Whiffle (default)
* **Resolution button** (1080p/720p) — Click to cycle display resolution
* **Mouse** — Menus, zone editing, replay browsing
* **Mouse wheel** — Scroll the Achievements submenu (when in Achievements)
* **Versus Mode** — On-screen button to end turn
* Additional controls in specific modes (see in-game help)

## Training Your Own Model

Scripts are provided to extract frames from video, build a YOLO dataset, and train a custom model:

```bash
# Extract frames from video and create dataset in one step
python prepare_yolo_dataset.py data/replays/your_video.mp4 data/my_dataset --interval-seconds 5 --val-split 0.15 --classes silver gold --empty-labels

# Train (detection or segmentation); use --device 0 for GPU
python train_yolo_model.py --data data/my_dataset --task segment --classes silver gold --epochs 100 --device 0
```

Label images with CVAT.ai (YOLO 1.1 for boxes, YOLO Segmentation for polygons), then copy the trained `best.pt` to `data/whiffle_new_best.pt` or `data/whiffle_new_best_fivestar.pt`. See `train_yolo_model.py` for full options.

## Changes in v15.7

* **Playfield selection at launch:** After entering your name, choose Whiffle or Five Star; the correct model loads before gameplay.
* **Layout switching:** When switching between Whiffle and Five Star, the correct `.pt` model and scoring zones are reloaded; zones are cleared first so scoring is correct after switching back.
* **Game over:** Triggered in Timed and Survival modes when time runs out; reaching win score no longer shows game over (win is still recorded and saved).
* **Achievements:** Per-player storage; scrollable list with mouse wheel (OpenCV); layout label (Whiffle/Five Star) on unlocked achievements; Hole Hunter requires 2 special-hole scores; Legend at 3000 pts.
* **High-score proof:** Only the last 5 screenshots are kept in `high_score_proof`.
* **Raspberry Pi / Linux:** Platform-aware camera config; no-camera fallback to static frame; reduced error spam on startup.
* **Replay delete:** Requires confirmation (click Delete twice).
* **Operator Remote:** Added a built-in LAN operator dashboard with PIN login, live status, browser-based controls, session stats, and installable PWA support.
* **PyInstaller:** Onedir build (`Whiffle.exe` + `_internal`); hiddenimports for PIL, matplotlib, ultralytics, torch; openh264 DLL optional.
* **Inno Setup:** Single recursive copy of `dist/Whiffle` (including `_internal`); post-install `icacls` grants Users full control on install dir for saving configs, scores, zones; icon paths use `_internal\assets\pinball_icon.ico`.
