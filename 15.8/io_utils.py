# io_utils.py
"""
Small I/O helpers used across the codebase.

Currently provides an atomic JSON writer that guarantees the destination
file is either the previous contents or the fully-written new contents —
never a truncated partial file — even on crash or power loss.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from typing import Any, Optional

logger = logging.getLogger(__name__)


def atomic_write_json(
    path: str,
    data: Any,
    *,
    indent: Optional[int] = 4,
    ensure_ascii: bool = False,
    create_parents: bool = True,
) -> bool:
    """Write ``data`` as JSON to ``path`` atomically.

    Steps:
      1. Serialize JSON in-memory (fail fast on non-serializable input).
      2. Write to a sibling temp file in the same directory.
      3. flush + fsync the temp file.
      4. os.replace() onto the destination (atomic on POSIX and NTFS).

    Args:
        path: Destination file path.
        data: JSON-serializable value.
        indent: Passed to json.dump; use ``None`` for compact output.
        ensure_ascii: If False (default), preserves unicode characters.
        create_parents: If True, create missing parent directories.

    Returns:
        True on success, False on any failure (errors are logged).
    """
    try:
        payload = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    except (TypeError, ValueError) as e:
        logger.error(f"atomic_write_json: cannot serialize data for {path}: {e}")
        return False

    directory = os.path.dirname(os.path.abspath(path)) or "."
    if create_parents:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            logger.error(f"atomic_write_json: cannot create directory {directory}: {e}")
            return False

    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".tmp_",
            suffix=".json",
            dir=directory,
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            tmp_fd = None
            f.write(payload)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, path)
        tmp_path = None
        return True
    except (OSError, IOError) as e:
        logger.error(f"atomic_write_json: failed writing {path}: {e}")
        return False
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path is not None and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def get_app_dir() -> str:
    """Return the directory that holds persisted app data.

    When frozen (PyInstaller), returns the directory containing the exe so
    installed copies write to their own folder. Otherwise returns the
    directory of this file.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))
