import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from game_state_helpers import set_special_hole

logger = logging.getLogger(__name__)

Zone = Tuple[int, int, int, int, int]
Point = Tuple[int, int]

ANCHOR_DETECTION_INTERVAL_FRAMES = 15
ANCHOR_MIN_COUNT = 2
ANCHOR_MAX_COUNT = 4
ANCHOR_MAX_JUMP_PX = 140.0
ANCHOR_MAX_RESIDUAL_PX = 20.0
ANCHOR_MAX_OFFSET_PX = 180.0

# High-visibility green markers work well with inexpensive cameras and varied lighting.
DEFAULT_ANCHOR_HSV_LOWER = (35, 70, 70)
DEFAULT_ANCHOR_HSV_UPPER = (95, 255, 255)


def _coerce_point(point: Any) -> Optional[Point]:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    try:
        return int(point[0]), int(point[1])
    except (TypeError, ValueError):
        return None


def _normalize_points(points: Any) -> List[Point]:
    normalized: List[Point] = []
    for point in points or []:
        parsed = _coerce_point(point)
        if parsed is not None:
            normalized.append(parsed)
    return normalized


def _sort_points(points: Sequence[Point]) -> List[Point]:
    return sorted((int(x), int(y)) for x, y in points)


def ensure_zone_alignment_state(game_state: Any) -> None:
    if not hasattr(game_state, "zone_alignment_settings"):
        game_state.zone_alignment_settings = {"playfields": {}}
    if not isinstance(getattr(game_state, "zone_alignment_settings", None), dict):
        game_state.zone_alignment_settings = {"playfields": {}}

    playfields = game_state.zone_alignment_settings.get("playfields")
    if not isinstance(playfields, dict):
        playfields = {}
        game_state.zone_alignment_settings["playfields"] = playfields

    defaults = {
        "zone_alignment_enabled": False,
        "zone_alignment_offset_x": 0,
        "zone_alignment_offset_y": 0,
        "zone_alignment_confidence": 0.0,
        "zone_alignment_detected_count": 0,
        "zone_alignment_reference_count": 0,
        "zone_alignment_active": False,
        "zone_alignment_status": "Not calibrated",
        "zone_alignment_last_update_time": 0.0,
        "zone_alignment_last_message": "",
        "zone_alignment_observed_points": [],
        "zone_alignment_last_detection_frame": -1,
        "effective_scoring_zones": list(getattr(game_state, "scoring_zones", []) or []),
        "effective_special_hole": getattr(game_state, "special_hole", None),
    }
    for attr_name, default_value in defaults.items():
        if not hasattr(game_state, attr_name):
            setattr(game_state, attr_name, default_value)


def get_current_playfield_key(game_state: Any) -> str:
    return str(getattr(game_state, "playfield_type", "whiffle") or "whiffle").strip().lower()


def get_anchor_calibration(game_state: Any, playfield_key: Optional[str] = None) -> Dict[str, Any]:
    ensure_zone_alignment_state(game_state)
    resolved_key = playfield_key or get_current_playfield_key(game_state)
    playfields = game_state.zone_alignment_settings.setdefault("playfields", {})
    config = playfields.get(resolved_key)
    if not isinstance(config, dict):
        config = {}
        playfields[resolved_key] = config
    if "reference_points" not in config:
        config["reference_points"] = []
    return config


def get_reference_anchor_points(game_state: Any, playfield_key: Optional[str] = None) -> List[Point]:
    config = get_anchor_calibration(game_state, playfield_key)
    return _sort_points(_normalize_points(config.get("reference_points", [])))


def update_alignment_reference_count(game_state: Any) -> None:
    ensure_zone_alignment_state(game_state)
    reference_points = get_reference_anchor_points(game_state)
    game_state.zone_alignment_reference_count = len(reference_points)
    if len(reference_points) >= ANCHOR_MIN_COUNT:
        if not getattr(game_state, "zone_alignment_last_message", ""):
            game_state.zone_alignment_last_message = "Calibration ready."
    elif getattr(game_state, "zone_alignment_status", "") in ("Tracking", "Searching"):
        game_state.zone_alignment_status = "Not calibrated"


def set_reference_anchor_points(game_state: Any, points: Sequence[Point]) -> List[Point]:
    ensure_zone_alignment_state(game_state)
    normalized_points = _sort_points(_normalize_points(points))[:ANCHOR_MAX_COUNT]
    config = get_anchor_calibration(game_state)
    config["reference_points"] = normalized_points
    update_alignment_reference_count(game_state)
    game_state.zone_alignment_last_message = (
        f"Saved {len(normalized_points)} anchor reference points."
        if normalized_points
        else "Anchor calibration cleared."
    )
    return normalized_points


def scale_reference_anchor_points(
    game_state: Any, old_width: int, old_height: int, new_width: int, new_height: int
) -> None:
    ensure_zone_alignment_state(game_state)
    if old_width <= 0 or old_height <= 0 or new_width <= 0 or new_height <= 0:
        return
    reference_points = get_reference_anchor_points(game_state)
    if not reference_points:
        return

    scale_x = float(new_width) / float(old_width)
    scale_y = float(new_height) / float(old_height)
    scaled_points = [
        (
            max(0, min(int(round(point_x * scale_x)), new_width - 1)),
            max(0, min(int(round(point_y * scale_y)), new_height - 1)),
        )
        for point_x, point_y in reference_points
    ]
    set_reference_anchor_points(game_state, scaled_points)


def clear_zone_alignment_runtime(game_state: Any, status_text: str = "Alignment idle") -> None:
    ensure_zone_alignment_state(game_state)
    game_state.zone_alignment_offset_x = 0
    game_state.zone_alignment_offset_y = 0
    game_state.zone_alignment_confidence = 0.0
    game_state.zone_alignment_detected_count = 0
    game_state.zone_alignment_active = False
    game_state.zone_alignment_status = status_text
    game_state.zone_alignment_observed_points = []
    game_state.zone_alignment_last_update_time = time.time()
    update_effective_scoring_zones(game_state)


def apply_zone_offset(
    zones: Sequence[Zone],
    offset_x: float,
    offset_y: float,
    frame_width: int = 0,
    frame_height: int = 0,
) -> List[Zone]:
    shifted: List[Zone] = []
    max_x = max(0, int(frame_width))
    max_y = max(0, int(frame_height))
    dx = int(round(offset_x))
    dy = int(round(offset_y))

    for zone in zones or []:
        if not isinstance(zone, (list, tuple)) or len(zone) != 5:
            continue
        try:
            x, y, w, h, points = [int(value) for value in zone]
        except (TypeError, ValueError):
            continue

        new_x = x + dx
        new_y = y + dy
        if max_x > 0:
            new_x = max(0, min(new_x, max_x - max(1, w)))
        if max_y > 0:
            new_y = max(0, min(new_y, max_y - max(1, h)))
        shifted.append((new_x, new_y, max(1, w), max(1, h), points))
    return shifted


def update_effective_scoring_zones(game_state: Any) -> None:
    ensure_zone_alignment_state(game_state)
    base_zones = list(getattr(game_state, "scoring_zones", []) or [])
    use_alignment = bool(
        getattr(game_state, "zone_alignment_enabled", False)
        and getattr(game_state, "zone_alignment_active", False)
    )
    if use_alignment:
        frame_width = int(getattr(game_state, "current_width", 0) or 0)
        frame_height = int(getattr(game_state, "current_height", 0) or 0)
        effective_zones = apply_zone_offset(
            base_zones,
            getattr(game_state, "zone_alignment_offset_x", 0),
            getattr(game_state, "zone_alignment_offset_y", 0),
            frame_width,
            frame_height,
        )
    else:
        effective_zones = list(base_zones)

    game_state.effective_scoring_zones = effective_zones
    if getattr(game_state, "playfield_type", "whiffle") == "fivestar":
        game_state.effective_special_hole = None
    else:
        game_state.effective_special_hole = set_special_hole(effective_zones)


def get_effective_scoring_zones(game_state: Any) -> List[Zone]:
    ensure_zone_alignment_state(game_state)
    effective = getattr(game_state, "effective_scoring_zones", None)
    if isinstance(effective, list):
        return effective
    update_effective_scoring_zones(game_state)
    return list(getattr(game_state, "effective_scoring_zones", []) or [])


def get_effective_special_hole(game_state: Any) -> Optional[Zone]:
    ensure_zone_alignment_state(game_state)
    if not hasattr(game_state, "effective_special_hole"):
        update_effective_scoring_zones(game_state)
    return getattr(game_state, "effective_special_hole", None)


def detect_anchor_markers(frame: np.ndarray) -> List[Point]:
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        return []

    frame_height, frame_width = frame.shape[:2]
    frame_area = max(1, frame_height * frame_width)
    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array(DEFAULT_ANCHOR_HSV_LOWER, dtype=np.uint8)
    upper = np.array(DEFAULT_ANCHOR_HSV_UPPER, dtype=np.uint8)
    mask = cv2.inRange(hsv_frame, lower, upper)
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: List[Tuple[float, Point]] = []
    min_area = max(25.0, frame_area * 0.00003)
    max_area = max(min_area + 1.0, frame_area * 0.01)

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area or area > max_area:
            continue

        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue

        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            continue
        aspect_ratio = float(w) / float(h)
        hull = cv2.convexHull(contour)
        hull_area = float(cv2.contourArea(hull))
        solidity = area / hull_area if hull_area > 0 else 0.0
        if not (0.45 <= aspect_ratio <= 1.75):
            continue
        if circularity < 0.35 and solidity < 0.8:
            continue

        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        center_x = int(moments["m10"] / moments["m00"])
        center_y = int(moments["m01"] / moments["m00"])
        candidates.append((area, (center_x, center_y)))

    candidates.sort(key=lambda item: item[0], reverse=True)
    points = [point for _area, point in candidates[:ANCHOR_MAX_COUNT]]
    return _sort_points(points)


def estimate_anchor_translation(
    reference_points: Sequence[Point],
    observed_points: Sequence[Point],
    previous_offset: Optional[Tuple[float, float]] = None,
) -> Tuple[bool, float, float, float, str]:
    normalized_reference = _sort_points(reference_points)
    normalized_observed = _sort_points(observed_points)
    if len(normalized_reference) < ANCHOR_MIN_COUNT:
        return False, 0.0, 0.0, 0.0, "Anchor calibration requires at least two markers."
    if len(normalized_observed) < ANCHOR_MIN_COUNT:
        return False, 0.0, 0.0, 0.0, "Not enough anchors visible."

    pair_count = min(len(normalized_reference), len(normalized_observed))
    paired_reference = normalized_reference[:pair_count]
    paired_observed = normalized_observed[:pair_count]
    deltas = np.array(
        [
            [float(obs_x - ref_x), float(obs_y - ref_y)]
            for (ref_x, ref_y), (obs_x, obs_y) in zip(paired_reference, paired_observed)
        ],
        dtype=np.float32,
    )
    mean_delta = deltas.mean(axis=0)
    residuals = np.linalg.norm(deltas - mean_delta, axis=1)
    average_residual = float(residuals.mean()) if residuals.size else 0.0
    max_residual = float(residuals.max()) if residuals.size else 0.0
    dx = float(mean_delta[0])
    dy = float(mean_delta[1])

    if abs(dx) > ANCHOR_MAX_OFFSET_PX or abs(dy) > ANCHOR_MAX_OFFSET_PX:
        return False, 0.0, 0.0, 0.0, "Anchor shift is too large to trust."
    if max_residual > ANCHOR_MAX_RESIDUAL_PX:
        return False, 0.0, 0.0, 0.0, "Anchor markers disagree on board movement."

    if previous_offset is not None:
        previous_dx, previous_dy = previous_offset
        jump = float(np.hypot(dx - previous_dx, dy - previous_dy))
        if jump > ANCHOR_MAX_JUMP_PX:
            return False, 0.0, 0.0, 0.0, "Anchor shift jumped too far."

    count_factor = min(1.0, pair_count / float(ANCHOR_MAX_COUNT))
    residual_factor = max(0.0, 1.0 - (average_residual / ANCHOR_MAX_RESIDUAL_PX))
    confidence = max(0.0, min(1.0, count_factor * residual_factor))
    return True, dx, dy, confidence, f"Tracking {pair_count} anchors."


def refresh_zone_alignment(game_state: Any, frame: np.ndarray, force: bool = False) -> None:
    ensure_zone_alignment_state(game_state)
    if frame is None:
        clear_zone_alignment_runtime(game_state, "No frame available")
        game_state.zone_alignment_last_message = "No frame available for anchor detection."
        return

    current_frame_count = int(getattr(game_state, "frame_count", 0) or 0)
    last_detection_frame = int(getattr(game_state, "zone_alignment_last_detection_frame", -1) or -1)
    if (
        not force
        and last_detection_frame >= 0
        and current_frame_count - last_detection_frame < ANCHOR_DETECTION_INTERVAL_FRAMES
    ):
        return
    game_state.zone_alignment_last_detection_frame = current_frame_count

    if not getattr(game_state, "camera_available", True):
        clear_zone_alignment_runtime(game_state, "Static mode")
        game_state.zone_alignment_last_message = "Anchor alignment is disabled in static image mode."
        return

    reference_points = get_reference_anchor_points(game_state)
    if len(reference_points) < ANCHOR_MIN_COUNT:
        clear_zone_alignment_runtime(game_state, "Not calibrated")
        game_state.zone_alignment_last_message = "Calibrate anchors before enabling alignment."
        return

    if not getattr(game_state, "zone_alignment_enabled", False):
        clear_zone_alignment_runtime(game_state, "Disabled")
        game_state.zone_alignment_last_message = "Anchor alignment is turned off."
        return

    observed_points = detect_anchor_markers(frame)
    game_state.zone_alignment_detected_count = len(observed_points)
    game_state.zone_alignment_observed_points = observed_points
    previous_offset = (
        float(getattr(game_state, "zone_alignment_offset_x", 0) or 0),
        float(getattr(game_state, "zone_alignment_offset_y", 0) or 0),
    )
    ok, dx, dy, confidence, message = estimate_anchor_translation(
        reference_points, observed_points, previous_offset
    )
    if not ok:
        clear_zone_alignment_runtime(game_state, "Searching")
        game_state.zone_alignment_detected_count = len(observed_points)
        game_state.zone_alignment_last_message = message
        return

    game_state.zone_alignment_offset_x = int(round(dx))
    game_state.zone_alignment_offset_y = int(round(dy))
    game_state.zone_alignment_confidence = float(confidence)
    game_state.zone_alignment_active = True
    game_state.zone_alignment_status = "Tracking"
    game_state.zone_alignment_last_update_time = time.time()
    game_state.zone_alignment_last_message = message
    update_effective_scoring_zones(game_state)


def calibrate_anchor_reference(game_state: Any, frame: np.ndarray) -> Tuple[bool, str]:
    ensure_zone_alignment_state(game_state)
    if frame is None:
        return False, "No frame is available for anchor calibration."
    if not getattr(game_state, "camera_available", True):
        return False, "Anchor calibration requires a live camera feed."

    observed_points = detect_anchor_markers(frame)
    if len(observed_points) < ANCHOR_MIN_COUNT:
        return False, "At least two visible anchor markers are required for calibration."

    saved_points = set_reference_anchor_points(game_state, observed_points)
    game_state.zone_alignment_enabled = True
    game_state.zone_alignment_detected_count = len(observed_points)
    game_state.zone_alignment_observed_points = list(observed_points)
    game_state.zone_alignment_status = "Calibrated"
    game_state.zone_alignment_last_update_time = time.time()
    game_state.zone_alignment_offset_x = 0
    game_state.zone_alignment_offset_y = 0
    game_state.zone_alignment_confidence = 1.0
    game_state.zone_alignment_active = False
    update_effective_scoring_zones(game_state)
    return True, f"Saved {len(saved_points)} anchor markers for this playfield."
