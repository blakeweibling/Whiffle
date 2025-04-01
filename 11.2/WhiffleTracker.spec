# -*- mode: python ; coding: utf-8 -*-

import sys
import os

added_files = [
    # Root directory files
    ('.env', '.'),
    ('achievements.json', '.'),
    ('achievements_status.json', '.'),
    ('data.yaml', '.'),
    ('game_over.png', '.'),
    ('high_scores.json', '.'),
    ('hsv_ranges.json', '.'),
    ('logo.png', '.'),
    ('pinball_icon.png', '.'),
    ('scoring_zones.json', '.'),
    ('splash.jpg', '.'),
    ('splash.png', '.'),
    ('static_frame.png', '.'), # Corrected filename from previous step
    ('whiffle_leaderboard.json', '.'),
    ('whiffle_new_best.pt', '.'),

    # Folders and their contents
    ('sounds', 'sounds'), # Include the sounds folder [cite: 2]
]

a = Analysis(
    ['game.py'], # Your main script filename [cite: 2, 9]
    pathex=[],
    binaries=[],
    datas=added_files, # Use the updated list [cite: 2, 9]
    hiddenimports=[ # Verify all are needed [cite: 2, 10]
        'pygame',
        'numpy',
        'cv2',
        'ultralytics',
        'scipy.spatial',
        'requests',
        'setuptools',
        'queue',
        'json',
        'logging',
        'datetime',
        'time',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[ # Verify these exclusions [cite: 3, 13]
        'tkinter', 'sqlite3', 'PyQt5', 'unittest', 'pytest',
        'pydoc_data', 'notebook', #'dotenv', #'scipy', #'requests',
        #'urllib3', 'chardet', 'idna', 'certifi', '_ssl',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE( # This defines the output for onefile mode
    pyz,
    a.scripts,
    [],
    [],
    a.datas, # Include the data files [cite: 4, 16]
    [],
    name='WhiffleTracker', # Name of the output .exe file [cite: 4, 16]
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # Keeping UPX off based on previous troubleshooting [cite: 4]
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Set True for console window, False for GUI only [cite: 4]
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='pinball_icon.ico' # Set the icon [cite: 5, 17]
)

# --- The 'COLLECT' block below is removed or commented out for onefile mode ---
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.datas,
#     strip=False,
#     upx=False,
#     upx_exclude=[],
#     name='WhiffleTracker_App',
# )