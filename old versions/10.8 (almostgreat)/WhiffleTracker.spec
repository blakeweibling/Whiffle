# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# --- Define Data Files ---
# List of tuples: (source_path, destination_in_bundle)
# '.' for destination means the root folder of the bundle.
added_files = [
    # Root directory files
    ('.env', '.'), # Consider if bundling .env is secure for your use case
    ('achievements.json', '.'),
    ('achievements_status.json', '.'),
    ('background_music.mp3', '.'),
    ('constants.py', '.'), # Include necessary .py files if not picked up as imports
    ('data.yaml', '.'),
    ('detection.py', '.'),
    ('ding.wav', '.'),
    # ('game.py', '.'), # Main script - already handled
    # ('game loop.py', '.'), # Include if used and not imported directly/indirectly
    ('game_over.png', '.'),
    ('game_state.py', '.'),
    ('game_state_utils.py', '.'),
    ('high_scores.json', '.'),
    ('hsv_ranges.json', '.'),
    ('input_handler.py', '.'),
    ('leaderboard.py', '.'),
    ('logo.png', '.'),
    ('menu.py', '.'),
    ('menu_utils.py', '.'),
    # ('pinball_icon.ico', '.'), # Already used as icon, usually not needed inside unless loaded explicitly
    ('pinball_icon.png', '.'),
    ('player.py', '.'),
    ('scoring.py', '.'),
    ('scoring_zones.json', '.'),
    ('splash.jpg', '.'),
    ('splash.png', '.'),
    ('static_frame.png', '.'),
    ('submenus.py', '.'),
    ('tracking.py', '.'),
    ('ui.py', '.'),
    ('utils.py', '.'), # The python file, not the folder
    ('whiffle_leaderboard.json', '.'),
    ('whiffle_new_best.pt', '.'), # Include the model file

    # Folders and their contents
    ('sounds', 'sounds') # Copies the entire 'sounds' folder
]

# --- Basic Setup ---
a = Analysis(
    ['game.py'], # <--- Your main script filename
    pathex=[],
    binaries=[],
    datas=added_files, # <--- USE THE POPULATED LIST HERE
    hiddenimports=[
        'pygame',
        'numpy',
        'cv2',
        'ultralytics',
        'scipy.spatial', # Helps PyInstaller find optional import if scipy NOT excluded
        'requests', # Keep if online leaderboard needed
        'setuptools', # Added, sometimes helps with pkg_resources issues
        'queue',
        'json',
        'logging',
        'datetime',
        'time',
        # Add any other modules PyInstaller might miss
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # --- Exclusions for Size Reduction ---
    excludes=[
        # --- Review These ---
        # Are you sure you don't need these? Test thoroughly!
        # If your app breaks, try removing some of these.

        # Definitely safe (if not used)
        'tkinter',
        'sqlite3',
        'PyQt5',
        'unittest',
        'pytest',
        'pydoc_data',
        'notebook',

        # Likely safe (Test!)
        #'dotenv', # Keep if you load .env at runtime *after* bundling

        # Optional (Performance/Size trade-off - Test!)
        #'scipy', # Excluded as tracking.py supposedly has a fallback? Verify this.

        # Optional (Feature Dependent - Uncomment if NO online leaderboard needed)
        #'requests',
        #'urllib3',
        #'chardet',
        #'idna',
        #'certifi',
        #'_ssl', # Keep if requests is kept for HTTPS
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# --- Build Executable ---
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas, # Pass the populated datas list
    [],
    name='WhiffleTracker', # Name of your final executable
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Set to True to try UPX compression (install UPX separately)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, # Set to False for a GUI application (no background console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='pinball_icon.ico' # Use the icon file
)

# --- For 'onedir' mode (Recommended for debugging/initial size check) ---
# This creates a folder containing the EXE and all dependencies/data files.
# Easier to inspect contents than 'onefile'.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas, # Pass the populated datas list
    strip=False,
    upx=True, # Enable UPX for collected binaries too
    name='WhiffleTracker_App', # Name of the output folder
)

# --- For 'onefile' mode (Uncomment the 'exe =' line below and comment out the 'coll =' block above) ---
# This creates a single large executable file. Can have slower startup.
# exe = EXE(...) # Keep the full exe definition from above if using onefile