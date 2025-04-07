# ui_elements.py
import logging

import cv2
import numpy as np

# Local project imports
from constants import UIConstants
# Import GameState for type hinting and accessing effects
from game_state import GameState

logger = logging.getLogger(__name__)

# Constants for ball visualization
BALL_COLORS = {
    "white": UIConstants.WHITE,
    "red": UIConstants.RED,
    "half": (255, 0, 255),
}
BALL_RADIUS_FACTOR = 1.0  # This might not be needed anymore if not drawing balls


def draw_balls(frame: np.ndarray, game_state: GameState) -> None:
    """
    Draw ball trails (if in Fun/Retro Mode) on the frame.
    Does NOT draw the balls themselves as filled circles anymore.
    Args:
        frame (np.ndarray): The frame to draw on.
        game_state (GameState): The current game state containing tracked balls and trails.
    """

    # --- Draw Ball Trails (Fun / Retro Mode Only) ---
    # --- START CHANGE: Include "retro" mode ---
    if game_state.game_mode in ["fun", "retro"]:
        # --- END CHANGE ---
        if hasattr(game_state, "active_trails"):
            for trail in game_state.active_trails.values():
                try:
                    trail.draw(frame)
                except Exception as e:
                    logger.error(
                        f"Error drawing trail for ball ID {trail.ball_id}: {e}"
                    )
        else:
            logger.warning("game_state missing 'active_trails' attribute.")
    # --- END RE-ENABLE ---

    # --- Draw Current Ball Positions ---
    # --- SECTION REMOVED/COMMENTED OUT - NO LONGER DRAWING FILLED CIRCLES ---
    # if hasattr(game_state, 'tracked_balls'):
    #     for ball_data in game_state.tracked_balls:
    #         try:
    #             if len(ball_data) >= 6:
    #                 x, y, radius, ball_id, age, ball_type = ball_data
    #                 center = (int(x), int(y))
    #                 draw_radius = int(radius * BALL_RADIUS_FACTOR)
    #                 color = BALL_COLORS.get(ball_type, UIConstants.YELLOW)
    #
    #                 # *** THIS LINE IS REMOVED/COMMENTED OUT ***
    #                 # cv2.circle(frame, center, draw_radius, color, -1)
    #                 # *** END REMOVAL ***
    #
    #             else:
    #                 logger.warning(f"Skipping ball draw for malformed data: {ball_data}")
    #
    #         except (IndexError, ValueError, TypeError) as e:
    #             logger.warning(f"Error processing ball data for drawing: {ball_data}. Error: {e}")
    #         except Exception as e:
    #             logger.error(f"Unexpected error drawing ball {ball_data}: {e}")
    # else:
    #     logger.debug("No tracked_balls attribute found in game_state for drawing.")
    # --- END SECTION REMOVAL ---


def _draw_debug_overlay(frame: np.ndarray, game_state: GameState) -> None:
    """Draws debugging information directly onto the frame."""
    # This function can remain as is, it draws boxes and text, not filled circles.
    if hasattr(game_state, "tracked_balls"):
        for ball in game_state.tracked_balls:
            try:
                if len(ball) >= 6:
                    x, y, radius, ball_id, age, ball_type = ball[:6]
                    center_x, center_y, int_radius = int(x), int(y), int(radius)
                    # Keep drawing the debug bounding box, but not the filled circle
                    pt1 = (center_x - int_radius, center_y - int_radius)
                    pt2 = (center_x + int_radius, center_y + int_radius)
                    cv2.rectangle(
                        frame, pt1, pt2, UIConstants.YELLOW, 1
                    )  # Bounding box
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
                        cv2.LINE_AA,
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
