# effects.py
"""
Visual effects like ball trails and explosions for Whiffle Tracker Fun Mode.
"""

import cv2
import numpy as np
import random
import time
from typing import List, Tuple, Dict

# Trail parameters (remain as red fade to black)
TRAIL_MAX_LENGTH = 20
TRAIL_START_COLOR = (0, 0, 255)  # Red (BGR)
TRAIL_END_COLOR = (0, 0, 0)  # Black (BGR)
TRAIL_START_THICKNESS = 2
TRAIL_END_THICKNESS = 1

# --- ADJUSTED EXPLOSION PARAMETERS ---
EXPLOSION_PARTICLE_COUNT = 40  # Increased from 20
EXPLOSION_DURATION = 0.6  # Increased from 0.4 seconds
EXPLOSION_MAX_SPEED = 180  # Increased from 120 pixels per second
EXPLOSION_PARTICLE_SIZE = 3  # Increased from 2
EXPLOSION_GRAVITY = 150  # Pixels per second^2 (pulls particles down)
EXPLOSION_COLORS = [
    (0, 255, 255),  # Yellow
    (255, 190, 0),  # Lighter Orange
    (255, 255, 255),  # Pure White (Added)
    (50, 50, 255),  # Lighter Red
    (0, 220, 255),  # Bright Yellow (Added)
]
# --- END ADJUSTED EXPLOSION PARAMETERS ---


class BallTrail:
    """Manages the trail effect for a single ball."""

    def __init__(self, ball_id: int):
        self.ball_id = ball_id
        self.positions: List[Tuple[int, int]] = []

    def add_position(self, position: Tuple[int, int]):
        """Adds a new position to the trail."""
        if not self.positions or self.positions[-1] != position:
            self.positions.append(position)
            if len(self.positions) > TRAIL_MAX_LENGTH:
                self.positions.pop(0)

    def draw(self, frame: np.ndarray):
        """Draws the trail onto the frame with fading color and thickness."""
        num_points = len(self.positions)
        if num_points < 2:
            return

        for i in range(num_points - 1):
            pt1 = self.positions[i]
            pt2 = self.positions[i + 1]
            if pt1 == pt2:
                continue

            fade_ratio = (i / (num_points - 1)) if num_points > 1 else 0
            color = tuple(
                int(c1 + (c2 - c1) * fade_ratio)
                for c1, c2 in zip(TRAIL_START_COLOR, TRAIL_END_COLOR)
            )
            thickness = int(
                TRAIL_START_THICKNESS
                + (TRAIL_END_THICKNESS - TRAIL_START_THICKNESS) * fade_ratio
            )
            thickness = max(1, thickness)

            try:
                cv2.line(frame, pt1, pt2, color, thickness, lineType=cv2.LINE_AA)
            except OverflowError:
                pass
            except Exception as e:
                print(f"Error drawing trail line: {e}")


class Explosion:
    """Manages a particle explosion effect."""

    def __init__(self, center_x: int, center_y: int):
        self.center_x = center_x
        self.center_y = center_y
        self.start_time = time.time()
        self.particles = []  # List of [x, y, vx, vy, color]

        for _ in range(EXPLOSION_PARTICLE_COUNT):
            angle = random.uniform(0, 2 * np.pi)
            # Give a slightly stronger initial upward bias to counteract gravity a bit
            speed = random.uniform(EXPLOSION_MAX_SPEED * 0.4, EXPLOSION_MAX_SPEED)
            vx = np.cos(angle) * speed
            vy = np.sin(angle) * speed - random.uniform(
                0, EXPLOSION_GRAVITY * 0.1
            )  # Slight upward nudge
            color = random.choice(EXPLOSION_COLORS)
            self.particles.append([float(center_x), float(center_y), vx, vy, color])

    def update(self, dt: float):
        """Updates particle positions, adding gravity."""
        for p in self.particles:
            # Apply gravity
            p[3] += EXPLOSION_GRAVITY * dt  # Increase y-velocity (downward)

            # Update position
            p[0] += p[2] * dt  # Update x
            p[1] += p[3] * dt  # Update y

            # Optional: Add drag/friction
            # drag = 0.1
            # p[2] *= (1 - drag * dt)
            # p[3] *= (1 - drag * dt)

    def is_active(self) -> bool:
        """Checks if the explosion duration has passed."""
        return (time.time() - self.start_time) < EXPLOSION_DURATION

    def draw(self, frame: np.ndarray):
        """Draws the particles onto the frame."""
        elapsed_time = time.time() - self.start_time
        # Optional: Fade out particles over time using alpha (might affect performance slightly)
        # If performance is an issue, remove alpha calculation and blending.
        alpha_blend = 0.5 + 0.5 * (
            1.0 - (elapsed_time / EXPLOSION_DURATION)
        )  # Fade alpha from 1.0 down to 0.5
        alpha_blend = max(0.0, min(1.0, alpha_blend))

        if alpha_blend <= 0:
            return

        overlay = frame.copy()  # Create overlay for alpha blending particles
        output = frame  # Final output frame

        for p in self.particles:
            x, y, _, _, color = p
            try:
                # Draw particle onto the overlay
                cv2.circle(
                    overlay,
                    (int(x), int(y)),
                    EXPLOSION_PARTICLE_SIZE,
                    color,
                    -1,
                    lineType=cv2.LINE_AA,
                )
            except OverflowError:
                pass
            except Exception as e:
                print(f"Error drawing explosion particle: {e}")

        # Blend the overlay with the original frame
        try:
            cv2.addWeighted(overlay, alpha_blend, output, 1 - alpha_blend, 0, output)
        except cv2.error as e:
            # Fallback if blending fails, just draw directly (no transparency)
            print(f"Warning: addWeighted failed ({e}). Drawing particles directly.")
            for p in self.particles:
                x, y, _, _, color = p
                try:
                    cv2.circle(
                        frame,
                        (int(x), int(y)),
                        EXPLOSION_PARTICLE_SIZE,
                        color,
                        -1,
                        lineType=cv2.LINE_AA,
                    )
                except:
                    pass  # Ignore errors in fallback
