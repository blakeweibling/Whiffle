"""
Scoring zone management for the Whiffle Tracker project.

This module owns:

* The interactive "draw a new scoring zone" UX (:func:`define_scoring_zone`).
* The shared zone bounds-check used by both detection and scoring code
  (:func:`is_in_scoring_zone`).
* The on-screen drawing of zone overlays (:func:`draw_scoring_zones`).
* Helper utilities reused by ``interaction_utils.py`` (:func:`_zones_overlap`).

Zone tuples are ``(x, y, w, h, points)`` with ``(x, y)`` being the top-left
corner. Zone membership uses **half-open** intervals -- i.e. a pixel at
``(x + w, y + h)`` is *not* inside the zone -- so the same point cannot belong
to two adjacent zones.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from constants import ScoringConstants, UIConstants

DEFAULT_POINTS: int = ScoringConstants.DEFAULT_POINTS
MAX_POINTS: int = ScoringConstants.MAX_POINTS
FONT_SCALE: float = UIConstants.FONT_SCALE_MEDIUM
FONT_THICKNESS: int = UIConstants.FONT_THICKNESS
TEXT_OFFSET_X: int = UIConstants.TEXT_OFFSET_X
TEXT_OFFSET_Y: int = UIConstants.TEXT_OFFSET_Y
TEXT_SAFE_DISTANCE: int = UIConstants.TEXT_SAFE_DISTANCE

logger = logging.getLogger(__name__)

Zone = Tuple[int, int, int, int, int]


# ---------------------------------------------------------------------------
# bounds / overlap helpers (used by detection + scoring + interaction code)
# ---------------------------------------------------------------------------


def is_in_scoring_zone(ball: Sequence[Any], zone: Sequence[Any]) -> bool:
    """Return True when the ball's center lies inside ``zone``.

    ``ball`` can be any sequence with the x coordinate at index 0 and the y
    coordinate at index 1 (e.g. ``(x, y)``, ``(x, y, r)``, ``(x, y, r, id)`` or
    a full tracked-ball tuple). ``zone`` must be ``(x, y, w, h, points)``.

    The interval is half-open -- a point at ``(x + w, y + h)`` is **not**
    inside the zone -- which keeps detection and scoring consistent.
    """
    try:
        bx = float(ball[0])
        by = float(ball[1])
        zx = float(zone[0])
        zy = float(zone[1])
        zw = float(zone[2])
        zh = float(zone[3])
    except (TypeError, ValueError, IndexError):
        return False
    return (zx <= bx < zx + zw) and (zy <= by < zy + zh)


def _zones_overlap(
    new_zone: Tuple[int, int, int, int],
    existing_zones: List[Zone],
) -> bool:
    """Whether ``new_zone`` (x, y, w, h) intersects any zone in ``existing_zones``."""
    try:
        x1, y1, w1, h1 = (int(v) for v in new_zone[:4])
    except (TypeError, ValueError):
        return False
    for z in existing_zones:
        if not (isinstance(z, (list, tuple)) and len(z) >= 4):
            continue
        try:
            x2, y2, w2, h2 = (int(v) for v in z[:4])
        except (TypeError, ValueError):
            continue
        if x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1:
            continue
        logger.warning(
            "New zone (%d, %d, %d, %d) overlaps with existing zone (%d, %d, %d, %d)",
            x1, y1, w1, h1, x2, y2, w2, h2,
        )
        return True
    return False


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------


def _get_text_position(
    x: int, y: int, w: int, h: int, frame_width: int, frame_height: int
) -> Tuple[int, int]:
    """Position the label so it doesn't fall off the right edge of the frame."""
    fits_to_right = x + w + TEXT_SAFE_DISTANCE < frame_width
    text_x = x + w + TEXT_OFFSET_X if fits_to_right else x
    text_y = y if fits_to_right else min(frame_height - 1, y + h + TEXT_OFFSET_Y)
    return text_x, text_y


def _draw_zone_overlay(
    frame: np.ndarray,
    zones: List[Zone],
    special_hole: Optional[Zone] = None,
) -> None:
    """Render every zone as a rectangle + points label, highlighting the special hole."""
    for zone in zones:
        if not (isinstance(zone, (list, tuple)) and len(zone) == 5):
            continue
        try:
            x, y, w, h, points = (int(v) for v in zone)
        except (TypeError, ValueError):
            continue
        is_special = special_hole is not None and tuple(zone) == tuple(special_hole)
        color = UIConstants.PRIMARY if is_special else UIConstants.ACCENT
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, FONT_THICKNESS)
        text_x, text_y = _get_text_position(x, y, w, h, frame.shape[1], frame.shape[0])
        label = f"{points} pts (Special Hole)" if is_special else f"{points} pts"
        cv2.putText(
            frame,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            FONT_SCALE,
            color,
            FONT_THICKNESS,
            cv2.LINE_AA,
        )


def draw_scoring_zones(
    frame: np.ndarray,
    scoring_zones: List[Zone],
    special_hole: Optional[Zone] = None,
) -> None:
    """Draw all scoring zones on the frame with their point values."""
    if frame is None or not hasattr(frame, "shape"):
        return
    _draw_zone_overlay(frame, scoring_zones or [], special_hole)


# ---------------------------------------------------------------------------
# interactive zone-drawing UI
# ---------------------------------------------------------------------------


def _validate_frame(frame: np.ndarray) -> bool:
    if frame is None or not hasattr(frame, "shape"):
        logger.error("define_scoring_zone called with a null frame")
        return False
    if frame.shape[0] == 0 or frame.shape[1] == 0:
        logger.error("define_scoring_zone called with a zero-sized frame")
        return False
    return True


def _handle_mouse_event(event: int, x: int, y: int, drawing_state: dict) -> None:
    """Translate mouse events into ``drawing_state`` updates."""
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing_state["drawing"] = True
        drawing_state["start"] = (x, y)
        drawing_state["temp_zone"] = (x, y, 0, 0)
        logger.debug("Drawing started at (%d, %d)", x, y)
    elif event == cv2.EVENT_MOUSEMOVE and drawing_state["drawing"]:
        sx, sy = drawing_state["start"]
        drawing_state["temp_zone"] = (sx, sy, x - sx, y - sy)
    elif event == cv2.EVENT_LBUTTONUP and drawing_state["drawing"]:
        drawing_state["drawing"] = False
        if drawing_state["temp_zone"] is not None:
            x1, y1, w, h = drawing_state["temp_zone"]
            nx = min(x1, x1 + w)
            ny = min(y1, y1 + h)
            nw = abs(w)
            nh = abs(h)
            drawing_state["temp_zone"] = (nx, ny, nw, nh)
            logger.debug("Drawing ended; temp zone = (%d, %d, %d, %d)", nx, ny, nw, nh)


def _run_drawing_loop(
    frame: np.ndarray,
    cap: cv2.VideoCapture,
    drawing_state: dict,
    scoring_zones: List[Zone],
) -> Optional[Zone]:
    """Run the modal drawing loop and return the new zone (or None on cancel)."""
    overlay = np.zeros_like(frame)
    _draw_zone_overlay(overlay, scoring_zones)

    while True:
        if cap is not None and not cap.isOpened():
            logger.error("Camera closed during zone definition")
            return None

        temp_frame = cv2.addWeighted(frame, 0.8, overlay, 0.2, 0)

        temp_zone = drawing_state.get("temp_zone")
        if temp_zone:
            x, y, w, h = temp_zone
            cv2.rectangle(
                temp_frame,
                (x, y),
                (x + w, y + h),
                UIConstants.YELLOW,
                FONT_THICKNESS,
            )
            points_display = drawing_state.get("points") or str(DEFAULT_POINTS)
            text_x, text_y = _get_text_position(
                x, y, w, h, temp_frame.shape[1], temp_frame.shape[0]
            )
            cv2.putText(
                temp_frame,
                f"{points_display} pts",
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                FONT_SCALE,
                UIConstants.YELLOW,
                FONT_THICKNESS,
                cv2.LINE_AA,
            )

        instructions = (
            "Drag to draw zone | 0-9 set points | Backspace edit | Enter confirm | "
            "'c' cancel"
        )
        cv2.putText(
            temp_frame,
            instructions,
            (TEXT_OFFSET_X, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            FONT_SCALE,
            UIConstants.WHITE,
            FONT_THICKNESS,
            cv2.LINE_AA,
        )

        cv2.imshow(UIConstants.WINDOW_NAME, temp_frame)
        key = cv2.waitKey(1) & 0xFF

        if key == 13 and temp_zone and not drawing_state["drawing"]:
            if _zones_overlap(temp_zone, scoring_zones):
                logger.warning("Cancelling zone: overlaps existing zone")
                return None
            try:
                points = (
                    DEFAULT_POINTS
                    if not drawing_state.get("points")
                    else int(drawing_state["points"])
                )
            except ValueError:
                points = DEFAULT_POINTS
            points = max(1, min(points, MAX_POINTS))
            x, y, w, h = temp_zone
            zone: Zone = (int(x), int(y), int(w), int(h), int(points))
            logger.info("Scoring zone defined: %s", zone)
            return zone

        if key == ord("c"):
            logger.info("Scoring zone definition cancelled")
            return None

        if temp_zone and not drawing_state["drawing"]:
            if ord("0") <= key <= ord("9"):
                drawing_state["points"] = (drawing_state.get("points") or "") + chr(key)
                logger.debug("points buffer = %s", drawing_state["points"])
            elif key == 8:  # Backspace
                drawing_state["points"] = (drawing_state.get("points") or "")[:-1]
                logger.debug("points buffer = %s", drawing_state["points"])


def define_scoring_zone(
    frame: np.ndarray,
    cap: cv2.VideoCapture,
    trackbar_created: bool,
    scoring_zones: List[Zone],
) -> Tuple[Optional[Zone], bool]:
    """Run the interactive zone-drawing flow.

    The ``trackbar_created`` parameter is kept only for backwards compatibility
    with older callers; it is unused. The boolean returned alongside the new
    zone mirrors the legacy "trackbar_created" return so call sites continue to
    unpack ``(zone, _) = define_scoring_zone(...)`` unchanged.
    """
    if not _validate_frame(frame):
        return None, False

    drawing_state: dict = {
        "drawing": False,
        "start": (-1, -1),
        "temp_zone": None,
        "points": "",
    }
    try:
        cv2.setMouseCallback(
            UIConstants.WINDOW_NAME,
            lambda e, x, y, f, p: _handle_mouse_event(e, x, y, drawing_state),
        )
    except cv2.error as exc:
        logger.error("Failed to install mouse callback for zone drawing: %s", exc)
        return None, False

    zone = _run_drawing_loop(frame, cap, drawing_state, scoring_zones)
    return zone, False
