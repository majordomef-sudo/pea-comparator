#!/usr/bin/env python3
"""
seo_tracker.py — Suivi SEO via Google Search Console API
Utilise le service account existant pour tracker les positions réelles.
"""
import json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from notify_alfred import send_telegram

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
HISTORY_FILE = WORKSPACE / "state" / "seo_history.json"

GSC_KEY = os.path.expanduser("~/.secrets/gsc-service-account.json")
SITE_URL = 'https://alfredstudio.mooo.com/'

def get_gsc_service():
    """Retourne le service Google Search Console."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        credentials = service_account.Credentials.from_service_account_file(
            GSC_KEY,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        service = build("searchconsole", "v1", credentials=credentials)
        return service
    except Exception as e:
        print(f"  ⚠️ GSC: {e}")
        return None

def query_gsc(service):
    """Interroge GSC pour les positions des mots-clés."""
    try:
        request = {
            "startDate": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "endDate": datetime.now().strftime("%Y-%m-%d"),
            "dimensions": ["query"],
            "rowLimit": 10
        }
        response = service.searchanalytics().query(
            siteUrl=SITE_URL, body=request
        ).execute()
        
        results = []
        for row in response.get("rows", []):
            results.append({
                "keyword": row["keys"][0],
                "impressions": row["impressions"],
                "clicks": row["clicks"],
                "ctr": round(row["ctr"] * 100, 2),
                "position": round(row["position"], 1),
            })
        return results
    except Exception as e:
        print(f"  ⚠️ GSC query: {e}")
        return []

def run():
    print("🔍 SEO Tracker — Google Search Console...")
    
    service = get_gsc_service()
    if not service:
        print("  Fallback: vérification DuckDuckGo")
        # Fallback to basic search
        import urllib.request, urllib.parse
        MOTS_CLES = ["comparateur PEA", "ETF PEA", "calculateur intérêts composés"]
        results = []
        for kw in MOTS_CLES:
            try:
                url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(kw)}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                count = html.lower().count("alfredstudio.mooo.com")
                results.append({"keyword": kw, "mentions": count, "source": "duckduckgo"})
            except Exception as e:
                results.append({"keyword": kw, "error": str(e), "source": "duckduckgo"})
    else:
        results = query_gsc(service)
        for r in results:
            r["source"] = "gsc"
            print(f"  {r['keyword']}: pos {r['position']} ({r['impressions']} impressions)")
    
    entry = {
        "date": datetime.now().isoformat(),
        "keywords": results
    }
    
    history = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            try:
                history = json.load(f)
            except:
                pass
    history.append(entry)
    history = history[-90:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    
    print(f"✅ SEO terminé — {len(results)} mot(s)-clé")

    # Notification Telegram
    try:
        msg = f"🔍 SEO Tracker — {len(results)} mot(s)-clé"
        for r in results[:5]:
            if 'position' in r:
                msg += f"\n{r['keyword']}: pos {r['position']} ({r['impressions']} impressions)"
            elif 'mentions' in r:
                msg += f"\n{r['keyword']}: {r['mentions']} mention(s)"
        send_telegram(msg)
    except Exception as e:
        print(f'Notif error: {e}', file=sys.stderr)



if __name__ == "__main__":
    run()
