# -*- mode: python ; coding: utf-8 -*-

import sys
import os
# REMOVED: from PyInstaller.utils.hooks import collect_data_files

# --- Basic Setup ---
a = Analysis(
    ['game.py'], # <--- Your main script filename
    pathex=[],
    binaries=[],
    # --- MODIFIED: Emptied datas list for diagnostics ---
    datas=[],
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # --- Exclusions for Size Reduction ---
    excludes=[
        # Definitely safe
        'tkinter',
        'sqlite3',
        'PyQt5',
        'unittest',
        'pytest',
        'pydoc_data',
        'notebook',
        # Likely safe (Test!)
        'dotenv',
        # Optional (Performance/Size trade-off)
        'scipy', # Excluded as tracking.py has a fallback
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

# --- Data Files Section Temporarily Empty ---
# a.datas += [ ('file.json', '.'), ... ]

# --- Build Executable ---
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas, # Will pass the empty list here
    [],
    name='WhiffleTracker', # Name of your final executable
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Set to True to try UPX compression (install UPX separately)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, # Set to False for a GUI application with no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='pinball_icon.ico'
)

# --- For 'onedir' mode (Recommended for debugging/initial size check) ---
coll = COLLECT(
    exe,
    a.binaries,
    a.datas, # Will pass the empty list here
    strip=False,
    upx=True, # Enable UPX for collected binaries too
    name='WhiffleTracker_App', # Name of the output folder
)

# --- For 'onefile' mode (Uncomment to use instead of COLLECT) ---
# exe = EXE(...) # Keep the exe definition from above