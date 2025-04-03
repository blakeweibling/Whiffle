import cv2
import numpy as np
import logging
from typing import List, Tuple

# Local project imports
from constants import UIConstants, GameConstants
from game_state import GameState

logger = logging.getLogger(__name__)

# Constants for ball visualization
BALL_COLORS = {
    "white": UIConstants.WHITE,
    "red": UIConstants.RED,
    "half": (255, 0, 255),  # Magenta for half red/half white
}
BALL_RADIUS_FACTOR = 1.0
TRAIL_LENGTH = GameConstants.BALL_TRAIL_LENGTH
TRAIL_THICKNESS = 2
TRAIL_BASE_COLOR = (100, 100, 100)  # Base color for trails (Gray)
TRAIL_FADE = True  # Whether to fade the trail


def draw_balls(frame: np.ndarray, game_state: GameState) -> None:
    """
    Draw tracked balls and their trails on the frame (disabled).
    Args:
        frame (np.ndarray): The frame to draw on.
        game_state (GameState): The current game state containing tracked balls and trails.
    """
    # Clean up trails for balls no longer tracked, but don't draw anything
    if hasattr(game_state, "ball_trails") and game_state.ball_trails:
        for ball_id, trail in list(game_state.ball_trails.items()):
            # Check if the ball ID still exists in tracked_balls
            # Ensure tracked_balls itself exists first
            if not hasattr(game_state, "tracked_balls") or not any(
                hasattr(b, "__len__") and len(b) > 3 and b[3] == ball_id
                for b in game_state.tracked_balls
            ):
                if ball_id in game_state.ball_trails:
                    del game_state.ball_trails[ball_id]
                continue  # Skip drawing trail for untracked ball

    # Ball and trail drawing is disabled; no rendering occurs
    logger.debug("Ball drawing effects are disabled.")


# Feature 5: Draw Visual Debug Overlay
def _draw_debug_overlay(
    frame: np.ndarray, game_state: GameState
) -> None:  # Use GameState type hint
    """Draws debugging information directly onto the frame."""
    if hasattr(game_state, "tracked_balls"):
        for ball in game_state.tracked_balls:
            try:
                # Ensure ball has enough elements before unpacking
                if len(ball) >= 6:
                    x, y, radius, ball_id, age, ball_type = ball[
                        :6
                    ]  # Unpack only the first 6
                    center_x, center_y, int_radius = int(x), int(y), int(radius)
                    pt1 = (center_x - int_radius, center_y - int_radius)
                    pt2 = (center_x + int_radius, center_y + int_radius)
                    # Bounding box
                    cv2.rectangle(frame, pt1, pt2, UIConstants.YELLOW, 1)
                    label = f"ID:{ball_id} T:{ball_type}"
                    (w, h), _ = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, 1
                    )
                    text_x, text_y = pt1[0], pt1[1] - 5  # Position text above box
                    # Draw background for text
                    cv2.rectangle(
                        frame,
                        (text_x, text_y - h - 2),
                        (text_x + w, text_y + 2),
                        (0, 0, 0),
                        -1,
                    )  # Text bg
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

            except (
                IndexError,
                ValueError,
                TypeError,
            ) as e:  # Catch potential unpacking/conversion errors
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
