#!/usr/bin/env python3
"""
stats_youtube_nightly.py — Stats YouTube automatiques chaque nuit
Utilise l'API YouTube (token OAuth existant) et sauvegarde dans un historique.
"""
import json, os, sys, time
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from notify_alfred import send_telegram

sys.path.insert(0, str(Path("/home/ubuntu/.openclaw/workspace/skills/youtube_upload")))

from stats import get_credentials
from googleapiclient.discovery import build

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
HISTORY_FILE = WORKSPACE / "state" / "yt_stats_history.json"

def run():
    creds = get_credentials()
    if not creds:
        print("❌ Pas de credentials YouTube")
        return
    
    youtube = build("youtube", "v3", credentials=creds)
    
    # Infos chaîne
    channel = youtube.channels().list(
        part="snippet,statistics",
        mine=True
    ).execute()
    
    ch = channel["items"][0]
    stats = ch["statistics"]
    snippet = ch["snippet"]
    
    entry = {
        "date": datetime.now().isoformat(),
        "channel": snippet["title"],
        "subscribers": int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "total_videos": int(stats.get("videoCount", 0)),
        "videos": []
    }
    
    # Dernières vidéos
    videos = youtube.search().list(
        part="snippet",
        forMine=True,
        type="video",
        order="date",
        maxResults=10
    ).execute()
    
    ids = [v["id"]["videoId"] for v in videos.get("items", [])]
    if ids:
        details = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(ids)
        ).execute()
        
        for v in details["items"]:
            s = v["statistics"]
            entry["videos"].append({
                "id": v["id"],
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"],
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0))
            })
    
    # Charger historique
    history = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            try:
                history = json.load(f)
            except:
                pass
    
    history.append(entry)
    history = history[-90:]  # garder 90 jours
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    
    print(f"✅ Stats YouTube sauvegardées — {entry['subscribers']} abos, {entry['total_views']} vues")
    print(f"   {len(entry['videos'])} vidéos suivies")
    
    # Calculer tendance
    if len(history) >= 2:
        prev = history[-2]
        sub_diff = entry["subscribers"] - prev["subscribers"]
        view_diff = entry["total_views"] - prev["total_views"]
        print(f"   📈 {sub_diff:+d} abos / {view_diff:+d} vues depuis hier")

    # Notification Telegram
    try:
        msg = f"📊 Stats YouTube — {entry['subscribers']} abos, {entry['total_views']} vues"
        msg += f"\n   {len(entry['videos'])} vidéos suivies"
        if len(history) >= 2:
            prev = history[-2]
            sub_diff = entry['subscribers'] - prev['subscribers']
            view_diff = entry['total_views'] - prev['total_views']
            msg += f"\n   📈 {sub_diff:+d} abos / {view_diff:+d} vues (24h)"
        send_telegram(msg)
    except Exception as e:
        print(f'Notif error: {e}', file=sys.stderr)



if __name__ == "__main__":
    run()
