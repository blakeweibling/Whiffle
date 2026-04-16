import os
import logging
from typing import Optional, Tuple

import httplib2
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google_auth_httplib2 import AuthorizedHttp
import pickle

# Set up logging
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Network timeout in seconds for Drive API calls and credential refresh.
# Without this the underlying httplib2 client can hang indefinitely on bad
# connectivity, blocking whichever thread initiated the upload.
DRIVE_HTTP_TIMEOUT_SECONDS = 60


def _build_http_with_timeout() -> httplib2.Http:
    """Return an httplib2.Http instance with a bounded request timeout."""
    return httplib2.Http(timeout=DRIVE_HTTP_TIMEOUT_SECONDS)

# Path to the OAuth credentials file (credentials.json)
CREDENTIALS_FILE = "configs/google_credentials.json"
TOKEN_PICKLE_FILE = "configs/token.pickle"


def get_credentials() -> Optional[Credentials]:
    """
    Get Google Drive API credentials.

    Returns:
        Google OAuth2 credentials or None if authentication fails
    """
    creds = None

    # Check if we have a token.pickle file with saved credentials
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, "rb") as token:
            try:
                creds = pickle.load(token)
            except Exception as e:
                logger.error(f"Error loading credentials from token.pickle: {e}")

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                # Bound the refresh HTTP call with an explicit timeout.
                creds.refresh(Request(timeout=DRIVE_HTTP_TIMEOUT_SECONDS))
            except Exception as e:
                logger.error(f"Error refreshing Google credentials: {e}")
                return None
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                logger.error(f"Google credentials file not found at {CREDENTIALS_FILE}")
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.error(f"Error during Google authentication flow: {e}")
                return None

        # Save the credentials for the next run
        try:
            os.makedirs(os.path.dirname(TOKEN_PICKLE_FILE), exist_ok=True)
            with open(TOKEN_PICKLE_FILE, "wb") as token:
                pickle.dump(creds, token)
        except Exception as e:
            logger.error(f"Error saving credentials to token.pickle: {e}")

    return creds


def upload_video_to_drive(file_path: str, title: str = None) -> Tuple[bool, str]:
    """
    Upload a video file to Google Drive and make it shareable.

    Args:
        file_path: Path to the video file to upload
        title: Optional title for the uploaded file (defaults to filename)

    Returns:
        Tuple of (success: bool, message: str)
        If successful, message contains the shareable link
        If failed, message contains the error description
    """
    # Check if file exists
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"

    # Use filename as title if not provided
    if title is None:
        title = os.path.basename(file_path)

    # Get credentials
    creds = get_credentials()
    if not creds:
        return (
            False,
            "Failed to authenticate with Google Drive. Check your credentials.",
        )

    try:
        # Build the Drive API client with a timeout-bounded HTTP transport so
        # Drive calls cannot hang the app indefinitely on network failure.
        # When ``http`` is provided, ``credentials`` must not be, so wrap the
        # Http in AuthorizedHttp which injects the bearer token per request.
        authed_http = AuthorizedHttp(creds, http=_build_http_with_timeout())
        service = build("drive", "v3", http=authed_http)

        # Determine the MIME type based on file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext == ".gif":
            mime_type = "image/gif"
        else:
            mime_type = "video/mp4"

        # Define file metadata
        file_metadata = {"name": title, "mimeType": mime_type}

        # Create a media upload object
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        # Upload the file
        logger.info(f"Uploading {file_path} to Google Drive...")
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )

        # Make the file publicly accessible with a link
        permission = {"type": "anyone", "role": "reader"}
        service.permissions().create(fileId=file.get("id"), body=permission).execute()

        # Get the shareable link
        file = (
            service.files().get(fileId=file.get("id"), fields="webViewLink").execute()
        )

        shareable_link = file.get("webViewLink")

        return True, shareable_link

    except Exception as e:
        logger.error(f"Error uploading to Google Drive: {e}")
        return False, f"Error uploading to Google Drive: {str(e)}"
