import os
import logging
import httplib2
import time
import json
from typing import Optional, Tuple, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets, OAuth2Credentials
from oauth2client.tools import run_flow
from oauth2client import tools
import argparse

from constants import YouTubeConstants

# Set up logging
logger = logging.getLogger(__name__)


def get_youtube_credentials() -> Optional[Dict[str, Any]]:
    """
    Get the YouTube/Google API credentials from the stored file.

    Returns:
        Optional[Dict[str, Any]]: Credentials object or None if not available
    """
    # Storage file for OAuth2 credentials
    token_path = os.path.join("configs", "youtube_token.json")

    # Client secrets file path (needed for OAuth2 flow)
    client_secrets_path = os.path.join("configs", "client_secrets.json")

    # Check if client secrets file exists
    if not os.path.exists(client_secrets_path):
        logger.error(f"Google credentials file not found at {client_secrets_path}")
        # Try the alternate path
        client_secrets_path = os.path.join("configs", "google_credentials2.json")
        if not os.path.exists(client_secrets_path):
            logger.error(
                "No valid credentials file found. Creating a placeholder file."
            )
            create_placeholder_credentials(client_secrets_path)
            return None

    try:
        # Create a storage object for credentials
        storage = Storage(token_path)

        # Try to get existing credentials
        credentials = storage.get()

        # If credentials don't exist or are invalid, try to create new ones
        if credentials is None or credentials.invalid:
            logger.warning(
                "YouTube credentials are missing or invalid. Attempting to generate new ones."
            )
            try:
                return generate_new_credentials(client_secrets_path, token_path)
            except Exception as auth_error:
                logger.error(f"Error generating new YouTube credentials: {auth_error}")
                return None

        # Return valid credentials
        return credentials
    except Exception as e:
        logger.error(f"Error getting YouTube credentials: {e}")
        return None


def create_placeholder_credentials(file_path: str) -> None:
    """
    Creates a placeholder client_secrets.json file with instructions

    Args:
        file_path: Path where to create the placeholder file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Create a placeholder with instructions
        placeholder = {
            "installed": {
                "client_id": "YOUR_CLIENT_ID",
                "project_id": "YOUR_PROJECT_ID",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "YOUR_CLIENT_SECRET",
                "redirect_uris": ["http://localhost:8080/"],
            },
            "_comment": "Replace with actual values from Google Cloud Console: https://console.cloud.google.com/",
        }

        # Write the placeholder to file
        with open(file_path, "w") as f:
            json.dump(placeholder, f, indent=4)

        logger.info(f"Created placeholder credentials file at {file_path}")
        logger.info(
            "Please edit this file with your actual Google Cloud OAuth credentials"
        )
    except Exception as e:
        logger.error(f"Error creating placeholder credentials: {e}")


def generate_new_credentials(
    client_secrets_path: str, token_path: str
) -> Optional[OAuth2Credentials]:
    """
    Generate new YouTube API credentials using OAuth2 flow.

    Args:
        client_secrets_path: Path to the client secrets JSON file
        token_path: Path to store the generated token

    Returns:
        OAuth2Credentials or None if authentication fails
    """
    try:
        # Create directory for token if it doesn't exist
        os.makedirs(os.path.dirname(token_path), exist_ok=True)

        # Define the required scopes for YouTube uploads
        scopes = ["https://www.googleapis.com/auth/youtube.upload"]

        # Log the authentication process
        logger.info("Starting YouTube authentication process")

        # Set up a simple command line argument parser for the OAuth flow
        # import sys
        # import argparse
        #
        # parser = argparse.ArgumentParser(add_help=False)
        # parser.add_argument("--auth_host_name", default="localhost")
        # parser.add_argument(
        #     "--auth_host_port", default=[8080, 8090], type=int, nargs="*"
        # )
        # parser.add_argument(
        #     "--noauth_local_webserver", action="store_true", default=False
        # )
        # args, _ = parser.parse_known_args()
        # --- END REMOVED section ---

        # --- ADD default flags for run_flow ---
        # Create default flags using tools.argparser - this includes logging_level
        parent_parser = argparse.ArgumentParser(parents=[tools.argparser])
        flags = parent_parser.parse_args([])
        # --- END ADDED section ---

        # Create the OAuth2 flow object
        flow = flow_from_clientsecrets(
            client_secrets_path,
            scope=scopes,
            message="Error loading client secrets file",
        )

        # Set the redirect URI to match what's in the client_secrets file
        flow.redirect_uri = "http://localhost:8080/"

        # Create the storage to save the credentials
        storage = Storage(token_path)

        # Show a notification about authentication
        logger.info(
            "Please authenticate with your Google account in the browser window that opens"
        )

        # Try to open a web browser for authentication
        import webbrowser

        try:
            # Open authentication URL in the default browser
            auth_uri = flow.step1_get_authorize_url()
            webbrowser.open(auth_uri, new=1, autoraise=True)
            logger.info(f"Opening browser for authentication: {auth_uri}")

            # Let the user know they need to complete the process in the browser
            print("\n=====================================================")
            print("   Please complete the YouTube authentication process")
            print("   in the browser window that just opened.")
            print("=====================================================\n")
        except Exception as browser_error:
            logger.error(f"Failed to open browser: {browser_error}")
            print("\n=====================================================")
            print("   Please manually open this URL to authenticate:")
            print(f"   {auth_uri}")
            print("=====================================================\n")

        # Run the OAuth2 flow to get credentials
        # Pass the default flags instead of custom args
        credentials = run_flow(flow, storage, flags)

        logger.info("Successfully authenticated with YouTube API")
        return credentials
    except Exception as e:
        logger.error(f"Error during YouTube authentication: {e}")
        print("\n=====================================================")
        print("   YouTube authentication failed. Please ensure you have:")
        print(
            "   1. Valid client_secrets.json file in configs/google_credentials2.json"
        )
        print("   2. Enabled the YouTube Data API in your Google Cloud Console")
        print("   3. Configured OAuth2 consent screen properly")
        print("=====================================================\n")
        return None


def upload_video_to_youtube(
    video_path: str, player_name: str, score: int, game_mode: str
) -> Tuple[bool, str]:
    """
    Upload a video to YouTube.

    Args:
        video_path (str): Path to the video file
        player_name (str): Name of the player
        score (int): Score achieved in the game
        game_mode (str): Game mode played

    Returns:
        Tuple[bool, str]: Success status and YouTube URL or error message
    """
    # Check if file exists
    if not os.path.exists(video_path):
        return False, f"Video file not found: {video_path}"

    # Check file size
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if file_size_mb > YouTubeConstants.MAX_VIDEO_SIZE_MB:
        return (
            False,
            f"Video file too large: {file_size_mb:.2f}MB (max: {YouTubeConstants.MAX_VIDEO_SIZE_MB}MB)",
        )

    # Get credentials
    credentials = get_youtube_credentials()
    if not credentials:
        return False, "Failed to obtain YouTube credentials"

    try:
        # Build the YouTube API service
        youtube = build("youtube", "v3", credentials=credentials)

        # Prepare video metadata
        # Use constants for templates and defaults
        title = YouTubeConstants.TITLE_TEMPLATE.format(
            player=player_name if YouTubeConstants.INCLUDE_PLAYER_NAME else "Player",
            score=score,
            game_mode=game_mode,
        )

        description = YouTubeConstants.DESCRIPTION_TEMPLATE.format(
            player=player_name if YouTubeConstants.INCLUDE_PLAYER_NAME else "Player",
            score=score,
            game_mode=game_mode,
        )

        # Create upload request body
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": YouTubeConstants.DEFAULT_TAGS,
                "categoryId": YouTubeConstants.DEFAULT_CATEGORY_ID,
            },
            "status": {"privacyStatus": YouTubeConstants.DEFAULT_PRIVACY_STATUS},
        }

        # Create upload request with progress tracking
        media = MediaFileUpload(
            video_path, mimetype="video/*", resumable=True, chunksize=1024 * 1024
        )

        # Execute the request
        request = youtube.videos().insert(
            part=",".join(body.keys()), body=body, media_body=media
        )

        # Upload the video with progress tracking
        logger.info(f"Starting YouTube upload for {title}...")
        response = None
        retries = 0

        while response is None and retries < YouTubeConstants.MAX_RETRIES:
            try:
                status, response = request.next_chunk()
                if status:
                    percent = int(status.progress() * 100)
                    logger.info(f"Upload progress: {percent}%")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    retries += 1
                    if retries >= YouTubeConstants.MAX_RETRIES:
                        return (
                            False,
                            f"YouTube upload failed after {retries} retries: {e}",
                        )
                    logger.warning(f"YouTube upload error (retry {retries}): {e}")
                    time.sleep(5)  # Wait before retrying
                else:
                    return False, f"YouTube upload error: {e}"

        # Get the video ID and URL
        video_id = response["id"]
        video_url = f"https://youtu.be/{video_id}"

        logger.info(f"Successfully uploaded video to YouTube: {video_url}")
        return True, video_url

    except HttpError as e:
        error_message = f"HTTP error during YouTube upload: {e}"
        logger.error(error_message)
        return False, error_message
    except Exception as e:
        error_message = f"Unexpected error during YouTube upload: {e}"
        logger.error(error_message)
        return False, error_message
