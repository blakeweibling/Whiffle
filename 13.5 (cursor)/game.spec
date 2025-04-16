# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['game.py', 'game_loop.py', 'game_state.py', 'game_input.py', 'ui.py', 'ui_screens.py', 
     'menu.py', 'menu_utils.py', 'submenus.py', 'submenu_draw_functions.py', 'scoring.py',
     'scoring_logic.py', 'leaderboard.py', 'tracking.py', 'effects.py', 'stats_calculator.py',
     'heatmap_utils.py', 'data_logger.py', 'detection.py', 'utils.py', 'ui_utils.py',
     'ui_elements.py', 'cleanup_utils.py', 'achievement.py', 'player.py', 'game_types.py',
     'game_state_utils.py', 'game_state_helpers.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('configs', 'configs'),
        ('data', 'data'),
        ('requirements.txt', '.'),
        ('.env', '.')
    ],
    hiddenimports=[
        'pygame',
        'numpy',
        'pandas',
        'cv2',
        'PIL',
        'matplotlib',
        'scipy',
        'sklearn'
    ],
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
    name='game',
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
    icon=['assets/pinball_icon.ico'],
)
