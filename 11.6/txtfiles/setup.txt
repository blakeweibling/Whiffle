import sys
import os
from cx_Freeze import setup, Executable

# Disable SSL verification (temporary workaround)
os.environ["CXFREEZE_SSL_VERIFY"] = "0"  # Disable SSL verification for cx_Freeze
import ssl

ssl._create_default_https_context = (
    ssl._create_unverified_context
)  # Disable SSL verification globally

# Increase the recursion limit to avoid RecursionError (from previous fix)
sys.setrecursionlimit(5000)

# Define the base for Windows (to hide the console window if desired)
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # Use this if your game has a GUI and you don't want a console window

# Define the main script (entry point of your game)
main_script = "game.py"  # Change to "menu.py" if that's your entry point

# List of files and folders to include (assets, JSON files, etc.)
include_files = [
    "game_over.png",
    "logo.png",
    "pinball_icon.png",
    "splash.png",
    "splash2.png",
    "static_frame.png",
    "ding.wav",
    "sounds",
    "achievements.json",
    "achievements_status.json",
    "high_scores.json",
    "hsv_ranges.json",
    "scoring_zones.json",
    "whiffle_leaderboard.json",
    "README.md",
    "README.txt",
    "requirements.txt",
    "WhiffleTracker.txt",
    "data.yaml",
]

# Define packages your game depends on
packages = [
    "pygame",
    "numpy",
    "cv2",
    "ultralytics",
    "scipy.spatial",
    "requests",
    "setuptools",
    "queue",
    "json",
    "logging",
    "datetime",
    "time",
]

# Define files/folders to exclude
excludes = [
    "build",
    "dist",
    "utils",
    "pandas",
    "torchvision",
]

# Build options for cx_Freeze
build_exe_options = {
    "packages": packages,
    "include_files": include_files,
    "excludes": excludes,
    "include_msvcr": True,
    "optimize": 2,
}

# Define the executable
executables = [
    Executable(
        main_script,
        base=base,
        target_name="Whiffle",
        icon="pinball_icon.ico",
    )
]

# Setup configuration
setup(
    name="Whiffle",
    version="11.3",
    description="Whiffle Tracker",
    options={"build_exe": build_exe_options},
    executables=executables,
)
