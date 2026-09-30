#!/usr/bin/env python3
"""
veille_concurrence.py — Veille concurrentielle YouTube Finance
Utilise l'API YouTube publique + Chromium en fallback. Détecte les sujets chauds.
"""
import json, os, subprocess, sys, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from notify_alfred import send_telegram

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
OUTPUT_FILE = WORKSPACE / "state" / "veille_trends.json"
STATE_FILE = WORKSPACE / "state" / "veille_state.json"
BROWSER = "/snap/bin/chromium"

# Chaînes concurrentes (ID ou handle)
COMPETITORS = [
    {"name": "Henri ExplorIA", "handle": "@HenriExplorIA"},
]

def check_running():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
        if state.get("last_run", ""):
            last = datetime.fromisoformat(state["last_run"])
            if (datetime.now() - last).total_seconds() < 3600:
                return False
    return True

def search_youtube(query, max_results=5):
    """Recherche YouTube via l'API publique HTML."""
    try:
        urls = []
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # Extract video titles from ytInitialData
        for pattern in [r'"title":\{"runs":\[\{"text":"([^"]+)"',
                        r'"title":"([^"]+)"']:
            import re
            matches = re.findall(pattern, html)
            if matches:
                return matches[:max_results]
        return []
    except:
        return []

def get_channel_videos(handle):
    """Récupère les vidéos récentes d'une chaîne."""
    # Méthode 1 : YouTube search
    titles = search_youtube(handle, max_results=5)
    if titles:
        return [{"title": t} for t in titles]
    # Méthode 2 : oEmbed des dernières vidéos
    return []

def run():
    if not check_running():
        print("⏳ Dernière exécution trop récente, skip")
        return
    
    print(f"🔍 Veille concurrence — {len(COMPETITORS)} chaîne(s)...")
    results = []
    
    for comp in COMPETITORS:
        print(f"  {comp['name']}...")
        videos = get_channel_videos(comp["handle"])
        results.append({
            "name": comp["name"],
            "handle": comp["handle"],
            "videos": videos,
            "checked_at": datetime.now().isoformat()
        })
        if videos:
            for v in videos[:3]:
                print(f"    • {v.get('title', '?')[:70]}")
    
    output = {
        "last_run": datetime.now().isoformat(),
        "competitors": results
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    with open(STATE_FILE, "w") as f:
        json.dump({"last_run": datetime.now().isoformat()}, f)
    
    print(f"✅ Veille terminée — {len(results)} chaîne(s)")

    # Notification Telegram
    try:
        n = len(results)
        videos_found = sum(len(r.get('videos', [])) for r in results)
        msg = f"🔍 Veille concurrence — {n} chaîne(s) analysée(s)"
        msg += f"\n{videos_found} vidéo(s) trouvée(s)"
        for r in results:
            vids = r.get('videos', [])
            if vids:
                msg += f"\n• {r['name']}: {len(vids)} vidéos"
                for v in vids[:2]:
                    msg += f"\n{v.get('title', '?')[:60]}"
        send_telegram(msg)
    except Exception as e:
        print(f'Notif error: {e}', file=sys.stderr)



if __name__ == "__main__":
    run()
