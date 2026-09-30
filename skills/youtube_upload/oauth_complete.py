# -*- coding: utf-8 -*-
"""Finalise la reautorisation OAuth : echange le code contre un token, verifie les scopes."""
import os, sys, json, time, shutil
from google_auth_oauthlib.flow import InstalledAppFlow

CS = os.path.expanduser("~/.secrets/client_secrets.json")
TOK = os.path.expanduser("~/.secrets/youtube_token.json")
PENDING = os.path.expanduser("~/.secrets/oauth_pending.json")

code = sys.argv[1].strip() if len(sys.argv) > 1 else ""
if "code=" in code:
    code = code.split("code=")[-1].split("&")[0]
if not code:
    print("ERREUR: aucun code fourni (usage: python3 oauth_complete.py '<code ou URL>')")
    sys.exit(1)

p = json.load(open(PENDING))
flow = InstalledAppFlow.from_client_secrets_file(CS, p["scopes"])
flow.redirect_uri = p["redirect_uri"]
flow.code_verifier = p["code_verifier"]
flow.fetch_token(code=code)
creds = flow.credentials

# le token doit contenir le client_secret pour que le refresh fonctionne (patch du 25/08)
tok = json.loads(creds.to_json())
if not tok.get("client_secret"):
    tok["client_secret"] = json.load(open(CS))["installed"]["client_secret"]
    print("client_secret reinjecte dans le token")
json.dump(tok, open(TOK, "w"), indent=1)
print("token ecrit :", TOK)
scopes = set(creds.scopes or tok.get("scopes") or [])
print("scopes accordes :", sorted(scopes))
print("analytics present :", "https://www.googleapis.com/auth/yt-analytics.readonly" in scopes)
print("refresh_token present :", bool(tok.get("refresh_token")))
os.remove(PENDING)

# test : API YouTube Analytics sur les 28 derniers jours
try:
    from googleapiclient.discovery import build
    import datetime
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    end = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=28)).isoformat()
    r = yta.reports().query(ids="channel==MINE", startDate=start, endDate=end,
                            metrics="views,averageViewDuration,averageViewPercentage",
                            dimensions="video", sort="-views", maxResults=5).execute()
    print("TEST ANALYTICS OK (28 j) :")
    for row in r.get("rows", []):
        print("  ", row)
except Exception as e:
    msg = str(e)
    print("TEST ANALYTICS ECHEC :", msg[:300])
    if "has not been used" in msg or "disabled" in msg or "403" in msg:
        print(">>> ACTION : activer 'YouTube Analytics API' dans le projet alfred-youtube-492308 (console GCP).")
