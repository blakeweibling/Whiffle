# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller game.spec
# Output: dist/Whiffle/ with Whiffle.exe and dependencies (for Inno Setup "Whiffle" folder)

import os

_binaries = [('openh264-1.8.0-win64.dll', '.')] if os.path.isfile('openh264-1.8.0-win64.dll') else []

# Only include .env if it actually exists at build time. Avoids hard-failing
# fresh checkouts / CI builds where the file hasn't been populated yet.
_datas = [
    ('assets', 'assets'),
    ('configs', 'configs'),
    ('data', 'data'),
]
if os.path.isfile('.env'):
    _datas.append(('.env', '.'))

a = Analysis(
    ['game.py', 'game_loop.py', 'game_state.py', 'game_input.py', 'ui.py', 'ui_screens.py',
     'menu.py', 'menu_utils.py', 'submenus.py', 'submenu_draw_functions.py', 'scoring.py',
     'scoring_logic.py', 'leaderboard.py', 'tracking.py', 'effects.py', 'stats_calculator.py',
     'heatmap_utils.py', 'data_logger.py', 'detection.py', 'utils.py', 'ui_utils.py',
     'ui_elements.py', 'cleanup_utils.py', 'achievement.py', 'player.py', 'game_types.py',
     'game_state_utils.py', 'game_state_helpers.py', 'interaction_utils.py', 'youtube_utils.py',
     'google_drive_utils.py', 'screenshot_utils.py', 'replay_manager.py', 'versus_mode.py',
     'loading_screen.py', 'xp_system.py', 'operator_remote.py'],
    pathex=[],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=[
        # Core game/runtime
        'pygame',
        'pygame.mixer',
        'numpy',
        'cv2',
        'PIL',
        'PIL.Image',
        'dotenv',
        # matplotlib is not imported by Whiffle directly, but ultralytics pulls
        # it in for results plotting; keep listed so the PyInstaller hook for
        # ultralytics is satisfied at freeze time.
        'matplotlib',
        'matplotlib.pyplot',
        # ML / detection
        'ultralytics',
        'torch',
        # HTTP / networking (leaderboard, Supabase storage, Discord webhook,
        # version checks, operator-remote helpers, YouTube upload pipeline)
        'requests',
        'urllib3',
        'httplib2',
        # Google / OAuth (Drive + YouTube uploads)
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
        # scipy is imported lazily via try/except in tracking.py; excluding it
        # only suppresses *accidental* inclusion -- if it's installed in the
        # build env, PyInstaller will still bundle it via the explicit import.
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
