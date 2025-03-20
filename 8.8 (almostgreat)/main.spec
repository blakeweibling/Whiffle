# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],  # Entry point of your application
    pathex=[],  # Additional paths to search for modules (leave empty unless needed)
    binaries=[],  # Additional binaries (leave empty unless you have specific binaries to include)
    datas=[
        ('splash.png', '.'),  # Splash image
        ('labeled_data.pkl', '.'),  # Labeled data for ball detection
        ('training_data.csv', '.'),  # Fixed: Correct training data CSV file name
        ('zones.pkl', '.'),  # Scoring zones data
        ('sounds/*', 'sounds'),  # Entire sounds folder for sound effects and music
        ('config.json', '.'),  # Configuration file
        ('ball_detector_cnn.pth', '.'),  # CNN model for ball detection (note the underscore in the filename)
        ('whiffle_icon.ico', '.')  # Include the icon file in the bundle
    ],
    hiddenimports=[
        'pygame',  # For game functionality and sound
        'pandas',  # For handling CSV data
        'numpy',  # Used by OpenCV, pandas, and possibly your model
        'cv2',  # OpenCV for camera and image processing
        'sklearn',  # If you're using scikit-learn for the ball detector model
        'torch'  # Added: In case your ball detector model uses PyTorch
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],  # Exclude unnecessary modules to reduce size
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Whiffle',  # Name of the output .exe file
    debug=False,  # Set to True if you need debug output
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Use UPX compression to reduce size
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for a game
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='whiffle_icon.ico'  # Added: Specify the custom icon for the .exe
)