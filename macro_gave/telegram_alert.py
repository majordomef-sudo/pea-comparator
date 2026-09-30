"""Alertes Telegram - uniquement sur changement significatif (anti-spam)."""
import requests, os
from pathlib import Path

def _load_creds():
    s = {}
    env = Path.home() / ".secrets" / "env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line:
                line = line.replace("export ", "").strip()
                k, v = line.split("=", 1)
                s[k] = v.strip(chr(34)).strip(chr(39))
    return s

def send_alert(text, level="INFO"):
    creds = _load_creds()
    bt, ci = creds.get("TELEGRAM_BOT_TOKEN"), creds.get("TELEGRAM_CHAT_ID")
    if not (bt and ci):
        print("[TG] pas de creds, alerte non envoyee")
        return False
    import requests
    try:
        requests.post("https://api.telegram.org/bot"+bt+"/sendMessage",
            data={"chat_id": ci, "text": "[INCLUSION] " + text}, timeout=10)
        return True
    except Exception as e:
        print("[TG] erreur: " + str(e))
        return False

def should_alert(prev, new):
    # prev/new: dicts avec quadrant, transition, scores
    if not prev: return True
    if prev.get("quadrant") != new.get("quadrant"): return True
    if abs(new.get("transition",99) - prev.get("transition",0)) >= 15: return True
    if new.get("alert_red") and not prev.get("alert_red"): return True
    return False