# -*- mode: python ; coding: utf-8 -*-
# Build (on the Pi itself -- PyInstaller cannot cross-compile):
#     pyinstaller game.linux.spec
# Output: dist/Whiffle/ containing the `Whiffle` ELF binary plus _internal/.
# Copy the entire dist/Whiffle/ folder to any Pi (same OS/arch) and run ./Whiffle.

import os

# Only include the .env file if it actually exists in the build tree.
# (Avoids "file does not exist" failures on CI / fresh checkouts.)
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
    binaries=[],
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
        # ML / detection
        'ultralytics',
        'torch',
        # HTTP / networking (used by leaderboard, screenshot upload,
        # interaction_utils, youtube_utils)
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
        'tkinter', 'pandas', 'sklearn', 'pytest',
        'IPython', 'jupyter', 'notebook',
        'matplotlib',
        # Triton is an x86_64 / NVIDIA-CUDA JIT. The aarch64 wheel that gets
        # pulled in transitively by torch on the Pi segfaults inside
        # triton/knobs.py during import (CPU-feature / CUDA stub detection).
        # With triton absent, torch's has_triton_package() returns False
        # cleanly and torch falls back to its non-triton code paths -- which
        # is what we want for inference-only use on a Pi anyway.
        'triton', 'pytorch_triton',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Whiffle',
    debug=False,
    # IMPORTANT: do NOT strip or UPX-compress on aarch64 Linux. Stripping libtorch
    # and OpenCV shared libs commonly produces silent segfaults at import time on
    # the Pi; UPX corrupts a number of Torch/Numpy .so files on ARM.
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # console=True so first-launch users can see startup logs / tracebacks in
    # their terminal. Flip to False once the install is stable if you want a
    # pure GUI launch.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='Whiffle',
    strip=False,
    upx=False,
    upx_exclude=[],
)
