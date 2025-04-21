# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['game.py'],
    pathex=[],
    binaries=[],
    datas=[('background_music.mp3', '.'), ('ding.wav', '.'), ('logo.png', '.'), ('splash.png', '.'), ('hsv_ranges.json', '.'), ('scoring_zones.json', '.'), ('achievements.json', '.'), ('whiffle_leaderboard.json', '.'), ('best.pt', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['_pycache_', 'dataset', 'runs', 'cv2.dnn', 'cv2.gapi', 'cv2.videoio', 'ultralytics.models', 'ultralytics.data'],
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
    name='WhiffleTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
