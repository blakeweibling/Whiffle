# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['game.py'],
    pathex=['F:\\Whiffle\\10.6 (littlefix)'],
    binaries=[],
    datas=[
        # Configuration files
        ('.env', '.'),
        ('achievements.json', '.'),
        ('hsv_ranges.json', '.'),
        ('scoring_zones.json', '.'),
        ('whiffle_leaderboard.json', '.'),

        # Media files
        ('background_music.mp3', '.'),
        ('ding.wav', '.'),
        ('splash.png', '.'),
        ('last_frame.png', '.'),

        # YOLOv8 model files
        ('whiffle_new_best.pt', '.'),
    ],
    hiddenimports=[
        'pygame',
        'cv2',
        'dotenv',
        'ultralytics',
        'numpy',
        'Pillow',
        'matplotlib',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'pandas',
        'scipy',  # Keep scipy in excludes to avoid the full package
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WhiffleTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='pinball_icon.ico',
)