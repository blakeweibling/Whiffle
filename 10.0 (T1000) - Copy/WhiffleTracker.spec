# game.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['game.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ding.wav', '.'),
        ('background_music.mp3', '.'),
        ('logo.png', '.'),
        ('pinball_icon.png', '.'),
        ('splash.png', '.'),
        ('last_frame.png', '.'),
        ('hsv_ranges.json', '.'),
        ('scoring_zones.json', '.'),
        ('whiffle_leaderboard.json', '.'),
        ('achievements.json', '.'),
        ('whiffle_new_best.pt', '.'),
        ('data.yaml', '.')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='game',
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
    icon='pinball_icon.png',
)