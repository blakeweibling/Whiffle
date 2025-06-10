# Google Drive Integration for Video Sharing

This README explains how to set up Google Drive integration to enable video sharing in Whiffle.

## Setup Instructions

### 1. Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. From the Navigation menu, go to "APIs & Services" > "Library"
4. Search for "Google Drive API" and enable it for your project

### 2. Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
2. Select "External" user type (unless you're using a Google Workspace account)
3. Fill out the required information:
   - App name: "Whiffle Game"
   - User support email: your email
   - Developer contact information: your email
4. Add the scopes "/auth/drive.file" (allows access to files created by the app)
5. Add any test users you want to use during development
6. Complete the setup

### 3. Create OAuth Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Select "Desktop app" for application type
4. Name your client (e.g., "Whiffle Desktop Client")
5. Click "Create"
6. Download the JSON file with your credentials

### 4. Set Up Whiffle Game

1. Rename the downloaded JSON file to `google_credentials.json`
2. Place it in the `configs` directory of your Whiffle installation
3. The game will automatically use these credentials when you share a video

## First-Time Usage

The first time you share a video using the "Share Link" feature:

1. A browser window will open asking you to authorize the application
2. Sign in with your Google account and grant the requested permissions
3. After authorization, your browser will show a success message
4. The authorization token will be saved for future uploads

## Troubleshooting

- If you encounter permission errors, ensure your Google Cloud Project has the Drive API enabled
- If you change the scope of access, delete the `configs/token.pickle` file to force re-authentication
- For other issues, check the game logs for specific error messages

## Security Note

Your OAuth credentials are sensitive. Do not share them publicly or commit them to public repositories. The `google_credentials.json` file should be kept private and secure. 