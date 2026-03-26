# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller game.spec
# Output: dist/Whiffle/ with Whiffle.exe and dependencies (for Inno Setup "Whiffle" folder)

import os

_binaries = [('openh264-1.8.0-win64.dll', '.')] if os.path.isfile('openh264-1.8.0-win64.dll') else []

a = Analysis(
    ['game.py', 'game_loop.py', 'game_state.py', 'game_input.py', 'ui.py', 'ui_screens.py',
     'menu.py', 'menu_utils.py', 'submenus.py', 'submenu_draw_functions.py', 'scoring.py',
     'scoring_logic.py', 'leaderboard.py', 'tracking.py', 'effects.py', 'stats_calculator.py',
     'heatmap_utils.py', 'data_logger.py', 'detection.py', 'utils.py', 'ui_utils.py',
     'ui_elements.py', 'cleanup_utils.py', 'achievement.py', 'player.py', 'game_types.py',
     'game_state_utils.py', 'game_state_helpers.py', 'interaction_utils.py', 'youtube_utils.py',
     'google_drive_utils.py', 'screenshot_utils.py', 'replay_manager.py', 'versus_mode.py',
     'loading_screen.py', 'xp_system.py'],
    pathex=[],
    binaries=_binaries,
    datas=[
        ('assets', 'assets'),
        ('configs', 'configs'),
        ('data', 'data'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'pygame',
        'numpy',
        'cv2',
        'PIL',
        'PIL.Image',
        'matplotlib',
        'matplotlib.pyplot',
        'ultralytics',
        'torch',
        'google.oauth2.credentials',
        'google_auth_oauthlib.flow',
        'googleapiclient.discovery',
        'googleapiclient.http',
        'googleapiclient.errors',
        'oauth2client.file',
        'oauth2client.client',
        'oauth2client.tools',
        'google.auth.transport.requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'pandas', 'scipy', 'sklearn', 'pytest',
        'IPython', 'jupyter', 'notebook',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],  # no binaries/datas here for onedir
    exclude_binaries=True,
    name='Whiffle',
    debug=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/pinball_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='Whiffle',
    strip=False,
    upx=True,
    upx_exclude=[],
)
