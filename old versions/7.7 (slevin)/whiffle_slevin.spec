# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['whiffle_slevin.py'],
    pathex=[],
    binaries=[],
    datas=[('whiffle_splash.jpg', '.'), ('background_music.mp3', '.'), ('score.wav', '.'), ('calibration.json', '.'), ('leaderboard.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='whiffle_slevin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['whiffle_icon.ico'],
)
