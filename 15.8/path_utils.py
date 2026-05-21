# path_utils.py
"""
Resolve read-only bundled assets and writable app data paths for dev vs PyInstaller.

When frozen, PyInstaller places bundled ``data/``, ``configs/``, and ``assets/``
under ``sys._MEIPASS`` (the ``_internal/`` folder). The process CWD is often the
folder containing the ``Whiffle`` binary, so bare relative paths like
``data/whiffle_new_best.pt`` fail unless we seed/copy bundled trees beside the
executable and chdir there.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_app_dir() -> str:
    """Directory containing the runnable app (writable user data lives here when frozen)."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_bundle_dir() -> Optional[str]:
    """PyInstaller extraction dir (read-only bundled files), or None when running from source."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", None)
    return os.path.dirname(os.path.abspath(__file__))


def resolve_resource_path(relative_path: str) -> str:
    """Absolute path to a bundled read-only file (model, default config, asset).

    Checks, in order: beside the executable (seeded copy), then ``_MEIPASS``, then
    relative to the repo root in dev mode.
    """
    rel = relative_path.replace("\\", "/").lstrip("/")
    app_candidate = os.path.join(get_app_dir(), rel)
    if os.path.exists(app_candidate):
        return app_candidate
    bundle = get_bundle_dir()
    if bundle:
        bundle_candidate = os.path.join(bundle, rel)
        if os.path.exists(bundle_candidate):
            return bundle_candidate
    return app_candidate


def resolve_writable_path(relative_path: str, *, create_parent: bool = True) -> str:
    """Absolute path for files the app creates or updates (scores, sessions, settings)."""
    rel = relative_path.replace("\\", "/").lstrip("/")
    path = os.path.join(get_app_dir(), rel)
    if create_parent:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    return path


def _seed_tree(src_dir: str, dst_dir: str) -> None:
    """Copy files from ``src_dir`` into ``dst_dir`` only when missing in the destination."""
    if not os.path.isdir(src_dir):
        return
    os.makedirs(dst_dir, exist_ok=True)
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        dst_root = dst_dir if rel in (".", "") else os.path.join(dst_dir, rel)
        os.makedirs(dst_root, exist_ok=True)
        for name in files:
            src_file = os.path.join(root, name)
            dst_file = os.path.join(dst_root, name)
            if not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)


def bootstrap_frozen_paths() -> None:
    """Prepare CWD and on-disk folders when running as a PyInstaller bundle.

    - ``chdir`` to the folder containing the ``Whiffle`` binary so relative paths
      match a normal repo layout.
    - Copy bundled ``data/``, ``configs/``, and ``assets/`` from ``_internal/``
      into that folder when files are missing (models, default JSON, splash art).
    """
    if not is_frozen():
        return

    app_dir = get_app_dir()
    bundle_dir = get_bundle_dir()
    if not bundle_dir:
        logger.warning("Frozen build has no sys._MEIPASS; relative paths may fail.")
        return

    try:
        os.chdir(app_dir)
    except OSError as exc:
        logger.warning("Could not chdir to %s: %s", app_dir, exc)

    for subdir in ("data", "configs", "assets"):
        _seed_tree(os.path.join(bundle_dir, subdir), os.path.join(app_dir, subdir))

    model = resolve_resource_path("data/whiffle_new_best.pt")
    if not os.path.isfile(model):
        logger.error(
            "YOLO model missing after bootstrap. Expected at %s. "
            "Rebuild with data/whiffle_new_best.pt present in the repo root.",
            model,
        )
    else:
        logger.debug("YOLO model available at %s", model)
