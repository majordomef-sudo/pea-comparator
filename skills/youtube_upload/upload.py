#!/usr/bin/env python3
import os
import sys
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]
CLIENT_SECRETS = os.path.expanduser("~/.secrets/client_secrets.json")
TOKEN_FILE = os.path.expanduser("~/.secrets/youtube_token.json")

def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None # Force re-auth if refresh fails
        
        if not creds:
            # Check if we are in an interactive terminal
            if sys.stdin.isatty():
                print("Initiating manual authentication...")
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
                flow.redirect_uri = 'http://localhost'
                auth_url, _ = flow.authorization_url(prompt='consent')
                print(f"\n1. Please go to this URL in your browser:\n{auth_url}\n")
                print("2. After authorizing, you will be redirected to a page that might not load (localhost).")
                print("3. Copy the 'code' parameter from the URL in your address bar (e.g., ?code=4/0Af...)")
                code = input("\nEnter the authorization code: ").strip()
                flow.fetch_token(code=code)
                creds = flow.credentials
            else:
                raise RuntimeError("YouTube OAuth token expired and interactive re-authentication is not possible in this environment. Please run upload.py manually via SSH to re-authenticate.")
        
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds

def upload_video(video_path, title, description="", playlist_id=None, tags=None):
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title, "description": description, "categoryId": "27"},
        "status": {"privacyStatus": "public"}
    }
    if tags:
        body["snippet"]["tags"] = tags
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]
    
    if playlist_id:
        playlist_body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
        youtube.playlistItems().insert(part="snippet", body=playlist_body).execute()
        
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(url)
    return url

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: upload.py <video_path> <title> [description] [playlist_id] [tags_json]")
        sys.exit(1)
    desc = sys.argv[3] if len(sys.argv) > 3 else ""
    pid = sys.argv[4] if len(sys.argv) > 4 else None
    tags = json.loads(sys.argv[5]) if len(sys.argv) > 5 else None
    upload_video(sys.argv[1], sys.argv[2], desc, pid, tags)
