# replay_manager.py
"""
Manages the recording, saving, loading, and playback of game replays for the Whiffle Tracker.
"""

import logging
import time
import json
import os
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import base64
import uuid
import shutil
from constants import ReplayConstants

logger = logging.getLogger(__name__)

# Constants
REPLAY_DIR = "data/replays"
REPLAY_FILE_EXT = ".whr"  # Whiffle Replay format
REPLAY_TEMP_FRAMES_DIR = "data/replays/temp_frames"
KEYFRAME_INTERVAL = 60  # Save a keyframe every 60 frames (2 seconds at 30fps)
MAX_KEYFRAMES = (
    180  # Maximum number of keyframes to store per replay (6 min at 2s interval)
)
REPLAY_THUMBNAIL_SIZE = (320, 180)  # 16:9 aspect ratio thumbnail
MAX_REPLAY_HISTORY = 50  # Maximum number of replays to keep in history

# Default timestamps for highlight windows
DEFAULT_HIGHLIGHT_SECONDS_BEFORE = 3.0
DEFAULT_HIGHLIGHT_SECONDS_AFTER = 2.0


class ReplayFrame:
    """Represents a single frame in a replay sequence."""

    def __init__(
        self,
        timestamp: float,
        frame_count: int,
        balls: List[Tuple[int, int, float, int, int, str]],
        score: int,
        game_timer: Optional[float] = None,
        events: List[Dict[str, Any]] = None,
        keyframe_image: Optional[np.ndarray] = None,
    ):
        self.timestamp = timestamp
        self.frame_count = frame_count
        self.balls = balls.copy() if balls else []
        self.score = score
        self.game_timer = game_timer
        self.events = events.copy() if events else []
        self.keyframe_image = keyframe_image  # Optional image data for keyframes

    def to_dict(self) -> Dict[str, Any]:
        """Convert frame data to a dictionary for serialization."""
        result = {
            "timestamp": self.timestamp,
            "frame_count": self.frame_count,
            "balls": self.balls,
            "score": self.score,
            "events": self.events or [],
        }
        if self.game_timer is not None:
            result["game_timer"] = self.game_timer
        # The keyframe image is stored separately
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayFrame":
        """Create a ReplayFrame instance from a dictionary."""
        return cls(
            timestamp=data.get("timestamp", 0.0),
            frame_count=data.get("frame_count", 0),
            balls=data.get("balls", []),
            score=data.get("score", 0),
            game_timer=data.get("game_timer"),
            events=data.get("events", []),
            keyframe_image=None,  # Images are loaded separately
        )


class Replay:
    """Manages a complete game replay sequence."""

    def __init__(
        self,
        replay_id: str = None,
        player_name: str = "Player",
        game_mode: str = "classic",
        scoring_zones: List[Tuple[int, int, int, int, int]] = None,
    ):
        self.replay_id = replay_id or str(uuid.uuid4())
        self.player_name = player_name
        self.game_mode = game_mode
        self.scoring_zones = scoring_zones.copy() if scoring_zones else []
        self.creation_time = time.time()
        self.width = 0  # Will be set when first frame is captured
        self.height = 0  # Will be set when first frame is captured
        self.frames: List[ReplayFrame] = []
        self.score_events: List[Dict[str, Any]] = []
        self.final_score = 0
        self.duration = 0.0
        self.title = f"{player_name}'s {game_mode.capitalize()} Game"
        self.description = ""
        self.highlight_segments: List[Tuple[float, float, str]] = (
            []
        )  # [(start_time, end_time, description)]
        self.keyframe_timestamps: List[float] = (
            []
        )  # List of timestamps where keyframes exist
        self.recording = False
        self.modified = False

    def start_recording(self, resolution: Tuple[int, int]) -> None:
        """Start recording a new replay."""
        self.width, self.height = resolution
        self.recording = True
        self.frames = []
        self.keyframe_timestamps = []
        self.creation_time = time.time()
        logger.info(
            f"Started recording replay {self.replay_id} at {self.width}x{self.height}"
        )

        # Ensure temp directory exists
        if not os.path.exists(REPLAY_TEMP_FRAMES_DIR):
            os.makedirs(REPLAY_TEMP_FRAMES_DIR, exist_ok=True)

    def add_frame(
        self, game_state: Any, current_frame: Optional[np.ndarray] = None
    ) -> None:
        """
        Add a new frame to the replay from the current game state.
        If it's a keyframe interval, also store the visual frame.
        """
        if not self.recording:
            return

        # Extract relevant data from game state
        frame_count = getattr(game_state, "frame_count", 0)
        tracked_balls = getattr(game_state, "tracked_balls", []).copy()
        score = getattr(game_state, "score", 0)
        game_timer = getattr(game_state, "game_timer", None)

        # Create list for any events that happened this frame
        events = []

        # Determine if this is a keyframe
        is_keyframe = frame_count % KEYFRAME_INTERVAL == 0
        keyframe_image = None

        if is_keyframe and current_frame is not None:
            # Save keyframe image to temporary directory
            try:
                # Ensure temp directory exists
                if not os.path.exists(REPLAY_TEMP_FRAMES_DIR):
                    os.makedirs(REPLAY_TEMP_FRAMES_DIR, exist_ok=True)

                keyframe_path = os.path.join(
                    REPLAY_TEMP_FRAMES_DIR, f"{self.replay_id}_{frame_count}.jpg"
                )

                # Create a thumbnail version
                if (
                    current_frame.size == 0
                    or current_frame.shape[0] == 0
                    or current_frame.shape[1] == 0
                ):
                    logger.error(
                        f"Invalid frame shape for keyframe: {current_frame.shape if hasattr(current_frame, 'shape') else 'unknown'}"
                    )
                else:
                    # Make a deep copy to avoid modifying the original
                    thumbnail = current_frame.copy()

                    # Resize to a manageable size (1/4 of original)
                    try:
                        thumbnail = cv2.resize(
                            thumbnail, (self.width // 4, self.height // 4)
                        )

                        # Write to file
                        result = cv2.imwrite(keyframe_path, thumbnail)
                        if result:
                            # Keep track of keyframe timestamps
                            current_time = time.time()
                            self.keyframe_timestamps.append(current_time)
                            if frame_count % 300 == 0:  # Log every ~10 seconds at 30fps
                                logger.info(f"Saved keyframe at {keyframe_path}")
                            else:
                                logger.debug(f"Saved keyframe at {keyframe_path}")
                        else:
                            logger.error(
                                f"Failed to write keyframe to file: {keyframe_path}"
                            )
                    except Exception as e:
                        logger.error(f"Error resizing or saving keyframe: {e}")
            except Exception as e:
                logger.error(f"Failed to save keyframe: {e}")

        # Create and store the frame
        replay_frame = ReplayFrame(
            timestamp=time.time(),
            frame_count=frame_count,
            balls=tracked_balls,
            score=score,
            game_timer=game_timer,
            events=events,
            keyframe_image=keyframe_image,
        )

        self.frames.append(replay_frame)

        # Log frame capture occasionally
        if frame_count % 300 == 0:  # Log every ~10 seconds at 30fps
            logger.info(
                f"Added frame #{len(self.frames)} to replay (game frame #{frame_count})"
            )

        # Limit frames if needed for performance (unlikely to be needed)
        if len(self.frames) > 100000:  # ~55 minutes at 30fps
            # Remove oldest frames but keep keyframes
            self.frames = self.frames[-50000:]
            logger.warning("Replay exceeds 100,000 frames, truncating to last 50,000")

    def add_score_event(self, zone_id: int, points: int, ball_type: str) -> None:
        """
        Record a scoring event. Also adds it to the most recent frame's events.
        """
        if not self.recording:
            return

        event = {
            "type": "score",
            "timestamp": time.time(),
            "zone_id": zone_id,
            "points": points,
            "ball_type": ball_type,
        }

        self.score_events.append(event)

        # Also add to the most recent frame's events if available
        if self.frames:
            self.frames[-1].events.append(event)

        # Automatically create a highlight around this score event
        self._add_score_highlight(event["timestamp"], f"+{points} in zone {zone_id}")

    def _add_score_highlight(self, timestamp: float, description: str) -> None:
        """
        Create a highlight segment around a scoring event.
        """
        start_time = max(0, timestamp - DEFAULT_HIGHLIGHT_SECONDS_BEFORE)
        end_time = timestamp + DEFAULT_HIGHLIGHT_SECONDS_AFTER

        self.highlight_segments.append((start_time, end_time, description))

    def stop_recording(self, final_score: int) -> Optional[str]:
        """
        Stop recording and prepare the replay for saving.

        Args:
            final_score: The final score to record

        Returns:
            The replay ID if successfully prepared, None otherwise
        """
        if not self.recording:
            return None

        self.recording = False
        self.final_score = final_score

        # Calculate total duration
        if self.frames:
            self.duration = self.frames[-1].timestamp - self.frames[0].timestamp

        logger.info(
            f"Stopped recording replay {self.replay_id}. Final score: {final_score}, Duration: {self.duration:.1f}s"
        )

        # Save the replay to file
        try:
            self.save_to_file(REPLAY_DIR)
            return self.replay_id
        except Exception as e:
            logger.error(f"Failed to save replay: {e}")
            return None

    def save_to_file(self, base_path: Optional[str] = None) -> str:
        """
        Save the replay data to a file.

        Returns:
            Path to the saved replay file
        """
        base_path = base_path or REPLAY_DIR
        os.makedirs(base_path, exist_ok=True)

        # Prepare replay metadata
        metadata = {
            "replay_id": self.replay_id,
            "player_name": self.player_name,
            "game_mode": self.game_mode,
            "creation_time": self.creation_time,
            "creation_time_iso": datetime.fromtimestamp(self.creation_time).isoformat(),
            "width": self.width,
            "height": self.height,
            "final_score": self.final_score,
            "duration": self.duration,
            "title": self.title,
            "description": self.description,
            "scoring_zones": self.scoring_zones,
            "highlight_segments": self.highlight_segments,
            "score_events": self.score_events,
            "keyframe_timestamps": self.keyframe_timestamps,
        }

        # Create directory for this replay
        replay_dir = os.path.join(base_path, self.replay_id)
        if os.path.exists(replay_dir):
            # If directory already exists, remove it to avoid mixing old and new data
            try:
                shutil.rmtree(replay_dir)
                logger.info(f"Removed existing replay directory: {replay_dir}")
            except Exception as e:
                logger.error(f"Error removing existing replay directory: {e}")

        # Create fresh directory
        os.makedirs(replay_dir, exist_ok=True)
        logger.info(f"Created replay directory: {replay_dir}")

        # Save metadata to JSON file
        metadata_path = os.path.join(replay_dir, "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.debug(f"Saved metadata to {metadata_path}")

        # Save frames data (without images)
        frames_data = [frame.to_dict() for frame in self.frames]
        frames_path = os.path.join(replay_dir, "frames.json")
        with open(frames_path, "w") as f:
            json.dump(frames_data, f, indent=2)
        logger.debug(f"Saved {len(frames_data)} frames to {frames_path}")

        # Create keyframes directory
        keyframes_dir = os.path.join(replay_dir, "keyframes")
        os.makedirs(keyframes_dir, exist_ok=True)
        logger.debug(f"Created keyframes directory: {keyframes_dir}")

        # Count of keyframes moved
        keyframes_moved = 0

        # Move keyframe images from temp directory to replay directory
        temp_keyframe_pattern = os.path.join(
            REPLAY_TEMP_FRAMES_DIR, f"{self.replay_id}_*.jpg"
        )
        import glob

        temp_keyframe_files = glob.glob(temp_keyframe_pattern)

        logger.info(f"Found {len(temp_keyframe_files)} temporary keyframes to move")

        for temp_keyframe_path in temp_keyframe_files:
            # Extract frame number from filename
            frame_number = (
                os.path.basename(temp_keyframe_path).split("_")[1].split(".")[0]
            )
            dest_path = os.path.join(keyframes_dir, f"{frame_number}.jpg")

            try:
                # Ensure source file exists and is readable
                if os.path.exists(temp_keyframe_path) and os.access(
                    temp_keyframe_path, os.R_OK
                ):
                    shutil.copy2(temp_keyframe_path, dest_path)
                    keyframes_moved += 1
                    logger.debug(
                        f"Copied keyframe: {temp_keyframe_path} -> {dest_path}"
                    )
                else:
                    logger.warning(f"Keyframe not accessible: {temp_keyframe_path}")
            except Exception as e:
                logger.error(f"Failed to copy keyframe: {e}")

        # Log keyframe status
        logger.info(f"Copied {keyframes_moved} keyframes to {keyframes_dir}")

        # Clean up temp keyframes after successful copy
        for temp_keyframe_path in temp_keyframe_files:
            if os.path.exists(temp_keyframe_path):
                try:
                    os.remove(temp_keyframe_path)
                    logger.debug(f"Removed temp keyframe: {temp_keyframe_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp keyframe: {e}")

        # Create a thumbnail from the first keyframe, if available
        if len(temp_keyframe_files) > 0:
            sorted_keyframes = sorted(
                temp_keyframe_files,
                key=lambda x: int(os.path.basename(x).split("_")[1].split(".")[0]),
            )
            if sorted_keyframes:
                first_keyframe = sorted_keyframes[0]
                try:
                    thumbnail_path = os.path.join(replay_dir, "thumbnail.jpg")
                    if os.path.exists(first_keyframe) and os.access(
                        first_keyframe, os.R_OK
                    ):
                        shutil.copy2(first_keyframe, thumbnail_path)
                        logger.info(f"Created thumbnail for replay {self.replay_id}")
                    else:
                        logger.warning(
                            f"First keyframe not accessible: {first_keyframe}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to create thumbnail for replay {self.replay_id}: {e}"
                    )
        else:
            logger.warning(
                f"No keyframes available to create thumbnail for replay {self.replay_id}"
            )

        # Create a single-file replay package
        replay_file = os.path.join(base_path, f"{self.replay_id}{REPLAY_FILE_EXT}")
        try:
            # Remove existing zip if it exists
            if os.path.exists(replay_file):
                try:
                    os.remove(replay_file)
                except:
                    pass

            # Create fresh archive
            logger.info(f"Creating archive from {replay_dir}")
            archive_base = replay_file.replace(REPLAY_FILE_EXT, "")
            shutil.make_archive(archive_base, "zip", replay_dir)
            if os.path.exists(archive_base + ".zip"):
                os.rename(archive_base + ".zip", replay_file)
                logger.info(f"Renamed {archive_base}.zip to {replay_file}")
            else:
                logger.error(f"Archive file not found: {archive_base}.zip")
        except Exception as e:
            logger.error(f"Failed to create replay package: {e}")

        logger.info(f"Saved replay to {replay_file}")
        return replay_file

    @classmethod
    def load_from_file(cls, replay_path: str) -> Optional["Replay"]:
        """
        Load a replay from a file.

        Args:
            replay_path: Path to the replay file

        Returns:
            A Replay object if successful, None otherwise
        """
        # Check if it's a full path or just an ID
        if not replay_path.endswith(REPLAY_FILE_EXT):
            replay_path = os.path.join(REPLAY_DIR, f"{replay_path}{REPLAY_FILE_EXT}")

        if not os.path.exists(replay_path):
            logger.error(f"Replay file not found: {replay_path}")
            return None

        # Extract the replay ID from the filename
        replay_id = os.path.basename(replay_path).replace(REPLAY_FILE_EXT, "")

        # Create extraction directory
        extract_dir = os.path.join(REPLAY_DIR, replay_id)
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir, exist_ok=True)

        # Extract the replay package
        try:
            # Rename to zip for extraction
            temp_zip = replay_path.replace(REPLAY_FILE_EXT, ".temp.zip")
            shutil.copy(replay_path, temp_zip)
            shutil.unpack_archive(temp_zip, extract_dir, "zip")
            os.remove(temp_zip)
        except Exception as e:
            logger.error(f"Failed to extract replay package: {e}")
            return None

        # Load metadata
        metadata_path = os.path.join(extract_dir, "metadata.json")
        if not os.path.exists(metadata_path):
            logger.error(f"Metadata file not found in replay package: {metadata_path}")
            return None

        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # Create replay object
            replay = cls(
                replay_id=metadata.get("replay_id", replay_id),
                player_name=metadata.get("player_name", "Unknown"),
                game_mode=metadata.get("game_mode", "classic"),
                scoring_zones=metadata.get("scoring_zones", []),
            )

            # Load metadata fields
            replay.creation_time = metadata.get("creation_time", time.time())
            replay.width = metadata.get("width", 1920)
            replay.height = metadata.get("height", 1080)
            replay.final_score = metadata.get("final_score", 0)
            replay.duration = metadata.get("duration", 0.0)
            replay.title = metadata.get("title", f"Replay {replay_id}")
            replay.description = metadata.get("description", "")
            replay.highlight_segments = metadata.get("highlight_segments", [])
            replay.score_events = metadata.get("score_events", [])
            replay.keyframe_timestamps = metadata.get("keyframe_timestamps", [])

            # Load frames data
            frames_path = os.path.join(extract_dir, "frames.json")
            if not os.path.exists(frames_path):
                logger.error(f"Frames data not found in replay package: {frames_path}")
                return None

            with open(frames_path, "r") as f:
                frames_data = json.load(f)

            replay.frames = [
                ReplayFrame.from_dict(frame_data) for frame_data in frames_data
            ]

            logger.info(
                f"Loaded replay {replay_id} with {len(replay.frames)} frames, duration: {replay.duration:.1f}s"
            )
            return replay

        except Exception as e:
            logger.error(f"Failed to load replay: {e}")
            return None

    def get_keyframe_image(self, frame_count: int) -> Optional[np.ndarray]:
        """
        Get a keyframe image for the given frame count.

        Args:
            frame_count: The frame count to get the image for

        Returns:
            The keyframe image if available, None otherwise
        """
        if frame_count % KEYFRAME_INTERVAL != 0:
            frame_count = (frame_count // KEYFRAME_INTERVAL) * KEYFRAME_INTERVAL

        keyframe_path = os.path.join(
            REPLAY_DIR, self.replay_id, "keyframes", f"{frame_count}.jpg"
        )
        if os.path.exists(keyframe_path):
            try:
                return cv2.imread(keyframe_path)
            except Exception as e:
                logger.error(f"Failed to load keyframe image: {e}")

        return None

    def generate_video(
        self, output_path: Optional[str] = None, format: str = "MP4"
    ) -> Optional[str]:
        """
        Generate a video file from the replay.

        Args:
            output_path: Path where the video should be saved. If None, a default path is used.
            format: Format to export the video in ("MP4" or "GIF").

        Returns:
            Path to the generated video file if successful, None otherwise
        """
        if not self.frames:
            logger.error("Cannot generate video from empty replay")
            return None

        # Determine file extension based on format
        file_extension = ".mp4" if format == "MP4" else ".gif"

        if output_path is None:
            os.makedirs(os.path.join(REPLAY_DIR, "videos"), exist_ok=True)
            output_path = os.path.join(
                REPLAY_DIR, "videos", f"{self.replay_id}{file_extension}"
            )

        # Check if we have keyframes to create the video
        keyframes_dir = os.path.join(REPLAY_DIR, self.replay_id, "keyframes")

        if not os.path.exists(keyframes_dir):
            logger.error(f"Keyframes directory not found: {keyframes_dir}")
            # Try to extract first if directory doesn't exist
            try:
                logger.info(f"Attempting to extract replay package to access keyframes")
                replay_path = os.path.join(
                    REPLAY_DIR, f"{self.replay_id}{REPLAY_FILE_EXT}"
                )
                extract_dir = os.path.join(REPLAY_DIR, self.replay_id)

                if os.path.exists(replay_path):
                    # Create extraction directory
                    if not os.path.exists(extract_dir):
                        os.makedirs(extract_dir, exist_ok=True)

                    # Copy to temp zip and extract
                    temp_zip = replay_path.replace(REPLAY_FILE_EXT, ".temp.zip")
                    shutil.copy(replay_path, temp_zip)

                    try:
                        shutil.unpack_archive(temp_zip, extract_dir, "zip")
                        # Clean up
                        if os.path.exists(temp_zip):
                            os.remove(temp_zip)

                        # Check again for keyframes directory
                        if not os.path.exists(keyframes_dir):
                            logger.error(
                                f"Keyframes directory still not found after extraction: {keyframes_dir}"
                            )
                            return None

                        logger.info(
                            f"Successfully extracted replay to access keyframes"
                        )
                    except Exception as e:
                        logger.error(f"Failed to extract replay package: {e}")
                        return None
                else:
                    logger.error(f"Replay file not found: {replay_path}")
                    return None
            except Exception as e:
                logger.error(f"Error attempting to extract replay package: {e}")
                return None

        try:
            # Get list of keyframe files
            keyframe_files = [
                f for f in os.listdir(keyframes_dir) if f.endswith(".jpg")
            ]

            if not keyframe_files:
                logger.error("No keyframe files found in directory: " + keyframes_dir)
                return None

            # Sort keyframes by frame number
            keyframe_files.sort(key=lambda f: int(f.split(".")[0]))
            logger.info(f"Found {len(keyframe_files)} keyframes for video generation")

            # Load the first keyframe to get dimensions
            first_frame_path = os.path.join(keyframes_dir, keyframe_files[0])
            first_frame = cv2.imread(first_frame_path)

            if first_frame is None:
                logger.error(f"Failed to load first keyframe: {first_frame_path}")
                return None

            height, width = first_frame.shape[:2]
            logger.info(f"Video dimensions: {width}x{height}")

            # For GIF format, we'll collect frames and use imageio for conversion
            if format == "GIF":
                try:
                    # Import imageio with error handling
                    try:
                        import imageio
                    except ImportError:
                        logger.error(
                            "Failed to import imageio module. Make sure it's installed (pip install imageio)"
                        )
                        return None

                    # Create a clear status message
                    logger.info(f"Creating GIF from {len(keyframe_files)} keyframes")

                    # Collect frames for GIF
                    gif_frames = []
                    for keyframe_file in keyframe_files:
                        # Extract frame number for finding matching data
                        frame_count = int(keyframe_file.split(".")[0])
                        img_path = os.path.join(keyframes_dir, keyframe_file)

                        # Load image
                        img = cv2.imread(img_path)
                        if img is None:
                            logger.warning(f"Failed to read keyframe image: {img_path}")
                            continue

                        # Find the nearest frame in our data
                        nearest_frame = None
                        for frame in self.frames:
                            if frame.frame_count == frame_count:
                                nearest_frame = frame
                                break

                        if nearest_frame:
                            # Add score overlay
                            score_text = f"Score: {nearest_frame.score}"
                            cv2.putText(
                                img,
                                score_text,
                                (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (255, 255, 255),
                                1,
                            )

                            # Add game mode
                            mode_text = f"Mode: {self.game_mode.capitalize()}"
                            cv2.putText(
                                img,
                                mode_text,
                                (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (255, 255, 255),
                                1,
                            )

                            # Add player name
                            player_text = f"Player: {self.player_name}"
                            cv2.putText(
                                img,
                                player_text,
                                (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (255, 255, 255),
                                1,
                            )

                            # Add timer if present
                            if nearest_frame.game_timer is not None:
                                timer_text = f"Time: {nearest_frame.game_timer:.1f}s"
                                cv2.putText(
                                    img,
                                    timer_text,
                                    (10, 90),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    (255, 255, 255),
                                    1,
                                )

                        # Convert BGR to RGB for GIF
                        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        gif_frames.append(img_rgb)

                    # Check if we have frames to create the GIF
                    if not gif_frames:
                        logger.error("No frames could be loaded for GIF creation")
                        return None

                    # First, make sure the output directory exists
                    os.makedirs(
                        os.path.dirname(os.path.abspath(output_path)), exist_ok=True
                    )

                    # Save as GIF using imageio
                    fps = ReplayConstants.REPLAY_VIDEO_FPS

                    # Use a simpler FPS for GIFs to avoid size issues
                    gif_fps = min(fps, 10)  # Limit to 10 FPS for GIFs

                    # Ensure any existing file is removed to avoid permission issues
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except Exception as e:
                            logger.warning(
                                f"Could not remove existing output file: {e}"
                            )

                    # Save the GIF with error handling
                    try:
                        imageio.mimsave(output_path, gif_frames, fps=gif_fps)
                    except Exception as e:
                        logger.error(f"Failed to save GIF with imageio: {e}")
                        return None

                    # Verify the file was created successfully
                    if not os.path.exists(output_path):
                        logger.error(f"GIF file not created at {output_path}")
                        return None

                    # Log success
                    logger.info(
                        f"Generated GIF with {len(gif_frames)} frames at {output_path}"
                    )
                    return output_path

                except Exception as e:
                    logger.error(f"Error generating GIF: {str(e)}")
                    import traceback

                    logger.error(traceback.format_exc())
                    return None
            else:
                # Create MP4 video writer
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                fps = ReplayConstants.REPLAY_VIDEO_FPS
                video_writer = cv2.VideoWriter(
                    output_path, fourcc, fps, (width, height)
                )

                if not video_writer.isOpened():
                    logger.error(f"Failed to create video writer for {output_path}")
                    return None

                # Add text with score and game information
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                font_color = (255, 255, 255)  # White
                font_thickness = 1

                # Write frames to video
                frames_written = 0
                for keyframe_file in keyframe_files:
                    # Extract frame number for finding matching data
                    frame_count = int(keyframe_file.split(".")[0])
                    img_path = os.path.join(keyframes_dir, keyframe_file)

                    # Load image
                    img = cv2.imread(img_path)
                    if img is None:
                        logger.warning(f"Failed to read keyframe image: {img_path}")
                        continue

                    # Find the nearest frame in our data
                    nearest_frame = None
                    for frame in self.frames:
                        if frame.frame_count == frame_count:
                            nearest_frame = frame
                            break

                    if nearest_frame:
                        # Add score overlay
                        score_text = f"Score: {nearest_frame.score}"
                        cv2.putText(
                            img,
                            score_text,
                            (10, 30),
                            font,
                            font_scale,
                            font_color,
                            font_thickness,
                        )

                        # Add game mode
                        mode_text = f"Mode: {self.game_mode.capitalize()}"
                        cv2.putText(
                            img,
                            mode_text,
                            (10, 50),
                            font,
                            font_scale,
                            font_color,
                            font_thickness,
                        )

                        # Add player name
                        player_text = f"Player: {self.player_name}"
                        cv2.putText(
                            img,
                            player_text,
                            (10, 70),
                            font,
                            font_scale,
                            font_color,
                            font_thickness,
                        )

                        # Add timer if present
                        if nearest_frame.game_timer is not None:
                            timer_text = f"Time: {nearest_frame.game_timer:.1f}s"
                            cv2.putText(
                                img,
                                timer_text,
                                (10, 90),
                                font,
                                font_scale,
                                font_color,
                                font_thickness,
                            )

                    # Write the frame
                    video_writer.write(img)
                    frames_written += 1

                # Release the video writer
                video_writer.release()
                logger.info(
                    f"Generated video with {frames_written} frames at {output_path}"
                )
                return output_path

        except Exception as e:
            logger.error(f"Failed to generate video: {e}")
            return None

    def extract_highlight_video(
        self,
        highlight_index: int,
        output_path: Optional[str] = None,
        format: str = "MP4",
    ) -> Optional[str]:
        """
        Extract a highlight segment as a video.

        Args:
            highlight_index: Index of the highlight segment to extract
            output_path: Path where the video should be saved. If None, a default path is used.
            format: Format to export the video in ("MP4" or "GIF").

        Returns:
            Path to the generated video file if successful, None otherwise
        """
        if not self.highlight_segments or highlight_index >= len(
            self.highlight_segments
        ):
            logger.error(f"Invalid highlight index: {highlight_index}")
            return None

        start_time, end_time, description = self.highlight_segments[highlight_index]

        if output_path is None:
            os.makedirs(os.path.join(REPLAY_DIR, "highlights"), exist_ok=True)
            safe_desc = "".join([c if c.isalnum() else "_" for c in description])[:20]
            output_path = os.path.join(
                REPLAY_DIR,
                "highlights",
                f"{self.replay_id}_highlight_{highlight_index}_{safe_desc}.mp4",
            )

        # Find frames within the highlight time range
        start_frame_idx = None
        end_frame_idx = None

        for i, frame in enumerate(self.frames):
            if start_frame_idx is None and frame.timestamp >= start_time:
                start_frame_idx = i
            if frame.timestamp <= end_time:
                end_frame_idx = i
            else:
                break

        if start_frame_idx is None or end_frame_idx is None:
            logger.error("Could not find frames for highlight segment")
            return None

        # Find keyframes within or close to the segment
        keyframes_dir = os.path.join(REPLAY_DIR, self.replay_id, "keyframes")
        if not os.path.exists(keyframes_dir):
            logger.error(f"Keyframes directory not found: {keyframes_dir}")
            return None

        try:
            # Collect frame data for the segment
            segment_frames = self.frames[start_frame_idx : end_frame_idx + 1]

            # Find available keyframes in this segment
            keyframe_counts = [
                frame.frame_count
                for frame in segment_frames
                if frame.frame_count % KEYFRAME_INTERVAL == 0
            ]

            if not keyframe_counts:
                logger.error("No keyframes found in highlight segment")
                return None

            # Load the first keyframe to get dimensions
            first_frame_path = os.path.join(keyframes_dir, f"{keyframe_counts[0]}.jpg")
            if not os.path.exists(first_frame_path):
                logger.error(f"Keyframe not found: {first_frame_path}")
                return None

            first_frame = cv2.imread(first_frame_path)
            height, width = first_frame.shape[:2]

            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            fps = 15  # Higher FPS for highlights
            video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            # Font settings for overlays
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            font_color = (255, 255, 255)  # White
            font_thickness = 2

            # Add highlight title frame
            title_frame = np.zeros((height, width, 3), dtype=np.uint8)
            title_text = description

            # Calculate text size to center it
            text_size = cv2.getTextSize(
                title_text, font, font_scale * 1.5, font_thickness
            )[0]
            text_x = (width - text_size[0]) // 2
            text_y = (height + text_size[1]) // 2

            # Add text to title frame
            cv2.putText(
                title_frame,
                title_text,
                (text_x, text_y),
                font,
                font_scale * 1.5,
                (255, 255, 255),
                font_thickness,
            )

            # Add player and score info
            player_text = f"Player: {self.player_name}"
            score_text = f"Score: {segment_frames[-1].score}"

            cv2.putText(
                title_frame,
                player_text,
                (text_x, text_y + 40),
                font,
                font_scale,
                (200, 200, 200),
                font_thickness - 1,
            )

            cv2.putText(
                title_frame,
                score_text,
                (text_x, text_y + 80),
                font,
                font_scale,
                (200, 200, 200),
                font_thickness - 1,
            )

            # Write title frame multiple times (3 seconds)
            for _ in range(int(fps * 2)):
                video_writer.write(title_frame)

            # Write keyframes
            for frame_count in keyframe_counts:
                keyframe_path = os.path.join(keyframes_dir, f"{frame_count}.jpg")
                if os.path.exists(keyframe_path):
                    img = cv2.imread(keyframe_path)

                    # Find corresponding frame data
                    for frame in segment_frames:
                        if frame.frame_count == frame_count:
                            # Add score overlay
                            cv2.putText(
                                img,
                                f"Score: {frame.score}",
                                (10, 30),
                                font,
                                font_scale,
                                font_color,
                                font_thickness,
                            )
                            break

                    video_writer.write(img)

            # Add ending frame
            end_frame = np.zeros((height, width, 3), dtype=np.uint8)
            end_text = "Highlight End"

            # Calculate text size to center it
            text_size = cv2.getTextSize(
                end_text, font, font_scale * 1.2, font_thickness
            )[0]
            text_x = (width - text_size[0]) // 2
            text_y = (height + text_size[1]) // 2

            # Add text to end frame
            cv2.putText(
                end_frame,
                end_text,
                (text_x, text_y),
                font,
                font_scale * 1.2,
                (200, 200, 200),
                font_thickness - 1,
            )

            # Write end frame (1 second)
            for _ in range(int(fps * 1)):
                video_writer.write(end_frame)

            video_writer.release()
            logger.info(f"Generated highlight video at {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to extract highlight: {e}")
            return None


class ReplayManager:
    """
    Manages recordings, storage, and playback of game replays.
    """

    def __init__(self):
        self.current_replay: Optional[Replay] = None
        self.replays: Dict[str, Dict[str, Any]] = {}  # Dictionary of replay metadata
        self.replays_path = REPLAY_DIR

        # Create replay directory if it doesn't exist
        os.makedirs(self.replays_path, exist_ok=True)
        os.makedirs(REPLAY_TEMP_FRAMES_DIR, exist_ok=True)

        # Load existing replays
        self._load_replays()

    def _load_replays(self) -> None:
        """
        Load metadata for all available replays.
        """
        # Look for replay files in the replays directory
        replay_files = [
            f
            for f in os.listdir(self.replays_path)
            if f.endswith(REPLAY_FILE_EXT)
            and os.path.isfile(os.path.join(self.replays_path, f))
        ]

        for replay_file in replay_files:
            replay_id = replay_file.replace(REPLAY_FILE_EXT, "")
            replay_path = os.path.join(self.replays_path, replay_file)

            # Try to extract just the metadata without loading all frames
            try:
                # Make a temporary copy with .zip extension for extraction
                temp_zip = replay_path.replace(REPLAY_FILE_EXT, ".temp.zip")
                shutil.copy(replay_path, temp_zip)

                # Extract just the metadata file
                temp_dir = os.path.join(self.replays_path, "temp_extract")
                os.makedirs(temp_dir, exist_ok=True)

                with open(temp_zip, "rb") as f:
                    # Check if it's a valid zip file by reading the first few bytes
                    if f.read(4) != b"PK\x03\x04":
                        logger.warning(
                            f"File is not a valid zip archive: {replay_file}"
                        )
                        continue

                # Extract metadata.json
                try:
                    shutil.unpack_archive(temp_zip, temp_dir, "zip")
                    metadata_path = os.path.join(temp_dir, "metadata.json")

                    if os.path.exists(metadata_path):
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)

                        # Check for thumbnail
                        thumbnail_path = os.path.join(temp_dir, "thumbnail.jpg")
                        has_thumbnail = os.path.exists(thumbnail_path)

                        self.replays[replay_id] = {
                            "id": replay_id,
                            "title": metadata.get("title", f"Replay {replay_id}"),
                            "player_name": metadata.get("player_name", "Unknown"),
                            "game_mode": metadata.get("game_mode", "classic"),
                            "creation_time": metadata.get("creation_time", 0),
                            "duration": metadata.get("duration", 0.0),
                            "final_score": metadata.get("final_score", 0),
                            "file_path": replay_path,
                            "highlight_count": len(
                                metadata.get("highlight_segments", [])
                            ),
                            "has_thumbnail": has_thumbnail,
                        }
                except Exception as e:
                    logger.error(f"Failed to extract metadata from replay: {e}")

                # Clean up
                try:
                    os.remove(temp_zip)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass

            except Exception as e:
                logger.error(f"Error loading replay metadata for {replay_file}: {e}")

        logger.info(f"Loaded metadata for {len(self.replays)} replays")

    def start_recording(self, game_state: Any) -> None:
        """
        Start recording a new replay.
        """
        # Debug logging to verify the method is being called
        logger.info("start_recording method called in ReplayManager")

        try:
            if self.current_replay and self.current_replay.recording:
                logger.warning(
                    "Already recording a replay, stopping current recording first"
                )
                self.stop_recording(game_state.score)

            # Get necessary data from game state
            player_name = (
                game_state.get_current_player().name
                if hasattr(game_state, "get_current_player")
                else "Player"
            )
            game_mode = getattr(game_state, "game_mode", "classic")
            scoring_zones = getattr(game_state, "scoring_zones", []).copy()
            resolution = getattr(
                game_state, "get_current_resolution_dimensions", lambda: (1920, 1080)
            )()

            # Create new replay
            self.current_replay = Replay(
                player_name=player_name,
                game_mode=game_mode,
                scoring_zones=scoring_zones,
            )

            # Start recording
            self.current_replay.start_recording(resolution)

            # Add the first frame
            current_frame = getattr(game_state, "current_frame", None)
            self.current_replay.add_frame(game_state, current_frame)

            # Set a flag in game_state to indicate we're recording
            setattr(game_state, "replay_recording", True)

            logger.info(
                f"Started recording replay {self.current_replay.replay_id} at {resolution[0]}x{resolution[1]}"
            )
            logger.info(
                f"Started recording replay {self.current_replay.replay_id} for player {player_name} in {game_mode} mode"
            )
        except Exception as e:
            logger.error(f"Exception in start_recording: {e}")
            logger.exception("Full traceback for start_recording error:")
            # Don't set the replay_recording flag if there was an error
            setattr(game_state, "replay_recording", False)

    def update_recording(self, game_state: Any) -> None:
        """
        Update the current replay with a new frame.
        """
        # Check if recording is active
        if not self.current_replay or not self.current_replay.recording:
            # If recording flag is set in game_state but not active in replay manager,
            # clear the flag for consistency
            if getattr(game_state, "replay_recording", False):
                setattr(game_state, "replay_recording", False)
                logger.warning("Inconsistent recording state detected and fixed")
            return

        # Check the game_state recording flag
        if not getattr(game_state, "replay_recording", False):
            setattr(game_state, "replay_recording", True)
            logger.debug("Fixed missing replay_recording flag in game_state")

        # Log the frame count periodically to track recording progress
        if game_state.frame_count % 30 == 0:  # Log every 30 frames
            current_frames = (
                len(self.current_replay.frames) if self.current_replay else 0
            )
            logger.info(f"Replay recording update - frames so far: {current_frames}")

        # Get the current frame from game_state
        # The current_frame is set in _render_frame function in game_loop.py
        # If it's not available yet, we'll skip this frame or use a backup approach
        current_frame = getattr(game_state, "current_frame", None)

        # If current_frame is not available yet, try to capture one directly
        if current_frame is None and hasattr(game_state, "cap") and game_state.cap:
            try:
                ret, direct_frame = game_state.cap.read()
                if ret and direct_frame is not None:
                    # Resize to match resolution if needed
                    target_width, target_height = getattr(
                        game_state,
                        "get_current_resolution_dimensions",
                        lambda: (1920, 1080),
                    )()
                    if (
                        direct_frame.shape[1] != target_width
                        or direct_frame.shape[0] != target_height
                    ):
                        current_frame = cv2.resize(
                            direct_frame, (target_width, target_height)
                        )
                    else:
                        current_frame = direct_frame
                    logger.debug("Captured frame directly for replay recording")
            except Exception as e:
                logger.error(f"Error capturing direct frame for replay: {e}")

        # Add the frame to the replay
        self.current_replay.add_frame(game_state, current_frame)

    def record_score(self, zone_id: int, points: int, ball_type: str) -> None:
        """
        Record a scoring event in the current replay.
        """
        if not self.current_replay or not self.current_replay.recording:
            return

        self.current_replay.add_score_event(zone_id, points, ball_type)

    def stop_recording(self, final_score: int, game_state: Any = None) -> Optional[str]:
        """
        Stop recording and save the replay.

        Args:
            final_score: The final score to record
            game_state: Optional game state to update the recording flag

        Returns:
            The replay ID if successful, None otherwise
        """
        if not self.current_replay or not self.current_replay.recording:
            logger.warning("No active replay to stop recording")
            return None

        # Clear recording flag in game_state if provided
        if game_state is not None:
            setattr(game_state, "replay_recording", False)

        # Stop recording in the Replay object
        replay_id = self.current_replay.stop_recording(final_score)

        if replay_id:
            # Get the replay path from the save operation
            file_path = os.path.join(REPLAY_DIR, f"{replay_id}{REPLAY_FILE_EXT}")

            # Add to replays dictionary
            self.replays[replay_id] = {
                "id": replay_id,
                "title": self.current_replay.title,
                "player_name": self.current_replay.player_name,
                "game_mode": self.current_replay.game_mode,
                "creation_time": self.current_replay.creation_time,
                "duration": self.current_replay.duration,
                "final_score": final_score,
                "file_path": file_path,
                "highlight_count": len(self.current_replay.highlight_segments),
                "has_thumbnail": True,  # Assuming thumbnail was created in save_to_file
                "timestamp": datetime.now(),
            }

            # Limit number of replays stored in memory
            if len(self.replays) > MAX_REPLAY_HISTORY:
                # Sort by timestamp and remove oldest
                oldest_replay = sorted(
                    self.replays.items(), key=lambda x: x[1].get("creation_time", 0)
                )[0][0]
                del self.replays[oldest_replay]

            logger.info(f"Saved replay {replay_id} with score {final_score}")
            return replay_id

        return None

    def load_replay(self, replay_id: str) -> Optional[Replay]:
        """
        Load a replay from storage.

        Args:
            replay_id: ID of the replay to load

        Returns:
            The loaded Replay object if successful, None otherwise
        """
        if replay_id not in self.replays:
            logger.error(f"Replay {replay_id} not found in replay list")
            return None

        replay_path = self.replays[replay_id]["file_path"]

        # Check if the file exists
        if not os.path.exists(replay_path):
            logger.error(f"Replay file not found: {replay_path}")
            return None

        logger.info(f"Loading replay from {replay_path}")

        try:
            # Check if the directory already exists and clean it up
            extract_dir = os.path.join(REPLAY_DIR, replay_id)
            if os.path.exists(extract_dir):
                logger.info(f"Removing existing extraction directory: {extract_dir}")
                try:
                    shutil.rmtree(extract_dir)
                except Exception as e:
                    logger.error(
                        f"Error cleaning up existing extraction directory: {e}"
                    )
                    # Continue anyway

            # Create fresh extraction directory
            os.makedirs(extract_dir, exist_ok=True)

            # Copy to temp zip file for extraction
            temp_zip = replay_path.replace(REPLAY_FILE_EXT, ".temp.zip")
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            shutil.copy(replay_path, temp_zip)

            # Verify it's a valid zip file
            if not os.path.exists(temp_zip):
                logger.error(f"Failed to create temp zip file: {temp_zip}")
                return None

            # Extract the zip archive
            try:
                logger.info(f"Extracting replay package to {extract_dir}")
                shutil.unpack_archive(temp_zip, extract_dir, "zip")
                # Clean up temp zip
                os.remove(temp_zip)
            except Exception as e:
                logger.error(f"Failed to extract replay package: {e}")
                return None

            # Verify extraction succeeded
            metadata_path = os.path.join(extract_dir, "metadata.json")
            if not os.path.exists(metadata_path):
                logger.error(
                    f"Metadata file not found after extraction: {metadata_path}"
                )
                return None

            # Load metadata
            with open(metadata_path, "r") as f:
                try:
                    metadata = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse metadata JSON: {e}")
                    return None

            # Create replay object
            replay = Replay(
                replay_id=metadata.get("replay_id", replay_id),
                player_name=metadata.get("player_name", "Unknown"),
                game_mode=metadata.get("game_mode", "classic"),
                scoring_zones=metadata.get("scoring_zones", []),
            )

            # Load metadata fields
            replay.creation_time = metadata.get("creation_time", time.time())
            replay.width = metadata.get("width", 1920)
            replay.height = metadata.get("height", 1080)
            replay.final_score = metadata.get("final_score", 0)
            replay.duration = metadata.get("duration", 0.0)
            replay.title = metadata.get("title", f"Replay {replay_id}")
            replay.description = metadata.get("description", "")
            replay.highlight_segments = metadata.get("highlight_segments", [])
            replay.score_events = metadata.get("score_events", [])
            replay.keyframe_timestamps = metadata.get("keyframe_timestamps", [])

            # Load frames data
            frames_path = os.path.join(extract_dir, "frames.json")
            if not os.path.exists(frames_path):
                logger.error(f"Frames data not found after extraction: {frames_path}")
                return None

            with open(frames_path, "r") as f:
                try:
                    frames_data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse frames JSON: {e}")
                    return None

            # Convert frame data to ReplayFrame objects
            try:
                replay.frames = [
                    ReplayFrame.from_dict(frame_data) for frame_data in frames_data
                ]
            except Exception as e:
                logger.error(f"Error converting frame data to ReplayFrame objects: {e}")
                return None

            # Verify we have frames
            if not replay.frames:
                logger.warning(f"Loaded replay {replay_id} contains no frames")

            logger.info(
                f"Successfully loaded replay {replay_id} with {len(replay.frames)} frames, duration: {replay.duration:.1f}s"
            )
            return replay

        except Exception as e:
            logger.error(f"Failed to load replay {replay_id}: {e}")
            return None

    def delete_replay(self, replay_id: str) -> bool:
        """
        Delete a replay.

        Args:
            replay_id: ID of the replay to delete

        Returns:
            True if successful, False otherwise
        """
        if replay_id not in self.replays:
            logger.error(f"Replay {replay_id} not found")
            return False

        try:
            replay_path = self.replays[replay_id]["file_path"]

            # Delete the replay file
            if os.path.exists(replay_path):
                os.remove(replay_path)

            # Delete extracted directory if it exists
            replay_dir = os.path.join(self.replays_path, replay_id)
            if os.path.exists(replay_dir) and os.path.isdir(replay_dir):
                shutil.rmtree(replay_dir, ignore_errors=True)

            # Remove from replays list
            del self.replays[replay_id]

            logger.info(f"Deleted replay {replay_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete replay {replay_id}: {e}")
            return False

    def get_all_replays(self) -> List[Dict[str, Any]]:
        """
        Get metadata for all available replays, sorted by creation time (newest first).

        Returns:
            List of replay metadata dictionaries
        """
        return sorted(
            self.replays.values(),
            key=lambda replay: replay.get("creation_time", 0),
            reverse=True,
        )

    def get_replay_thumbnail(self, replay_id: str) -> Optional[np.ndarray]:
        """
        Get the thumbnail image for a replay.

        Args:
            replay_id: ID of the replay

        Returns:
            Thumbnail image as a numpy array if available, None otherwise
        """
        if replay_id not in self.replays or not self.replays[replay_id].get(
            "has_thumbnail", False
        ):
            return None

        # Check if the thumbnail exists in the extracted directory
        thumbnail_path = os.path.join(self.replays_path, replay_id, "thumbnail.jpg")

        # If not extracted yet, extract the replay
        if not os.path.exists(thumbnail_path):
            replay_path = self.replays[replay_id]["file_path"]
            extract_dir = os.path.join(self.replays_path, replay_id)

            try:
                if not os.path.exists(extract_dir):
                    os.makedirs(extract_dir, exist_ok=True)

                temp_zip = replay_path.replace(REPLAY_FILE_EXT, ".temp.zip")
                shutil.copy(replay_path, temp_zip)

                # Extract just the thumbnail
                with open(temp_zip, "rb") as f:
                    if f.read(4) != b"PK\x03\x04":
                        logger.warning(
                            f"File is not a valid zip archive: {replay_path}"
                        )
                        return None

                # Try to extract just the thumbnail file
                import zipfile

                with zipfile.ZipFile(temp_zip, "r") as zip_ref:
                    try:
                        zip_ref.extract("thumbnail.jpg", extract_dir)
                    except:
                        logger.warning(f"No thumbnail in replay {replay_id}")
                        return None

                os.remove(temp_zip)

            except Exception as e:
                logger.error(f"Failed to extract thumbnail: {e}")
                return None

        # Load the thumbnail
        if os.path.exists(thumbnail_path):
            try:
                return cv2.imread(thumbnail_path)
            except Exception as e:
                logger.error(f"Failed to load thumbnail: {e}")

        return None

    def generate_video(
        self, replay_id: str, output_path: Optional[str] = None, format: str = "MP4"
    ) -> Optional[str]:
        """
        Generate a video from a replay.

        Args:
            replay_id: ID of the replay
            output_path: Path where the video should be saved. If None, a default path is used.
            format: Format to export the video in ("MP4" or "GIF").

        Returns:
            Path to the generated video if successful, None otherwise
        """
        replay = self.load_replay(replay_id)
        if not replay:
            return None

        return replay.generate_video(output_path, format)

    def extract_highlight(
        self,
        replay_id: str,
        highlight_index: int,
        output_path: Optional[str] = None,
        format: str = "MP4",
    ) -> Optional[str]:
        """
        Extract a highlight segment from a replay as a video.

        Args:
            replay_id: ID of the replay
            highlight_index: Index of the highlight segment
            output_path: Path where the video should be saved. If None, a default path is used.
            format: Format to export the video in ("MP4" or "GIF").

        Returns:
            Path to the generated video if successful, None otherwise
        """
        replay = self.load_replay(replay_id)
        if not replay:
            return None

        # Determine file extension based on format
        file_extension = ".mp4" if format == "MP4" else ".gif"

        # If output_path is provided but doesn't have the correct extension, update it
        if output_path and not output_path.endswith(file_extension):
            output_path = output_path.rsplit(".", 1)[0] + file_extension

        return replay.extract_highlight_video(highlight_index, output_path)

    def share_replay(
        self, replay_id: str, share_method: str = "local", format: str = "MP4"
    ) -> Optional[str]:
        """
        Share a replay using the specified method.

        Args:
            replay_id: ID of the replay to share
            share_method: Method to use for sharing ("local", "video", "highlight")
            format: Format to export the video in ("MP4" or "GIF")

        Returns:
            A string with the result of the share operation (e.g., file path, URL)
        """
        if replay_id not in self.replays:
            logger.error(f"Replay {replay_id} not found")
            return None

        try:
            if share_method == "local":
                # Just return the local file path
                return self.replays[replay_id]["file_path"]

            elif share_method == "video":
                # Generate and return video
                return self.generate_video(replay_id, format=format)

            elif share_method.startswith("highlight_"):
                # Extract highlight index from share method
                try:
                    highlight_index = int(share_method.split("_")[1])
                    return self.extract_highlight(replay_id, highlight_index)
                except:
                    logger.error(
                        f"Invalid highlight index in share method: {share_method}"
                    )
                    return None

            else:
                logger.error(f"Unsupported share method: {share_method}")
                return None

        except Exception as e:
            logger.error(f"Failed to share replay {replay_id}: {e}")
            return None
