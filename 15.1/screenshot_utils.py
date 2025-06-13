import cv2
import os
import logging
import uuid
from datetime import datetime
import requests
from typing import Dict, Any, Optional, Tuple

# Set up logging
logger = logging.getLogger(__name__)


def ensure_supabase_bucket_exists(
    supabase_url: str, supabase_key: str, bucket_name: str
) -> bool:
    """
    Ensure that the specified bucket exists in Supabase Storage.
    Will check if bucket exists and return True if it does.
    If bucket doesn't exist, will attempt to create it but continue if creation fails.

    Args:
        supabase_url: URL of the Supabase instance.
        supabase_key: API key for Supabase authentication.
        bucket_name: Name of the bucket to check/create.

    Returns:
        bool: True if bucket exists or was created successfully, False otherwise.
    """
    try:
        # Prepare headers for Supabase request
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
        }
        
        # Debug log the request details (excluding the actual key)
        logger.debug(f"Checking bucket existence with URL: {supabase_url}/storage/v1/bucket")
        logger.debug(f"Using headers: {', '.join(headers.keys())}")

        # First check if bucket exists
        list_url = f"{supabase_url}/storage/v1/bucket"
        response = requests.get(
            list_url,
            headers=headers,
            timeout=10,
            verify=False,  # Consistent with existing code that disables verification
        )

        # Debug log the response
        logger.debug(f"List buckets response status: {response.status_code}")
        if response.status_code != 200:
            logger.debug(f"List buckets response body: {response.text}")

        if response.status_code == 200:
            buckets = response.json()
            logger.debug(f"Found {len(buckets)} buckets in storage")
            for bucket in buckets:
                logger.debug(f"Found bucket: {bucket.get('name')} (public: {bucket.get('public', 'unknown')})")
            
            if any(bucket["name"] == bucket_name for bucket in buckets):
                logger.info(
                    f"Bucket '{bucket_name}' already exists in Supabase Storage"
                )
                return True

        # Bucket doesn't exist, try to create it
        create_url = f"{supabase_url}/storage/v1/bucket"
        payload = {
            "name": bucket_name,
            "public": True,  # Makes bucket publicly accessible
        }

        logger.debug(f"Attempting to create bucket with payload: {payload}")
        response = requests.post(
            create_url,
            headers=headers,
            json=payload,
            timeout=10,
            verify=False,  # Consistent with existing code that disables verification
        )

        # Debug log the create response
        logger.debug(f"Create bucket response status: {response.status_code}")
        if response.status_code not in (200, 201):
            logger.debug(f"Create bucket response body: {response.text}")

        if response.status_code == 200 or response.status_code == 201:
            logger.info(
                f"Successfully created bucket '{bucket_name}' in Supabase Storage"
            )
            return True
        else:
            # If we can't create the bucket, check if it exists again (it might have been created by another process)
            logger.debug("Create failed, checking bucket existence again...")
            response = requests.get(
                list_url,
                headers=headers,
                timeout=10,
                verify=False,
            )
            
            # Debug log the second check response
            logger.debug(f"Second check response status: {response.status_code}")
            if response.status_code != 200:
                logger.debug(f"Second check response body: {response.text}")
            
            if response.status_code == 200:
                buckets = response.json()
                if any(bucket["name"] == bucket_name for bucket in buckets):
                    logger.info(
                        f"Bucket '{bucket_name}' exists in Supabase Storage (created by another process)"
                    )
                    return True
            
            logger.warning(
                f"Failed to create bucket '{bucket_name}': {response.status_code} - {response.text}. "
                "The bucket may need to be created manually in the Supabase dashboard."
            )
            return False

    except Exception as e:
        logger.error(f"Error ensuring bucket exists: {e}")
        return False


def ensure_directory_exists(directory_path: str) -> None:
    """Ensure the directory exists, create it if it doesn't."""
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
            logger.info(f"Created directory: {directory_path}")
        except Exception as e:
            logger.error(f"Failed to create directory {directory_path}: {e}")
            raise


def capture_playfield_screenshot(frame: Any) -> Any:
    """
    Captures a screenshot of the current playfield.
    Args:
        frame: The current frame from the game.
    Returns:
        A copy of the frame.
    """
    if frame is None:
        logger.error("Cannot capture screenshot: frame is None")
        return None

    try:
        # Make a deep copy of the frame to avoid modifying the original
        screenshot = frame.copy()
        return screenshot
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        return None


def save_screenshot_locally(
    screenshot: Any, player_name: str, score: int, game_mode: str
) -> Optional[str]:
    """
    Saves the screenshot to a local directory.
    Args:
        screenshot: The screenshot to save.
        player_name: Player's name.
        score: Player's score.
        game_mode: The game mode.
    Returns:
        The path to the saved screenshot or None if failed.
    """
    if screenshot is None:
        logger.error("Cannot save screenshot: screenshot is None")
        return None

    try:
        directory = "high_score_proof"
        ensure_directory_exists(directory)

        # Generate a unique filename with timestamp, player name, score
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_player_name = "".join(c if c.isalnum() else "_" for c in player_name)
        filename = f"{timestamp}_{safe_player_name}_{score}_{game_mode}.png"
        file_path = os.path.join(directory, filename)

        # Save the screenshot
        cv2.imwrite(file_path, screenshot)
        logger.info(f"Saved screenshot to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving screenshot: {e}")
        return None


def upload_screenshot_to_supabase(
    file_path: str,
    supabase_url: str,
    supabase_key: str,
    player_name: str,
    score: int,
    game_mode: str,
) -> Optional[str]:
    """
    Uploads the screenshot to Supabase Storage.
    Args:
        file_path: Path to the local screenshot file.
        supabase_url: URL of the Supabase instance.
        supabase_key: API key for Supabase authentication.
        player_name: Player's name.
        score: Player's score.
        game_mode: The game mode.
    Returns:
        The public URL of the uploaded screenshot or None if failed.
    """
    if not file_path or not os.path.exists(file_path):
        logger.error(f"Cannot upload screenshot: file {file_path} does not exist")
        return None

    try:
        # Generate a unique filename for storage
        filename = os.path.basename(file_path)
        storage_path = f"high-scores/{game_mode}/{filename}"

        # Prepare headers for Supabase request
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}

        # Set up the storage bucket name - adjust as needed
        bucket_name = "high-score-screenshots"

        # Use Supabase Storage REST API to upload the file
        url = f"{supabase_url}/storage/v1/object/{bucket_name}/{storage_path}"

        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "image/png")}
            response = requests.post(
                url,
                headers=headers,
                files=files,
                timeout=30,
                verify=False,  # Consistent with existing code that disables verification
            )

        if response.status_code == 200 or response.status_code == 201:
            # Get the public URL
            public_url = (
                f"{supabase_url}/storage/v1/object/public/{bucket_name}/{storage_path}"
            )
            logger.info(f"Successfully uploaded screenshot to Supabase: {public_url}")
            return public_url
        else:
            logger.error(
                f"Failed to upload screenshot to Supabase: {response.status_code} - {response.text}"
            )
            return None
    except Exception as e:
        logger.error(f"Error uploading screenshot to Supabase: {e}")
        return None


def capture_and_upload_game_screenshot(
    frame: Any,
    player_name: str,
    score: int,
    game_mode: str,
    supabase_url: str,
    supabase_key: str,
) -> Optional[str]:
    """
    Captures a screenshot of the game, saves it locally, and uploads to Supabase.
    Args:
        frame: The current frame from the game.
        player_name: Player's name.
        score: Player's score.
        game_mode: The game mode.
        supabase_url: URL of the Supabase instance.
        supabase_key: API key for Supabase authentication.
    Returns:
        The public URL of the uploaded screenshot or None if any step failed.
    """
    # Capture screenshot
    screenshot = capture_playfield_screenshot(frame)
    if screenshot is None:
        return None

    # Save locally
    file_path = save_screenshot_locally(screenshot, player_name, score, game_mode)
    if file_path is None:
        return None

    # Upload to Supabase
    return upload_screenshot_to_supabase(
        file_path, supabase_url, supabase_key, player_name, score, game_mode
    )
