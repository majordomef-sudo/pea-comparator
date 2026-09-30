# -*- coding: utf-8 -*-
"""Retention reelle par video : ou decrochent les spectateurs. A lancer une fois l'OAuth analytics valide."""
import sys, json, datetime
from pathlib import Path
sys.path.insert(0, "/home/ubuntu/.openclaw/workspace/skills/youtube_upload")
from stats import get_credentials
from googleapiclient.discovery import build

creds = get_credentials()
yta = build("youtubeAnalytics", "v2", credentials=creds)
end = datetime.date.today()
start = end - datetime.timedelta(days=90)
r = yta.reports().query(
    ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
    metrics="views,averageViewDuration,averageViewPercentage",
    dimensions="video", sort="-views", maxResults=50).execute()
cols = [c["name"] for c in r.get("columnHeaders", [])]
print("colonnes:", cols)
rows = r.get("rows", [])
print("videos avec donnees:", len(rows))
out = []
for row in rows:
    d = dict(zip(cols, row))
    out.append(d)
    print(" ", d.get("video", ""), "| vues", d.get("views"), "| duree moyenne", d.get("averageViewDuration"), "s | vues moyennes", d.get("averageViewPercentage"), "%")
Path("/home/ubuntu/.openclaw/workspace/state/retention.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("sauve dans state/retention.json")
