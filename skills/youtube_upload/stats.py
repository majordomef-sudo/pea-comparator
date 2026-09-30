#!/usr/bin/env python3
import os, sys
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
CLIENT_SECRETS = os.path.expanduser("~/.secrets/client_secrets.json")
TOKEN_FILE = os.path.expanduser("~/.secrets/youtube_token.json")

def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds

def get_stats():
    creds = get_credentials()
    if not creds:
        print("❌ Pas de credentials. Lance upload.py d'abord.")
        sys.exit(1)

    youtube = build("youtube", "v3", credentials=creds)

    # Infos chaîne
    channel = youtube.channels().list(
        part="snippet,statistics",
        mine=True
    ).execute()

    ch = channel["items"][0]
    stats = ch["statistics"]
    snippet = ch["snippet"]

    print(f"📺 Chaîne : {snippet['title']}")
    print(f"👥 Abonnés : {int(stats.get('subscriberCount', 0)):,}")
    print(f"🎬 Vidéos  : {stats.get('videoCount', 0)}")
    print(f"👁️  Vues total : {int(stats.get('viewCount', 0)):,}")
    print()

    # Dernières vidéos
    videos = youtube.search().list(
        part="snippet",
        forMine=True,
        type="video",
        order="date",
        maxResults=5
    ).execute()

    print("📋 Dernières vidéos :")
    ids = [v["id"]["videoId"] for v in videos.get("items", [])]

    if ids:
        details = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(ids)
        ).execute()

        for v in details["items"]:
            s = v["statistics"]
            title = v["snippet"]["title"][:45]
            views = int(s.get("viewCount", 0))
            likes = int(s.get("likeCount", 0))
            vid_id = v["id"]
            print(f"  • {title}")
            print(f"    👁️ {views:,} vues | 👍 {likes:,} likes | https://youtu.be/{vid_id}")

if __name__ == "__main__":
    get_stats()
