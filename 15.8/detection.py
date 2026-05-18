# detection.py
"""
Ball detection for the Whiffle Tracker project.

This module runs a YOLOv8 model on the incoming frame and returns ball
detections to the tracker / scoring layers.

We do **not** try to second-guess the model with hand-rolled rim-ray / Sobel /
saturated-color gates -- those rejected real red balls sitting in recessed
wooden holes, where the rim is occluded and the color is desaturated. Instead
we apply only the cheap, reliable false-positive filters that target the
common failure mode (the YOLO model latching onto red-tinted wood-grain or
decorative graphics on the playfield):

  * **Frame-edge rejection** for solid-red detections (table border / frame).
  * **Loose color sanity** -- bbox center must read as redder than gray/brown
    wood (R > G and R > B by a small margin). Real red plastic clears this
    easily even when dark; wood does not.
  * **Aspect-ratio sanity** -- a real ball's bbox is roughly square.
  * **Zone-aware confidence** -- on the open playfield, require a slightly
    higher YOLO score for solid-red labels (because that is where the wood
    FPs live); in scoring zones, relax it so balls deep in a hole still pass.
  * **Top-N red rule** -- Whiffle has one player red ball, so only the
    highest-confidence solid-red detection survives per frame.
  * **Static-ghost suppression** -- a red detection that lives in the exact
    same spot frame after frame is almost certainly a wood pattern, not a
    moving ball; it gets locked out after enough frames of zero motion.

Public API (kept identical for drop-in replacement):

    class BallDetector:
        def __init__(self, model_path: Optional[str] = None)
        def detect_all_balls(
            self,
            frame: np.ndarray,
            frame_count: int,
            game_state: Any,
            scoring_zones: List[Tuple[int, int, int, int, int]],
            hsv_frame: Optional[np.ndarray] = None,
            debug_mode: bool = False,
        ) -> Tuple[
            List[Tuple[int, int, float, str]],
            List[Tuple[int, int, float, str]],
        ]

Each returned ball is ``(x, y, radius, ball_type)`` where ``ball_type`` is
the raw class label from the YOLO model.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

from constants import DetectionConstants, GameConstants, GameSpecificConstants

logger = logging.getLogger(__name__)

cv2.ocl.setUseOpenCL(True)
if not cv2.ocl.haveOpenCL():
    logger.warning("OpenCL is not available on this device. Falling back to CPU.")

EXCLUDED_POSITIONS: List[Tuple[Any, ...]] = list(GameSpecificConstants.EXCLUDED_POSITIONS)

# Labels that should be routed to the "gold" output bucket (which is also
# the bucket the half-red top-1 cap runs on). The Whiffle YOLO model in
# this project emits the half-red class as the bare label ``"half"``, so we
# must accept that alias here in addition to the more descriptive forms --
# otherwise the half-red collapse silently fires against an empty bucket
# while two ``"half"`` detections sail straight through in ``silver_buf``.
GOLD_LABEL_TOKENS: Tuple[str, ...] = (
    "half red",
    "halfred",
    "half",
    "gold",
    "yellow",
)

# Whiffle has exactly one of each of these special multiplier balls on the
# playfield at any time, so the detector caps each label to one survivor per
# frame (kept by highest YOLO confidence). The same kind tags are used as
# keys in the static-ghost suppressor so the red and half-red ghost tables
# stay independent.
UNIQUE_KIND_RED: str = "red"
UNIQUE_KIND_HALF_RED: str = "half-red"
UNIQUE_BALL_MAX_PER_FRAME: Dict[str, int] = {
    UNIQUE_KIND_RED: 1,
    UNIQUE_KIND_HALF_RED: 1,
}

# ---------------------------------------------------------------------- ghost suppression
# Wood-grain or decorative graphics on the playfield can be misclassified by
# the YOLO model as a red / half-red ball, and they sit in the **same pixel**
# from the moment the detector starts running. Real balls, in contrast, appear
# at a *new* position during gameplay (they are thrown into the table after
# the session has been running for at least a moment). The "temporal-ghost"
# filter exploits this difference:
#
#   * Every unique-ball detection bumps a hit counter for its 8x8 grid cell.
#   * A position is only **eligible** for ghost-locking if it was first seen
#     within ``EARLY_POSITION_WINDOW_FRAMES`` of the session start. Positions
#     that first appeared later are real balls -- they never get locked, even
#     if the ball sits still in a hole for the rest of the game.
#   * Eligible positions are locked once the hit counter reaches
#     ``GHOST_LOCK_FRAMES`` consecutive observations within
#     ``GHOST_ANCHOR_RADIUS_PX`` of the anchor.
#   * The anchor expires after ``GHOST_EXPIRE_FRAMES`` frames of inactivity
#     or whenever the candidate drifts further than the anchor radius.
GHOST_ANCHOR_RADIUS_PX: float = 8.0
GHOST_LOCK_FRAMES: int = 24
GHOST_EXPIRE_FRAMES: int = 90
EARLY_POSITION_WINDOW_FRAMES: int = 60

# Soft color guard parameters (very lightweight; not the old saturated-red gate).
# These only run on red detections **outside** any scoring zone; inside a hole
# a real ball can look brown-shadowed and would fail a strict red test.
RED_COLOR_R_OVER_G_MIN: float = 4.0   # mean(R) - mean(G) must be >= this
RED_COLOR_R_OVER_B_MIN: float = 4.0   # mean(R) - mean(B) must be >= this

# HSV saturated-red check (runs in-zone too).
#
# Real red plastic shows up at hue near 0 or 180 with high saturation; brown
# wood / red dial-faces sit at hue ~10-25 with much lower saturation. We
# count what fraction of pixels in the inner 50% of the bbox look like
# saturated red, and accept the detection if that fraction clears
# ``RED_HSV_SATURATED_FRACTION_MIN``. The thresholds are intentionally on
# the lenient side so a shadowed in-hole ball (V down, but H and S still
# in range) still passes -- but a brown dial pattern (H ~15, S ~50) does
# not produce enough saturated-red pixels to clear the fraction.
RED_HSV_HUE_LOW_MAX: int = 12
RED_HSV_HUE_HIGH_MIN: int = 168
RED_HSV_SATURATION_MIN: int = 70
RED_HSV_VALUE_MIN: int = 35
RED_HSV_SATURATED_FRACTION_MIN: float = 0.18
# Aspect ratio bounds are intentionally very lenient. A ball that is
# partially occluded by a recessed hole edge can have a fairly skewed bbox,
# and a ball at the far edge of the table that is furthest from the camera
# loses circularity to perspective foreshortening. Strong color/ghost
# filters and the NMS / top-1 cap protect against ratio-only FPs.
RED_ASPECT_MIN: float = 0.30
RED_ASPECT_MAX: float = 3.00

# How many pixels we forgive when deciding whether a detection is "inside"
# a scoring zone. A ball resting against the wood lip of a hole sometimes
# has its bbox center sit a few pixels outside the zone rectangle, even
# though the ball itself is clearly in the hole. Using a small margin makes
# the in-zone bypass robust to tightly-drawn zones.
IN_ZONE_BYPASS_MARGIN_PX: int = 20

# Non-unique balls (white / silver) do not suffer wood-grain false positives,
# so the conf-floor and small-ball-confirmation bypass uses a generous
# "near zone" margin. This lets a white ball that has come to rest just
# outside a tightly-drawn near-edge zone (e.g. the leftmost "50" hole or the
# "special" hole on the right) still be reported even when YOLO's confidence
# drops below the conservative ``YOLO_CONFIDENCE_THRESHOLD`` and even when
# perspective foreshortening near the far edge of the table has shrunk and
# skewed the ball's bbox.
NEAR_ZONE_BYPASS_MARGIN_PX: int = 100


def _normalize_label(label: str) -> str:
    if not label:
        return ""
    return label.lower().replace("_", " ").replace("-", " ").strip()


def _is_gold_label(label: str) -> bool:
    name = _normalize_label(label)
    if not name:
        return False
    return any(tok in name for tok in GOLD_LABEL_TOKENS)


def _is_solid_red_label(label: str) -> bool:
    """Solid player red ball (not half-red)."""
    name = _normalize_label(label)
    if not name:
        return False
    if "half" in name:
        return False
    return "red" in name


def _is_half_red_label(label: str) -> bool:
    """Half-red multiplier ball.

    Accepts the descriptive forms ('half-red', 'half_red', 'halfred') as well
    as the bare label ``'half'`` emitted by the Whiffle YOLO model. The bare
    form must be accepted, otherwise ``_collapse_label_to_top_n`` runs against
    a predicate that matches nothing and the top-1 cap silently no-ops while
    multiple half-red balls sail straight through.
    """
    name = _normalize_label(label)
    if not name:
        return False
    if "half" in name:
        return True
    return False


def _unique_kind_for_label(label: str) -> Optional[str]:
    """Return the unique-ball kind tag for a label, or ``None`` if not unique."""
    if _is_solid_red_label(label):
        return UNIQUE_KIND_RED
    if _is_half_red_label(label):
        return UNIQUE_KIND_HALF_RED
    return None


class BallDetector:
    """Run YOLO inference on a frame and bucket detections as silver vs. gold balls."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path: str = model_path or GameConstants.WHIFFLE_MODEL_PATH
        self.model = YOLO(self.model_path)
        self.class_names_by_id: Dict[int, str] = self._extract_class_names()
        self.class_names: List[str] = [
            self.class_names_by_id[k] for k in sorted(self.class_names_by_id.keys())
        ]
        self.state_names: List[str] = ["on_playfield", "in_hole"]

        # Multi-frame confirmation for very small bounding boxes (typically noise).
        self._small_ball_sticky: Dict[Tuple[int, int, int], Tuple[int, int]] = {}

        # Static "ghost" tracker for unique-ball labels (solid-red and
        # half-red). Keyed by ``(grid_x, grid_y, kind)`` so the two label
        # classes stay independent. Value is
        # ``(anchor_cx, anchor_cy, hit_count, first_seen_frame, last_seen_frame)``.
        # ``first_seen_frame`` is the frame index at which this grid cell was
        # first observed; only positions first seen within the session-start
        # window are eligible to be locked as ghosts (see _is_label_ghost).
        self._ghost_table: Dict[
            Tuple[int, int, str], Tuple[float, float, int, int, int]
        ] = {}

        # Frame index of the first call into the detector. Used by the
        # temporal-ghost filter to distinguish wood-grain FPs (visible from
        # session start) from real balls that land during gameplay.
        self._session_start_frame: Optional[int] = None

        logger.info(
            "BallDetector initialized | model=%s | classes=%s",
            self.model_path,
            self.class_names_by_id,
        )

    # ------------------------------------------------------------------ helpers

    def _extract_class_names(self) -> Dict[int, str]:
        for source in (
            getattr(self.model, "names", None),
            getattr(getattr(self.model, "model", None), "names", None),
        ):
            if not source:
                continue
            try:
                if isinstance(source, dict):
                    return {int(k): str(v) for k, v in source.items()}
                if isinstance(source, (list, tuple)):
                    return {int(i): str(v) for i, v in enumerate(source)}
            except Exception as exc:
                logger.warning("Class-name parse failed (%s): %s", type(source), exc)
        logger.error("Could not extract class names from YOLO model at %s", self.model_path)
        return {}

    @staticmethod
    def _is_position_excluded(x: float, y: float) -> bool:
        if not EXCLUDED_POSITIONS:
            return False
        threshold = float(DetectionConstants.EXCLUSION_DISTANCE)
        thr_sq = threshold * threshold
        for entry in EXCLUDED_POSITIONS:
            if not entry or len(entry) < 2:
                continue
            try:
                ex = float(entry[0])
                ey = float(entry[1])
            except (TypeError, ValueError):
                continue
            if (x - ex) ** 2 + (y - ey) ** 2 < thr_sq:
                return True
        return False

    @staticmethod
    def _is_in_any_scoring_zone(
        x: float,
        y: float,
        scoring_zones: List[Tuple[int, int, int, int, int]],
        margin: float = 0.0,
    ) -> bool:
        """Return True when ``(x, y)`` is within ``margin`` px of any zone rect.

        ``margin > 0`` treats a ball whose center sits just outside a tightly-
        drawn zone as if it were inside, which gives the in-zone bypass a
        more forgiving footprint for balls resting against a hole edge.
        """
        for z in scoring_zones or []:
            if not (isinstance(z, (list, tuple)) and len(z) >= 4):
                continue
            try:
                zx, zy, zw, zh = (float(z[0]), float(z[1]), float(z[2]), float(z[3]))
            except (TypeError, ValueError):
                continue
            if (
                zx - margin <= x < zx + zw + margin
                and zy - margin <= y < zy + zh + margin
            ):
                return True
        return False

    @staticmethod
    def _near_frame_edge(
        cx: float, cy: float, frame_shape: Tuple[int, ...], margin: int
    ) -> bool:
        if margin <= 0:
            return False
        h, w = int(frame_shape[0]), int(frame_shape[1])
        if h <= 0 or w <= 0:
            return False
        return cx < margin or cy < margin or cx > w - margin or cy > h - margin

    def _prune_small_ball_sticky(self, frame_count: int) -> None:
        stale = [
            key
            for key, (last_seen, _count) in self._small_ball_sticky.items()
            if frame_count - last_seen > 15
        ]
        for key in stale:
            self._small_ball_sticky.pop(key, None)

    def _confirm_small_ball(
        self, cx: float, cy: float, cls_id: int, frame_count: int, required: int
    ) -> bool:
        if required <= 1:
            return True
        key = (int(cx) // 10, int(cy) // 10, int(cls_id))
        prev = self._small_ball_sticky.get(key)
        if prev is None or frame_count - prev[0] > 4:
            count = 1
        else:
            count = prev[1] + 1
        self._small_ball_sticky[key] = (frame_count, count)
        return count >= required

    # ----------------------------------------------------- unique-ball FP filters

    def _prune_ghost_table(self, frame_count: int) -> None:
        stale = [
            key
            for key, (_, _, _, _first_seen, last_seen) in self._ghost_table.items()
            if frame_count - last_seen > GHOST_EXPIRE_FRAMES
        ]
        for key in stale:
            self._ghost_table.pop(key, None)

    def _is_label_ghost(
        self, cx: float, cy: float, frame_count: int, kind: str
    ) -> bool:
        """Update the ``kind`` ghost table for ``(cx, cy)`` and report if it's locked.

        Temporal-ghost filter: each unique-ball detection bumps its grid cell's
        hit counter, but a position is only *eligible* to be locked as a ghost
        if its ``first_seen_frame`` was within ``EARLY_POSITION_WINDOW_FRAMES``
        of the session start. This means:

        * Wood-grain / decoration FPs, which are visible from the moment the
          detector starts running, are first-seen at session start, become
          eligible, and lock once they've been observed at the same pixel for
          ``GHOST_LOCK_FRAMES`` consecutive passes -- so they get suppressed
          permanently.

        * A real ball thrown into a hole during gameplay is first-seen *after*
          the session-start window has closed, so it is never eligible for
          locking -- it can sit motionless in its hole indefinitely and still
          be reported.

        Position drift outside ``GHOST_ANCHOR_RADIUS_PX`` resets the anchor;
        it preserves ``first_seen_frame`` so a wood-pattern that occasionally
        jitters by a pixel stays in the "from session start" cohort.
        """
        if self._session_start_frame is None:
            self._session_start_frame = int(frame_count)

        key = (int(cx) // 8, int(cy) // 8, kind)
        entry = self._ghost_table.get(key)
        if entry is None:
            self._ghost_table[key] = (
                float(cx), float(cy), 1, int(frame_count), int(frame_count)
            )
            return False

        ax, ay, count, first_seen, _last_seen = entry
        # Drift check: if the candidate has wandered, reset the anchor instead
        # of locking it in. We keep ``first_seen`` so that a wood pattern that
        # jitters by a few pixels still stays in the "from session start"
        # cohort and remains eligible for ghosting.
        if (cx - ax) ** 2 + (cy - ay) ** 2 > GHOST_ANCHOR_RADIUS_PX ** 2:
            self._ghost_table[key] = (
                float(cx), float(cy), 1, int(first_seen), int(frame_count)
            )
            return False

        count = min(count + 1, GHOST_LOCK_FRAMES * 4)
        self._ghost_table[key] = (ax, ay, count, int(first_seen), int(frame_count))

        # Only positions first observed within the session-start window are
        # eligible for locking. Real balls that land during gameplay have a
        # much later ``first_seen`` and stay accepted forever.
        is_early_position = (
            (first_seen - int(self._session_start_frame)) < EARLY_POSITION_WINDOW_FRAMES
        )
        return count >= GHOST_LOCK_FRAMES and is_early_position

    @staticmethod
    def _bbox_color_means(
        frame: np.ndarray, cx: float, cy: float, box_w: float, box_h: float
    ) -> Optional[Tuple[float, float, float]]:
        """Mean (B, G, R) over the inner 50% of the bbox; ``None`` if too small."""
        h, w = frame.shape[0], frame.shape[1]
        half_w = max(2, int(box_w * 0.25))
        half_h = max(2, int(box_h * 0.25))
        x0 = max(0, int(cx - half_w))
        x1 = min(w, int(cx + half_w))
        y0 = max(0, int(cy - half_h))
        y1 = min(h, int(cy + half_h))
        if x1 <= x0 or y1 <= y0:
            return None
        roi = frame[y0:y1, x0:x1]
        if roi.size == 0:
            return None
        b_mean, g_mean, r_mean = cv2.mean(roi)[:3]
        return float(b_mean), float(g_mean), float(r_mean)

    def _looks_reddish(
        self, frame: np.ndarray, cx: float, cy: float, box_w: float, box_h: float
    ) -> bool:
        """Cheap color sanity: bbox center must lean noticeably red."""
        means = self._bbox_color_means(frame, cx, cy, box_w, box_h)
        if means is None:
            return True  # benefit of the doubt when we cannot sample
        b, g, r = means
        return (r >= g + RED_COLOR_R_OVER_G_MIN) and (r >= b + RED_COLOR_R_OVER_B_MIN)

    @staticmethod
    def _looks_saturated_red(
        hsv_frame: Optional[np.ndarray],
        cx: float,
        cy: float,
        box_w: float,
        box_h: float,
    ) -> bool:
        """HSV-based saturated-red gate.

        Returns True when a meaningful fraction of pixels inside the inner
        50% of the bbox sit at hue near 0 or 180 with high saturation and
        non-trivial value -- i.e. they look like saturated red plastic.

        Returns True when we cannot sample (no HSV frame, degenerate ROI)
        so the gate "fails open" and never blocks a detection on a missing
        frame. This is what reliably separates a real red ball in a hole
        (still saturated red even when shadowed) from a brown wood-grain
        pattern or a red-printed dial face (low saturation, hue in the
        orange band, not the red band).
        """
        if hsv_frame is None or not hasattr(hsv_frame, "shape") or hsv_frame.size == 0:
            return True

        fh, fw = int(hsv_frame.shape[0]), int(hsv_frame.shape[1])
        if fh < 2 or fw < 2:
            return True

        half_w = max(2, int(box_w * 0.25))
        half_h = max(2, int(box_h * 0.25))
        x0 = max(0, int(cx - half_w))
        x1 = min(fw, int(cx + half_w))
        y0 = max(0, int(cy - half_h))
        y1 = min(fh, int(cy + half_h))
        if x1 <= x0 or y1 <= y0:
            return True

        roi = hsv_frame[y0:y1, x0:x1]
        if roi.size == 0:
            return True

        h = roi[:, :, 0]
        s = roi[:, :, 1]
        v = roi[:, :, 2]

        hue_red = (h <= RED_HSV_HUE_LOW_MAX) | (h >= RED_HSV_HUE_HIGH_MIN)
        sat_ok = s >= RED_HSV_SATURATION_MIN
        val_ok = v >= RED_HSV_VALUE_MIN
        red_mask = hue_red & sat_ok & val_ok

        total = float(red_mask.size)
        if total <= 0.0:
            return True
        fraction = float(red_mask.sum()) / total
        return fraction >= RED_HSV_SATURATED_FRACTION_MIN

    def _accept_unique_ball_detection(
        self,
        frame: np.ndarray,
        cx: float,
        cy: float,
        box_w: float,
        box_h: float,
        score: float,
        scoring_zones: List[Tuple[int, int, int, int, int]],
        frame_count: int,
        kind: str,
        debug_mode: bool,
        hsv_frame: Optional[np.ndarray] = None,
    ) -> bool:
        """Run the false-positive gauntlet for a single unique-ball detection.

        ``kind`` is one of ``UNIQUE_KIND_RED`` or ``UNIQUE_KIND_HALF_RED``.

        The gauntlet splits on whether the detection sits inside a scoring
        zone (with a small forgiveness margin):

        * **Inside any scoring zone** -- a real ball *belongs* here, possibly
          at rest for many seconds from the very first frame of the session
          (e.g. balls left in holes between games). We trust the YOLO model
          and skip every secondary filter, including the static-ghost
          lockout. The ghost lockout is what would otherwise wrongly
          suppress a red ball that has been sitting motionless in its hole
          since the detector started running.

        * **Outside any scoring zone** -- the open playfield. This is where
          wood-grain / decorative graphics live, so we apply the full
          gauntlet: aspect-ratio sanity, frame-edge rejection, a stricter
          YOLO confidence floor, a loose color test (solid red only -- half
          red is partly white so this would over-reject), and the
          temporal-ghost lockout. The temporal logic in ``_is_label_ghost``
          is still in effect: only positions first seen within the
          session-start window are eligible to be locked, so an
          out-of-zone red detection that appears mid-game is never locked.
        """
        dc = DetectionConstants

        # Solid-red HSV gate runs *always*, in-zone or out. Brown wood and
        # red-printed dial faces fall inside the user-drawn zones on some
        # Whiffle layouts -- the gate distinguishes them from a real
        # saturated-red ball even when the FP sits squarely inside a
        # scoring zone. Half-red is intentionally exempt because its
        # bbox center can sample the white half of the ball.
        if kind == UNIQUE_KIND_RED:
            if not self._looks_saturated_red(
                hsv_frame, cx, cy, box_w, box_h
            ):
                if debug_mode:
                    logger.debug(
                        "%s rejected (HSV not saturated-red) @ (%.0f, %.0f)",
                        kind, cx, cy,
                    )
                return False

        # The in-zone bypass uses a small margin so a ball resting against
        # a zone's hole-lip is still considered "in zone" even if its bbox
        # center sits a few pixels outside the user-drawn rectangle.
        in_zone = self._is_in_any_scoring_zone(
            cx, cy, scoring_zones, margin=float(IN_ZONE_BYPASS_MARGIN_PX)
        )

        if in_zone:
            # The HSV gate above has already confirmed the detection looks
            # like saturated red plastic (for solid red); half-red is
            # trusted in-zone. Skip the rest of the out-of-zone filters
            # because real balls in holes can be skewed, shadowed and
            # static from the very first detection frame.
            return True

        if box_h <= 0:
            return False
        ratio = box_w / max(box_h, 1.0)
        if ratio < RED_ASPECT_MIN or ratio > RED_ASPECT_MAX:
            if debug_mode:
                logger.debug(
                    "%s rejected (aspect %.2f, out of zone) @ (%.0f, %.0f)",
                    kind, ratio, cx, cy,
                )
            return False

        if self._near_frame_edge(
            cx, cy, frame.shape, int(dc.RED_BALL_FRAME_EDGE_MARGIN_PX)
        ):
            if debug_mode:
                logger.debug(
                    "%s rejected (frame edge, out of zone) @ (%.0f, %.0f)",
                    kind, cx, cy,
                )
            return False

        if score < float(dc.RED_BALL_MIN_YOLO_CONFIDENCE):
            if debug_mode:
                logger.debug(
                    "%s rejected (conf %.2f < %.2f, out of zone) @ (%.0f, %.0f)",
                    kind, score, float(dc.RED_BALL_MIN_YOLO_CONFIDENCE), cx, cy,
                )
            return False

        if kind == UNIQUE_KIND_RED:
            if not self._looks_reddish(frame, cx, cy, box_w, box_h):
                if debug_mode:
                    logger.debug(
                        "%s rejected (not reddish, out of zone) @ (%.0f, %.0f)",
                        kind, cx, cy,
                    )
                return False

        # Temporal-ghost suppression. Out-of-zone is where wood-grain FPs
        # live; the temporal gate in ``_is_label_ghost`` makes sure a real
        # ball that appears mid-game out here (rare, but possible while a
        # ball is in flight) is not locked.
        if self._is_label_ghost(cx, cy, frame_count, kind):
            if debug_mode:
                logger.debug(
                    "%s rejected (temporal ghost, out of zone) @ (%.0f, %.0f)",
                    kind, cx, cy,
                )
            return False

        return True

    # -------------------------------------------------------------- NMS / output

    @staticmethod
    def _log_buffer_drops(
        before: List[Tuple[int, int, float, str, float]],
        after: List[Tuple[int, int, float, str, float]],
        stage: str,
        min_dist: Optional[float],
    ) -> None:
        """Emit a debug line for every detection dropped between two buffer states.

        ``before`` and ``after`` are the buffer contents before and after a
        stage (NMS or the unique-ball top-N cap). Any tuple present in
        ``before`` and absent in ``after`` is logged so the full audit
        trail (raw -> per-filter -> NMS / cap -> output) is visible from
        a single log file when ``debug_mode`` is on.
        """
        if not before:
            return
        kept = set(after)
        dropped = [b for b in before if b not in kept]
        if not dropped:
            return
        dist_note = f", min_dist={min_dist:.1f}" if min_dist is not None else ""
        for x, y, _r, ball_type, conf in dropped:
            logger.debug(
                "%s rejected (%s%s) @ (%d, %d) conf=%.2f",
                ball_type, stage, dist_note, x, y, conf,
            )

    @staticmethod
    def _nms(
        balls: List[Tuple[int, int, float, str, float]], min_dist: float
    ) -> List[Tuple[int, int, float, str, float]]:
        if not balls or min_dist <= 0.0 or len(balls) < 2:
            return balls
        d_sq = min_dist * min_dist
        ordered = sorted(balls, key=lambda b: b[4], reverse=True)
        kept: List[Tuple[int, int, float, str, float]] = []
        for cand in ordered:
            cx, cy = float(cand[0]), float(cand[1])
            if any((cx - kx) ** 2 + (cy - ky) ** 2 < d_sq for kx, ky, _r, _t, _s in kept):
                continue
            kept.append(cand)
        return kept

    @staticmethod
    def _collapse_label_to_top_n(
        balls: List[Tuple[int, int, float, str, float]],
        predicate,
        max_count: int,
    ) -> List[Tuple[int, int, float, str, float]]:
        """Keep at most ``max_count`` detections whose label matches ``predicate``.

        Survivors are picked by highest YOLO confidence. Detections that
        ``predicate(label)`` returns False for are never touched.
        """
        if not balls or max_count < 0:
            return balls
        match_idx = [i for i, b in enumerate(balls) if predicate(b[3])]
        if len(match_idx) <= max_count:
            return balls
        ordered = sorted(match_idx, key=lambda i: balls[i][4], reverse=True)
        drop = set(ordered[max_count:])
        return [b for i, b in enumerate(balls) if i not in drop]

    @staticmethod
    def _strip_conf(
        balls: List[Tuple[int, int, float, str, float]],
    ) -> List[Tuple[int, int, float, str]]:
        return [(x, y, r, t) for (x, y, r, t, _conf) in balls]

    # ----------------------------------------------------------------- public API

    def detect_all_balls(
        self,
        frame: np.ndarray,
        frame_count: int,
        game_state: Any,
        scoring_zones: List[Tuple[int, int, int, int, int]],
        hsv_frame: Optional[np.ndarray] = None,
        debug_mode: bool = False,
    ) -> Tuple[
        List[Tuple[int, int, float, str]],
        List[Tuple[int, int, float, str]],
    ]:
        """Detect all balls in ``frame`` and split them into (silver, gold) lists."""
        _ = (game_state,)

        if frame is None or not hasattr(frame, "shape") or frame.size == 0:
            return [], []
        if len(frame.shape) < 2 or frame.shape[0] < 2 or frame.shape[1] < 2:
            return [], []
        if not self.class_names_by_id:
            logger.error("Class-name map is empty; cannot run detection.")
            return [], []

        # The HSV saturated-red gate in the unique-ball gauntlet needs a
        # 3-channel HSV view of the same frame the YOLO model saw. Compute
        # it once here (the caller can also pass one in to avoid the cost).
        if hsv_frame is None and frame.ndim == 3 and frame.shape[2] >= 3:
            try:
                hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            except cv2.error as exc:
                logger.warning("Failed to compute HSV view of frame: %s", exc)
                hsv_frame = None

        self._prune_small_ball_sticky(frame_count)
        self._prune_ghost_table(frame_count)

        dc = DetectionConstants
        scale = float(dc.YOLO_INFERENCE_SCALE)
        if not (0.0 < scale <= 1.0):
            scale = 0.5
        inv_scale = 1.0 / scale

        if scale < 1.0:
            try:
                inference_frame = cv2.resize(
                    frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
                )
            except cv2.error as exc:
                logger.warning("Failed to downscale frame for inference: %s", exc)
                inference_frame = frame
                inv_scale = 1.0
        else:
            inference_frame = frame

        predict_kwargs: Dict[str, Any] = {
            "conf": float(dc.YOLO_RAW_INFERENCE_CONFIDENCE),
            "iou": float(dc.YOLO_IOU_THRESHOLD),
            "verbose": False,
        }
        imgsz = int(dc.YOLO_INFERENCE_IMG_SIZE)
        if imgsz > 0:
            predict_kwargs["imgsz"] = imgsz

        try:
            results = self.model(inference_frame, **predict_kwargs)
        except Exception as exc:
            logger.exception("YOLO inference failed: %s", exc)
            return [], []

        silver_buf: List[Tuple[int, int, float, str, float]] = []
        gold_buf: List[Tuple[int, int, float, str, float]] = []

        # In debug mode we keep every raw YOLO detection so the debug window
        # can outline what the model produced before any of our filters ran.
        raw_detections: List[Tuple[int, int, float, str, float]] = []

        conf_floor = float(dc.YOLO_CONFIDENCE_THRESHOLD)
        small_box_max = float(dc.SMALL_BALL_MAX_BOX_PX)
        small_box_required = int(dc.SMALL_BALL_CONFIRM_THRESHOLD)
        scoring_zones = scoring_zones or []

        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None or len(boxes) == 0:
                continue
            try:
                xyxy = boxes.xyxy.cpu().numpy()
                scores = boxes.conf.cpu().numpy()
                class_ids = boxes.cls.cpu().numpy()
            except Exception as exc:
                logger.warning("Could not read YOLO result tensors: %s", exc)
                continue

            for (x_min, y_min, x_max, y_max), score, cls in zip(xyxy, scores, class_ids):
                x_min = float(x_min) * inv_scale
                x_max = float(x_max) * inv_scale
                y_min = float(y_min) * inv_scale
                y_max = float(y_max) * inv_scale

                box_w = max(0.0, x_max - x_min)
                box_h = max(0.0, y_max - y_min)
                if box_w < 2.0 or box_h < 2.0:
                    continue

                cx = (x_min + x_max) * 0.5
                cy = (y_min + y_max) * 0.5
                radius = max(box_w, box_h) * 0.5

                if self._is_position_excluded(cx, cy):
                    if debug_mode:
                        logger.debug(
                            "Skipping detection at (%.0f, %.0f) -- excluded position",
                            cx, cy,
                        )
                    continue

                cls_int = int(round(float(cls)))
                ball_type = self.class_names_by_id.get(cls_int)
                if ball_type is None:
                    if debug_mode:
                        logger.debug(
                            "Skipping unknown class id %d (known=%s)",
                            cls_int, sorted(self.class_names_by_id.keys()),
                        )
                    continue

                conf = float(score)

                # Always log every YOLO box that survives the raw inference
                # threshold, BEFORE we apply any of our own filtering. This
                # is the only way to tell from a log file whether a missing
                # ball was never produced by the model in the first place
                # vs. produced and then dropped by one of the downstream
                # gates. Each surviving detection is followed by either a
                # "Detected ..." or a "... rejected (...)" line so the log
                # has a complete audit trail per box.
                if debug_mode:
                    logger.debug(
                        "RAW YOLO: %s (cls=%d) at (%.0f, %.0f) box=%.0fx%.0f conf=%.2f",
                        ball_type, cls_int, cx, cy, box_w, box_h, conf,
                    )
                    raw_detections.append(
                        (
                            int(round(cx)),
                            int(round(cy)),
                            float(max(box_w, box_h) * 0.5),
                            str(ball_type),
                            conf,
                        )
                    )

                # YOLO sometimes labels a perspective-skewed white ball at
                # the far edge of the table as "half-red", because the dim
                # contrast there resembles a half-shaded ball. A real
                # half-red ball has plenty of saturated-red pixels in its
                # bbox; a white ball has none. If the HSV gate rejects
                # this as half-red, relabel it as a plain white ball so
                # it still gets reported (just with the correct label and
                # without the unique-ball top-1 cap).
                if _is_half_red_label(ball_type):
                    if not self._looks_saturated_red(
                        hsv_frame, cx, cy, box_w, box_h
                    ):
                        if debug_mode:
                            logger.debug(
                                "Relabel half-red -> white "
                                "(no saturated red) @ (%.0f, %.0f) conf=%.2f",
                                cx, cy, conf,
                            )
                        ball_type = "white"

                # Pre-compute the in-zone flag once. Unique balls use a
                # tight margin (they go through ghost / FP filtering anyway).
                # Non-unique balls (white / silver) use a much wider margin
                # so a ball at rest just outside a tightly-drawn near-edge
                # zone still benefits from the lenient conf-floor path.
                in_zone = self._is_in_any_scoring_zone(
                    cx, cy, scoring_zones, margin=float(IN_ZONE_BYPASS_MARGIN_PX)
                )
                near_zone = self._is_in_any_scoring_zone(
                    cx, cy, scoring_zones, margin=float(NEAR_ZONE_BYPASS_MARGIN_PX)
                )

                # Unique-ball labels (solid red, half-red) go through the
                # zone-aware false-positive gauntlet. All other labels use
                # the plain confidence floor unless they are near a zone.
                unique_kind = _unique_kind_for_label(ball_type)
                if unique_kind is not None:
                    if not self._accept_unique_ball_detection(
                        frame,
                        cx, cy,
                        box_w, box_h,
                        conf,
                        scoring_zones,
                        frame_count,
                        unique_kind,
                        debug_mode,
                        hsv_frame=hsv_frame,
                    ):
                        continue
                else:
                    # White / silver balls don't suffer wood-grain FPs, so
                    # we relax the conf floor for anything anywhere near a
                    # scoring zone. This is what gets near-edge white balls
                    # in tightly-drawn zones to be reported.
                    if conf < conf_floor and not near_zone:
                        if debug_mode:
                            logger.debug(
                                "%s rejected (conf %.2f < %.2f, "
                                "not near zone) @ (%.0f, %.0f)",
                                ball_type, conf, conf_floor, cx, cy,
                            )
                        continue

                # Small-ball multi-frame confirmation: balls deep in a hole
                # are often tiny in pixels. Outside zones (and outside the
                # generous near-zone margin) we still need this to suppress
                # single-frame noise, but near a zone we trust the raw YOLO
                # output -- otherwise a small in-hole ball whose YOLO class
                # id flickers (or whose bbox jitters across a 10-px grid
                # boundary) never accumulates enough confirmations and is
                # silently dropped.
                if max(box_w, box_h) <= small_box_max and not near_zone:
                    if not self._confirm_small_ball(
                        cx, cy, cls_int, frame_count, small_box_required
                    ):
                        if debug_mode:
                            logger.debug(
                                "%s rejected (small-ball confirmation, "
                                "box=%.0fx%.0f, not near zone) @ (%.0f, %.0f)",
                                ball_type, box_w, box_h, cx, cy,
                            )
                        continue

                rec = (
                    int(round(cx)),
                    int(round(cy)),
                    float(radius),
                    str(ball_type),
                    conf,
                )

                if _is_gold_label(ball_type):
                    gold_buf.append(rec)
                else:
                    silver_buf.append(rec)

                if debug_mode:
                    logger.debug(
                        "Detected %s (cls=%d) at (%.0f, %.0f) r=%.1f conf=%.2f",
                        ball_type, cls_int, cx, cy, radius, conf,
                    )

        nms_dist = float(dc.DETECTION_NMS_MIN_DISTANCE_PX)
        silver_pre_nms = list(silver_buf)
        gold_pre_nms = list(gold_buf)
        silver_buf = self._nms(silver_buf, nms_dist)
        gold_buf = self._nms(gold_buf, nms_dist)
        if debug_mode:
            self._log_buffer_drops(
                silver_pre_nms, silver_buf, "NMS (silver)", nms_dist
            )
            self._log_buffer_drops(
                gold_pre_nms, gold_buf, "NMS (gold)", nms_dist
            )

        # Whiffle has at most one of each unique multiplier ball on the
        # playfield at any time (one solid red, one half-red). Keep only the
        # highest-confidence survivor of each kind.
        max_red = max(
            0,
            int(
                UNIQUE_BALL_MAX_PER_FRAME.get(
                    UNIQUE_KIND_RED, dc.RED_MAX_PLAYER_RED_BALLS
                )
            ),
        )
        max_half_red = max(
            0, int(UNIQUE_BALL_MAX_PER_FRAME.get(UNIQUE_KIND_HALF_RED, 1))
        )
        silver_pre_cap = list(silver_buf)
        gold_pre_cap = list(gold_buf)
        silver_buf = self._collapse_label_to_top_n(
            silver_buf, _is_solid_red_label, max_red
        )
        gold_buf = self._collapse_label_to_top_n(
            gold_buf, _is_half_red_label, max_half_red
        )
        if debug_mode:
            self._log_buffer_drops(
                silver_pre_cap, silver_buf, "top-N cap (solid red)", None
            )
            self._log_buffer_drops(
                gold_pre_cap, gold_buf, "top-N cap (half-red)", None
            )

        silver_balls = self._strip_conf(silver_buf)
        gold_balls = self._strip_conf(gold_buf)

        if debug_mode:
            kept_centers = {
                (int(x), int(y))
                for x, y, _r, _t, _c in silver_buf + gold_buf
            }
            self._draw_debug_window(
                frame,
                silver_balls,
                gold_balls,
                raw_detections=raw_detections,
                kept_centers=kept_centers,
                scoring_zones=scoring_zones,
            )

        return silver_balls, gold_balls

    # -------------------------------------------------------------- visualisation

    def _draw_debug_window(
        self,
        frame: np.ndarray,
        silver_balls: List[Tuple[int, int, float, str]],
        gold_balls: List[Tuple[int, int, float, str]],
        raw_detections: Optional[List[Tuple[int, int, float, str, float]]] = None,
        kept_centers: Optional[set] = None,
        scoring_zones: Optional[List[Tuple[int, int, int, int, int]]] = None,
    ) -> None:
        try:
            dbg = frame.copy()

            # Light outline of every scoring zone, so we can see whether a
            # missed detection actually lands inside the user-drawn zone.
            if scoring_zones:
                for z in scoring_zones:
                    if not (isinstance(z, (list, tuple)) and len(z) >= 4):
                        continue
                    try:
                        zx, zy, zw, zh = (
                            int(z[0]), int(z[1]), int(z[2]), int(z[3])
                        )
                    except (TypeError, ValueError):
                        continue
                    cv2.rectangle(
                        dbg, (zx, zy), (zx + zw, zy + zh), (180, 180, 0), 1
                    )

            # Faint outline for every RAW YOLO detection that did not survive
            # filtering. This makes it obvious when YOLO is producing boxes
            # that our filters are throwing away.
            if raw_detections:
                kept = kept_centers or set()
                for x, y, r, btype, conf in raw_detections:
                    if (int(x), int(y)) in kept:
                        continue
                    cv2.circle(
                        dbg,
                        (int(x), int(y)),
                        max(2, int(r)),
                        (128, 128, 128),
                        1,
                    )
                    cv2.putText(
                        dbg,
                        f"{btype}? {conf:.2f}",
                        (int(x) + 6, int(y) + 12),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.35,
                        (128, 128, 128),
                        1,
                        cv2.LINE_AA,
                    )

            for x, y, r, btype in silver_balls:
                if _is_solid_red_label(btype):
                    color = (0, 0, 255)
                elif "white" in _normalize_label(btype):
                    color = (255, 255, 0)
                else:
                    color = (200, 200, 200)
                cv2.circle(dbg, (int(x), int(y)), int(max(2, r)), color, 2)
                cv2.putText(
                    dbg,
                    btype,
                    (int(x) + 6, int(y) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    color,
                    1,
                    cv2.LINE_AA,
                )
            for x, y, r, btype in gold_balls:
                color = (0, 215, 255)
                cv2.circle(dbg, (int(x), int(y)), int(max(2, r)), color, 2)
                cv2.putText(
                    dbg,
                    btype,
                    (int(x) + 6, int(y) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    color,
                    1,
                    cv2.LINE_AA,
                )
            cv2.imshow("Ball Detection", dbg)
            cv2.waitKey(1)
        except cv2.error:
            logger.debug("Ball Detection debug window unavailable (headless / no GUI).")
