# scoring_logic.py
"""
Core scoring logic for the Whiffle Tracker project.

Given the per-frame ``tracked_balls`` list in :class:`game_state.GameState`,
this module:

1. Logs ball positions to the data logger (used by the heatmap).
2. Decides whether each tracked ball is in a scoring zone and stable.
3. Applies score, multiplier and special-hole rules, then updates the
   player, replay manager, achievements counters and game-mode side-effects
   (e.g. survival mode time bonus).

The entry point is :func:`update_scoring`, called once per game-loop frame
from ``game_state_utils.update_scoring`` (the thin wrapper used elsewhere).

Compared to the previous implementation, this version:

* Tracks zone stability by **zone index**, not by ``id(zone)`` of the tuple,
  which was fragile across reloads / mutations of ``scoring_zones``.
* Saves scored positions for **every** ball type, not just solid red, so a
  tracker ID flip on a settled ball does not double-score it.
* Cleanly removes dead state for vanished tracked-ball IDs.
* Has a single, well-defined scoring path with explicit log lines.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from constants import GameConstants
from effects import BallTrail, Explosion
from game_state_helpers import (
    is_ball_at_rest,
    play_sound,
    save_score,
    show_notification,
)
from game_types import CurrentGameState
from scoring import is_in_scoring_zone

logger = logging.getLogger(__name__)

BallTuple = Tuple[int, int, float, int, int, str]
Zone = Tuple[int, int, int, int, int]

CLEANUP_INTERVAL_FRAMES: int = 30
SCORED_POSITION_MAX_ENTRIES: int = 120
SCORED_POSITION_TRIM_TO: int = 80

MULTIPLIER_BALL_TYPES: Dict[str, float] = {
    "gold": 2.0,
    "yellow": 2.0,
    "red": 2.0,
    "half red": 1.5,
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _normalize_label(label: Optional[str]) -> str:
    if not label:
        return ""
    return str(label).lower().replace("_", " ").replace("-", " ").strip()


def _is_solid_red_ball_type(b_type: Optional[str]) -> bool:
    """Solid player-red label, matching the convention used by detection.py."""
    name = _normalize_label(b_type)
    if not name:
        return False
    if "half" in name:
        return False
    return "red" in name


def _score_multiplier(b_type: Optional[str]) -> float:
    """Multiplier applied to a base zone value for a given ball type label."""
    name = _normalize_label(b_type)
    if not name:
        return 1.0
    # Half-X (e.g. half-red) takes precedence; otherwise check the rich
    # multiplier types. Default to 1.0 for plain silver / white / unknown.
    if "half" in name:
        return MULTIPLIER_BALL_TYPES.get("half red", 1.5)
    for key, mult in MULTIPLIER_BALL_TYPES.items():
        if key == "half red":
            continue
        if key in name:
            return mult
    return 1.0


def _find_zone_for_ball(
    x: float,
    y: float,
    r: float,
    ball_id: int,
    scoring_zones: List[Zone],
) -> Tuple[Optional[Zone], int]:
    """Return ``(zone, idx)`` if the ball center is inside any zone, else ``(None, -1)``."""
    for i, z in enumerate(scoring_zones):
        if not (isinstance(z, (list, tuple)) and len(z) == 5):
            continue
        try:
            if is_in_scoring_zone((int(x), int(y), float(r), int(ball_id)), z):
                return z, i
        except Exception as exc:
            logger.debug("is_in_scoring_zone raised for ball %s / zone %d: %s", ball_id, i, exc)
            continue
    return None, -1


def _ensure_dict(game_state: Any, attr: str) -> Dict[Any, Any]:
    """Return ``getattr(game_state, attr)``, recreating an empty dict if missing/wrong type."""
    value = getattr(game_state, attr, None)
    if not isinstance(value, dict):
        value = {}
        setattr(game_state, attr, value)
    return value


def _ensure_list(game_state: Any, attr: str) -> List[Any]:
    value = getattr(game_state, attr, None)
    if not isinstance(value, list):
        value = []
        setattr(game_state, attr, value)
    return value


def _update_zone_stability(
    ball_id: int,
    zone_idx: int,
    history: Dict[int, List[int]],
    frames_required: int,
) -> bool:
    """Update the per-ball zone-index history and return whether the ball is stable.

    A ball is "stable" when its most recent ``frames_required`` history entries
    are all the same non-negative zone index. ``zone_idx`` of ``-1`` means
    "not in any zone".
    """
    if frames_required < 1:
        frames_required = 1
    queue = history.get(ball_id)
    if queue is None:
        queue = []
        history[ball_id] = queue
    queue.append(int(zone_idx))
    if len(queue) > frames_required:
        del queue[: len(queue) - frames_required]
    if len(queue) < frames_required:
        return False
    first = queue[0]
    if first < 0:
        return False
    return all(v == first for v in queue)


def _suppress_old_state(
    game_state: Any, live_ball_ids: set, frame_count: int
) -> None:
    """Drop per-ball state for ball ids that have aged out of ``tracked_balls``."""
    if frame_count % CLEANUP_INTERVAL_FRAMES != 0:
        return

    state_dict_names = (
        "ball_states",
        "previous_ball_states",
        "ball_positions_history",
        "ball_zone_history",
        "balls_in_zone",
        "ball_scored_zones",
        "active_trails",
    )
    keys_to_remove: set = set()
    for name in state_dict_names:
        state_dict = getattr(game_state, name, None)
        if isinstance(state_dict, dict):
            keys_to_remove.update(set(state_dict.keys()) - live_ball_ids)
    if not keys_to_remove:
        return
    logger.debug("Cleaning per-ball state for vanished ids: %s", sorted(keys_to_remove))
    for name in state_dict_names:
        state_dict = getattr(game_state, name, None)
        if isinstance(state_dict, dict):
            for ball_id in keys_to_remove:
                state_dict.pop(ball_id, None)


def _record_scored_position(
    game_state: Any, center: Tuple[int, int], ball_id: int
) -> None:
    """Remember a scored position so a tracker-id flip cannot double-score it."""
    sp = _ensure_dict(game_state, "scored_positions")
    sp[(int(center[0]), int(center[1]))] = int(ball_id)
    if len(sp) > SCORED_POSITION_MAX_ENTRIES:
        for k in list(sp.keys())[: len(sp) - SCORED_POSITION_TRIM_TO]:
            sp.pop(k, None)


def _clear_scored_positions_around_zone(
    game_state: Any, zone: Zone, margin: int = 35
) -> None:
    """Forget scored positions inside the bounding box of ``zone`` (+ ``margin`` px)."""
    sp = getattr(game_state, "scored_positions", None)
    if not isinstance(sp, dict) or not sp:
        return
    if not (isinstance(zone, (list, tuple)) and len(zone) >= 4):
        return
    zx, zy, zw, zh = int(zone[0]), int(zone[1]), int(zone[2]), int(zone[3])
    for key in list(sp.keys()):
        kx, ky = key[0], key[1]
        if (
            zx - margin <= kx <= zx + zw + margin
            and zy - margin <= ky <= zy + zh + margin
        ):
            sp.pop(key, None)


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------


def update_scoring(game_state: Any) -> None:
    """Process tracked balls, award score for zone hits, and update side-effects."""
    tracked_balls: List[BallTuple] = getattr(game_state, "tracked_balls", [])
    if not isinstance(tracked_balls, list):
        logger.error("game_state.tracked_balls is not a list; aborting update_scoring.")
        return

    current_time = time.time()
    frame_count = int(getattr(game_state, "frame_count", 0))
    debug_mode = bool(getattr(game_state, "debug_mode", False))

    if hasattr(game_state, "data_logger") and game_state.data_logger and tracked_balls:
        try:
            game_state.data_logger.log_ball_positions(tracked_balls)
        except Exception as exc:
            logger.error("Error logging ball positions: %s", exc)

    live_ids = {b[3] for b in tracked_balls if len(b) >= 6}
    _suppress_old_state(game_state, live_ids, frame_count)

    scoring_zones: List[Zone] = getattr(game_state, "scoring_zones", []) or []
    if not isinstance(scoring_zones, list):
        logger.error("game_state.scoring_zones is not a list; nothing to score.")
        return

    # Make sure required state containers exist before we try to mutate them.
    ball_positions_history = _ensure_dict(game_state, "ball_positions_history")
    ball_zone_history = _ensure_dict(game_state, "ball_zone_history")
    ball_states = _ensure_dict(game_state, "ball_states")
    previous_ball_states = _ensure_dict(game_state, "previous_ball_states")
    zone_cooldown = _ensure_dict(game_state, "zone_cooldown")
    ball_scored_zones = _ensure_dict(game_state, "ball_scored_zones")
    balls_in_zone = _ensure_dict(game_state, "balls_in_zone")
    scored_balls = _ensure_list(game_state, "scored_balls")
    active_trails = _ensure_dict(game_state, "active_trails")
    active_explosions = _ensure_list(game_state, "active_explosions")

    stability_frames_required = max(1, int(GameConstants.ZONE_STABILITY_FRAMES))
    cooldown_seconds = float(GameConstants.SCORE_COOLDOWN_DURATION) / 1000.0

    zone_balls_this_frame: Dict[int, List[int]] = {}
    newly_scored_pts = 0

    for ball in tracked_balls:
        if len(ball) < 6:
            logger.debug("Skipping malformed tracked ball: %r", ball)
            continue
        try:
            x, y, r, ball_id, _age, b_type = ball
            x_f = float(x)
            y_f = float(y)
            r_f = float(r)
            ball_id = int(ball_id)
            b_type = str(b_type) if b_type is not None else ""
        except (ValueError, TypeError) as exc:
            logger.debug("Skipping ball that failed to unpack: %r (%s)", ball, exc)
            continue

        center = (int(x_f), int(y_f))

        # --- position history (drives at-rest detection + heatmap)
        positions = ball_positions_history.setdefault(ball_id, [])
        positions.append((center, current_time))
        max_len = max(1, int(GameConstants.POSITION_HISTORY_LENGTH))
        while len(positions) > max_len or (
            positions and current_time - positions[0][1] > 5.0
        ):
            positions.pop(0)

        # --- fun / retro trail
        if (
            getattr(game_state, "game_mode", "") in ("fun", "retro")
            and isinstance(active_trails, dict)
        ):
            trail = active_trails.get(ball_id)
            if trail is None:
                trail = BallTrail(ball_id)
                active_trails[ball_id] = trail
            trail.add_position(center)

        zone, zone_idx = _find_zone_for_ball(x_f, y_f, r_f, ball_id, scoring_zones)

        at_rest = is_ball_at_rest(ball_id, ball_positions_history, debug_mode)
        stable = _update_zone_stability(
            ball_id, zone_idx, ball_zone_history, stability_frames_required
        )

        previous_ball_states[ball_id] = ball_states.get(ball_id, {}).copy()
        ball_states[ball_id] = {
            "at_rest": at_rest,
            "stable": stable,
            "zone": zone,
            "idx": zone_idx,
            "time": current_time,
        }

        if zone is not None and zone_idx >= 0 and stable:
            awarded = _try_award_score(
                game_state=game_state,
                ball_id=ball_id,
                b_type=b_type,
                center=center,
                zone=zone,
                zone_idx=zone_idx,
                current_time=current_time,
                cooldown_seconds=cooldown_seconds,
                zone_cooldown=zone_cooldown,
                ball_scored_zones=ball_scored_zones,
                balls_in_zone=balls_in_zone,
                scored_balls=scored_balls,
                active_explosions=active_explosions,
                zone_balls_this_frame=zone_balls_this_frame,
                live_ids=live_ids,
                debug_mode=debug_mode,
            )
            if awarded > 0:
                newly_scored_pts += awarded
        else:
            _maybe_clear_after_leaving_zone(
                game_state=game_state,
                ball_id=ball_id,
                x_f=x_f,
                y_f=y_f,
                r_f=r_f,
                ball_scored_zones=ball_scored_zones,
                balls_in_zone=balls_in_zone,
                scored_balls=scored_balls,
                scoring_zones=scoring_zones,
            )

    if newly_scored_pts > 0:
        play_sound(game_state, getattr(game_state, "score_sound", None))


# ---------------------------------------------------------------------------
# award helpers
# ---------------------------------------------------------------------------


def _try_award_score(
    *,
    game_state: Any,
    ball_id: int,
    b_type: str,
    center: Tuple[int, int],
    zone: Zone,
    zone_idx: int,
    current_time: float,
    cooldown_seconds: float,
    zone_cooldown: Dict[Tuple[int, int], float],
    ball_scored_zones: Dict[int, int],
    balls_in_zone: Dict[int, Zone],
    scored_balls: List[int],
    active_explosions: List[Any],
    zone_balls_this_frame: Dict[int, List[int]],
    live_ids: Optional[set] = None,
    debug_mode: bool = False,
) -> int:
    """Apply scoring for one stable ball/zone pair. Returns points awarded (0 if blocked).

    The cooldown is intentionally per-(zone, ball). The original implementation
    keyed the cooldown by zone index only, which meant that several distinct
    balls landing in the same zone (e.g. multiple balls in the right-side
    gutter / 1-pt drain) would silently lose all but the first hit for
    ``cooldown_seconds``. The per-(zone, ball) key still prevents a single
    ball from rapid-fire re-scoring (the original intent) while letting every
    physical ball count once.
    """
    cooldown_key = (zone_idx, ball_id)
    cooldown_until = zone_cooldown.get(cooldown_key, 0.0)
    if current_time < cooldown_until:
        if debug_mode:
            logger.debug(
                "Ball %s blocked by zone %d cooldown for %.2fs more.",
                ball_id,
                zone_idx,
                cooldown_until - current_time,
            )
        return 0

    # Already scored this entry?
    if ball_scored_zones.get(ball_id) == zone_idx:
        if debug_mode:
            logger.debug("Ball %s already scored in zone %d this entry.", ball_id, zone_idx)
        return 0

    # Same physical spot already scored under a different tracker id?
    if _position_already_scored(game_state, center, ball_id, live_ids):
        if debug_mode:
            logger.debug(
                "Position %s already scored under a different ball id; suppressing.",
                center,
            )
        # Still record this ball as having scored to keep cleanup symmetrical.
        ball_scored_zones[ball_id] = zone_idx
        balls_in_zone[ball_id] = zone
        return 0

    zone_balls_this_frame.setdefault(zone_idx, []).append(ball_id)

    base_pts = int(zone[4]) if len(zone) >= 5 else 0
    is_special = zone == getattr(game_state, "special_hole", None)
    if is_special:
        # The special hole's "reward" is the end-of-session score doubling;
        # the immediate points are whatever the zone's own value is so that
        # the running total matches the per-ball/per-zone arithmetic the
        # player sees on the playfield (no surprise +100 bonus).
        if not getattr(game_state, "special_hole_hit_this_session", False):
            logger.info(
                "*** First special-hole hit this session -- end score will double. ***"
            )
            show_notification(
                game_state, "Special Hole Hit! Score will double!", duration=3.0
            )
        game_state.special_hole_hit_this_session = True
        game_state.special_hole_hits_this_session = (
            int(getattr(game_state, "special_hole_hits_this_session", 0)) + 1
        )

    multiplier = _score_multiplier(b_type)
    points = int(round(base_pts * multiplier))
    if points <= 0:
        if debug_mode:
            logger.debug(
                "Zone %d has non-positive base points (%d * %.2f); skipping score.",
                zone_idx,
                base_pts,
                multiplier,
            )
        return 0

    # Achievements / per-session bookkeeping.
    if multiplier > 1.0:
        game_state.points_from_multiplier_balls_this_game = (
            int(getattr(game_state, "points_from_multiplier_balls_this_game", 0)) + points
        )
    label = _normalize_label(b_type)
    if "half" in label:
        game_state.scored_half_red_this_session = True
    elif "red" in label or "gold" in label or "yellow" in label:
        game_state.scored_red_ball_this_session = True

    game_state.score = int(getattr(game_state, "score", 0)) + points

    # Update player object (skips persistent XP in static-image mode).
    try:
        current_player = (
            game_state.get_current_player()
            if hasattr(game_state, "get_current_player")
            else None
        )
        if current_player is not None:
            is_double_ball = len(zone_balls_this_frame.get(zone_idx, [])) > 1
            if is_double_ball:
                current_player.consecutive_double_balls = (
                    int(getattr(current_player, "consecutive_double_balls", 0)) + 1
                )
            else:
                current_player.consecutive_double_balls = 0

            if getattr(game_state, "camera_available", True):
                did_level_up = current_player.add_score(
                    points,
                    zone=zone,
                    is_special_hole=is_special,
                    is_double_ball=is_double_ball,
                )
                if did_level_up:
                    show_notification(
                        game_state,
                        f"Level Up! Now level {current_player.level}",
                        duration=3.0,
                    )
            else:
                current_player.score = int(getattr(current_player, "score", 0)) + points
                current_player.total_score = (
                    int(getattr(current_player, "total_score", 0)) + points
                )
        else:
            logger.warning("No current player available; score recorded only on game_state.")
    except Exception as exc:
        logger.error("Error updating current player after score: %s", exc)

    # Logging / replay / data-logger side effects.
    if hasattr(game_state, "data_logger") and game_state.data_logger:
        try:
            game_state.data_logger.log_score_event(
                zone_id=zone_idx, points=points, ball_type=b_type
            )
        except Exception as exc:
            logger.error("Error logging score event: %s", exc)

    if (
        getattr(game_state, "camera_available", True)
        and getattr(game_state, "replay_manager", None) is not None
    ):
        try:
            game_state.replay_manager.record_score(
                zone_id=zone_idx, points=points, ball_type=b_type
            )
        except Exception as exc:
            logger.error("Error recording score in replay: %s", exc)

    # Survival mode time bonus.
    if getattr(game_state, "game_mode", "") == "survival":
        time_gain = float(
            getattr(GameConstants, "SURVIVAL_MODE_TIME_GAIN_PER_SCORE", 5.0)
        )
        if getattr(game_state, "game_timer", None) is not None:
            game_state.game_timer = float(game_state.game_timer) + time_gain
            logger.info(
                "Survival Mode: +%.1fs (timer now %.1fs)", time_gain, game_state.game_timer
            )
            show_notification(
                game_state, f"+{time_gain:.0f} Secs!", duration=1.0, is_error=False
            )

    # Mark ball as scored.
    if ball_id not in scored_balls:
        scored_balls.append(ball_id)
    balls_in_zone[ball_id] = zone
    ball_scored_zones[ball_id] = zone_idx
    _record_scored_position(game_state, center, ball_id)

    zone_cooldown[cooldown_key] = current_time + cooldown_seconds

    logger.info(
        "Ball %s (%s) scored %d pts [base=%d, mult=%.2f] in zone %d%s. Total=%d. "
        "Zone %d cooldown=%.1fs.",
        ball_id,
        b_type,
        points,
        base_pts,
        multiplier,
        zone_idx,
        " (special)" if is_special else "",
        game_state.score,
        zone_idx,
        cooldown_seconds,
    )

    # Fun / retro explosion at zone center.
    if getattr(game_state, "game_mode", "") in ("fun", "retro"):
        try:
            zx, zy, zw, zh, _ = zone
            active_explosions.append(Explosion(int(zx + zw / 2), int(zy + zh / 2)))
        except Exception as exc:
            logger.debug("Could not spawn explosion for zone %d: %s", zone_idx, exc)

    _maybe_handle_win_condition(game_state)
    return points


def _position_already_scored(
    game_state: Any,
    center: Tuple[int, int],
    ball_id: int,
    live_ids: Optional[set] = None,
) -> bool:
    """True if a nearby scored position should suppress this ball as a duplicate.

    Nearby positions only count as "the same physical ball" when the original
    scoring tracker id is no longer live. If the originally-scoring tracker is
    still being tracked this frame, this must be a *different* physical ball
    that just happens to have landed near the first one (multiple balls in the
    same zone), and we must let it score.

    A match against the caller's own ``ball_id`` always suppresses, so a single
    ball never double-scores from a single entry.
    """
    sp = getattr(game_state, "scored_positions", None)
    if not isinstance(sp, dict) or not sp:
        return False
    suppress_radius = 60
    cx, cy = int(center[0]), int(center[1])
    r_sq = suppress_radius * suppress_radius
    for (sx, sy), recorded_id in sp.items():
        if (cx - sx) ** 2 + (cy - sy) ** 2 >= r_sq:
            continue
        if recorded_id == ball_id:
            return True
        # If the original ball is still alive as a *distinct* tracker, this is
        # a physically different ball -- don't suppress it.
        if live_ids is not None and recorded_id in live_ids:
            continue
        # Original tracker is gone -> treat as tracker-id flip and suppress.
        return True
    return False


def _maybe_clear_after_leaving_zone(
    *,
    game_state: Any,
    ball_id: int,
    x_f: float,
    y_f: float,
    r_f: float,
    ball_scored_zones: Dict[int, int],
    balls_in_zone: Dict[int, Zone],
    scored_balls: List[int],
    scoring_zones: List[Zone],
) -> None:
    """If a ball has fully left the hole it scored in, allow it to re-score on re-entry."""
    if ball_id not in ball_scored_zones:
        return
    last_idx = ball_scored_zones[ball_id]
    if not (0 <= last_idx < len(scoring_zones)):
        ball_scored_zones.pop(ball_id, None)
        balls_in_zone.pop(ball_id, None)
        return
    last_zone = scoring_zones[last_idx]
    if not (isinstance(last_zone, (list, tuple)) and len(last_zone) == 5):
        ball_scored_zones.pop(ball_id, None)
        balls_in_zone.pop(ball_id, None)
        return
    try:
        still_inside = is_in_scoring_zone(
            (int(x_f), int(y_f), float(r_f), int(ball_id)), last_zone
        )
    except Exception as exc:
        logger.debug("is_in_scoring_zone errored during clear: %s", exc)
        still_inside = False
    if still_inside:
        return
    ball_scored_zones.pop(ball_id, None)
    balls_in_zone.pop(ball_id, None)
    if ball_id in scored_balls:
        try:
            scored_balls.remove(ball_id)
        except ValueError:
            pass
    _clear_scored_positions_around_zone(game_state, last_zone)
    logger.debug(
        "Ball %s left scored zone %d; re-entry can score again.", ball_id, last_idx
    )


def _maybe_handle_win_condition(game_state: Any) -> None:
    """Trigger save / record-completed flow when the game reaches the win threshold."""
    game_mode = getattr(game_state, "game_mode", "")
    if game_mode not in ("timed", "survival"):
        return
    score = int(getattr(game_state, "score", 0))
    win_score = int(getattr(game_state, "win_score", 0))
    if win_score <= 0 or score < win_score:
        return
    if getattr(game_state, "current_state", None) == CurrentGameState.GAME_OVER:
        return
    game_state.win_condition_met = True
    logger.info("Win condition met! Score %d >= %d", score, win_score)
    try:
        from game_state_utils import record_game_completed

        record_game_completed(game_state)
    except Exception as exc:
        logger.warning("record_game_completed failed: %s", exc)
    try:
        player_name = "Unknown"
        if hasattr(game_state, "get_current_player"):
            player = game_state.get_current_player()
            if player is not None and hasattr(player, "name"):
                player_name = str(player.name or "Unknown")
        save_score(game_state, player_name)
    except Exception as exc:
        logger.error("Error saving score on win condition: %s", exc)
