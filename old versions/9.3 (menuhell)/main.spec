# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('splash.png', '.'),
        ('logo.png', '.'),
        ('sounds/background_music.mp3', 'sounds'),
        ('sounds/score_effect.wav', 'sounds'),
        ('sounds/game_over.wav', 'sounds'),
        ('sounds/menu_click.wav', 'sounds'),
        ('ball_detector_cnn.pth', '.'),
        ('whiffle_icon.ico', '.')  # Include the icon file
    ],
    hiddenimports=[
        'pygame.mixer',
        'torch',
        'torch.nn',
        'unittest'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'PIL',
        'IPython',
        'jupyter',
        'pandas',
        'scikit-learn',
        'pygame.display',
        'pygame.font',
        'pygame.draw'
        # Removed 'pygame.event' from excludes
    ],
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
    name='whiffle',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for debugging; set to False if not needed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='whiffle_icon.ico'
)