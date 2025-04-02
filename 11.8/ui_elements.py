import cv2
import numpy as np
import logging
from typing import List, Tuple

# Local project imports
from game_constants import UIConstants, GameConstants
from game_state import GameState

logger = logging.getLogger(__name__)

# Constants for ball visualization
BALL_COLORS = {
    "white": UIConstants.WHITE,
    "red": UIConstants.RED,
    "half": (255, 0, 255),  # Magenta for half red/half white
}
TRAIL_LENGTH = GameConstants.BALL_TRAIL_LENGTH
TRAIL_THICKNESS = 2
TRAIL_BASE_COLOR = (180, 180, 180)
BALL_OUTLINE_THICKNESS = 2


def draw_balls(frame: np.ndarray, game_state: GameState) -> None:
    """
    Draw tracked balls (as outlines) and optionally their fading trails.
    Args:
        frame (np.ndarray): The frame to draw on.
        game_state (GameState): The current game state containing tracked balls and trails.
    """
    # --- Log Check ---
    trail_flag_value = getattr(game_state, 'ball_trails_enabled', 'AttributeNotFound')
    logger.debug(f"Checking ball_trails_enabled flag. Value: {trail_flag_value}")
    # ---

    # --- MODIFIED: If trails are disabled, draw NOTHING related to balls ---
    if not game_state.ball_trails_enabled:
        logger.debug("ball_trails_enabled is False. Skipping ALL ball/trail drawing.")
        return # Exit the function entirely, do not draw balls or trails
    # --- END MODIFICATION ---

    # --- This code only runs if ball_trails_enabled is TRUE ---
    logger.debug("ball_trails_enabled is True. Drawing balls and trails...")

    # --- Draw Balls First (only if trails are enabled) ---
    ball_types = {}
    if hasattr(game_state, "tracked_balls"):
        for ball in game_state.tracked_balls:
             try:
                 if len(ball) >= 6:
                     x, y, radius, ball_id, _, ball_type = ball[:6]
                     center_x, center_y, int_radius = int(x), int(y), int(max(1, radius))
                     color = BALL_COLORS.get(ball_type, UIConstants.YELLOW)
                     # Draw the ball outline
                     cv2.circle(frame, (center_x, center_y), int_radius, color, BALL_OUTLINE_THICKNESS)
                     ball_types[ball_id] = ball_type
             except (IndexError, ValueError, TypeError) as e:
                 logger.warning(f"Error processing ball data for drawing ball: {ball}. Error: {e}")
    # --- END Draw Balls ---

    # --- Draw Trails (only if trails are enabled) ---
    drawn_trail_ids = set()
    if hasattr(game_state, "ball_trails") and game_state.ball_trails:
        for ball_id, trail in list(game_state.ball_trails.items()):
            drawn_trail_ids.add(ball_id)
            if ball_id not in ball_types: # Check if ball still exists
                if ball_id in game_state.ball_trails:
                    del game_state.ball_trails[ball_id]
                continue

            if len(trail) > 1:
                points = np.array(trail, dtype=np.int32)
                num_segments = len(trail) - 1

                for i in range(num_segments):
                    # Faster Fade Logic
                    progress = (num_segments - i) / max(1, num_segments)
                    fade_factor = progress ** 2

                    thickness = max(1, int(TRAIL_THICKNESS * fade_factor))
                    segment_color = tuple(int(c * fade_factor) for c in TRAIL_BASE_COLOR)

                    try:
                        pt1 = tuple(points[i])
                        pt2 = tuple(points[i+1])
                        if thickness > 0:
                            cv2.line(frame, pt1, pt2, segment_color, thickness, cv2.LINE_AA)
                    except Exception as e:
                        logger.warning(f"Error drawing trail segment for ball {ball_id}: {e}")

    # Trail cleanup (only if trails are enabled)
    if hasattr(game_state, "ball_trails"):
         active_ball_ids = set(ball_types.keys())
         for ball_id in list(game_state.ball_trails.keys()):
              if ball_id not in active_ball_ids:
                   logger.debug(f"Removing trail for ball ID {ball_id} no longer present.")
                   del game_state.ball_trails[ball_id]
    # --- END Draw Trails ---


# Debug Overlay (Unchanged)
def _draw_debug_overlay(
    frame: np.ndarray, game_state: GameState
) -> None:
    if hasattr(game_state, "tracked_balls"):
        for ball in game_state.tracked_balls:
            try:
                if len(ball) >= 6:
                    x, y, radius, ball_id, age, ball_type = ball[:6]
                    center_x, center_y, int_radius = int(x), int(y), int(radius)
                    pt1 = (center_x - int_radius, center_y - int_radius)
                    pt2 = (center_x + int_radius, center_y + int_radius)
                    cv2.rectangle(frame, pt1, pt2, UIConstants.YELLOW, 1)
                    label = f"ID:{ball_id} T:{ball_type}"
                    (w, h), _ = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, 1
                    )
                    text_x, text_y = pt1[0], pt1[1] - 5
                    cv2.rectangle(
                        frame,
                        (text_x, text_y - h - 2),
                        (text_x + w, text_y + 2),
                        (0, 0, 0),
                        -1,
                    )
                    cv2.putText(
                        frame,
                        label,
                        (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        UIConstants.FONT_SCALE_SMALL,
                        UIConstants.YELLOW,
                        1,
                    )
                else:
                    logger.warning(
                        f"Skipping debug draw for malformed ball data (length < 6): {ball}"
                    )
            except (IndexError, ValueError, TypeError) as e:
                logger.warning(
                    f"Error processing ball data for debug overlay: {ball}. Error: {e}"
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error drawing debug overlay for ball {ball}: {e}"
                )
    else:
        logger.debug(
            "No tracked_balls attribute found in game_state for debug overlay."
        )