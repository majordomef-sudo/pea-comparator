#!/usr/bin/env python3
"""Analyse quotidienne des logs nginx -> rapport JSON + texte.
Parse access.log + access.log.1 + 2 gz recents (format combined nginx).
ZERO backslash dans ce fichier (le JSON mange les backslashes).
"""
import os, re, json, glob, gzip
from collections import Counter
from datetime import date

LOG_DIR = "/var/log/nginx"
OUT_DIR = "/home/ubuntu/.openclaw/workspace/state/analytics"
today = date.today()

ASSET_RE = re.compile(r'[.](js|css|png|jpg|jpeg|svg|ico|webp|woff2?|json|txt|xml|map)([?]|$)')
BOT_RE = re.compile(r'bot|crawl|spider|python-requests|curl|wget|Go-http|checker|scanner|semrush|ahrefs|mj12|bingpreview|facebookexternal|twitterbot|linkedinbot|slurp|baidu|yandex|monitor')
MOB_RE = re.compile(r'Mobile|Android|iPhone|iPad')

def read_lines():
    lines = []
    for f in [os.path.join(LOG_DIR, "access.log"), os.path.join(LOG_DIR, "access.log.1")]:
        if os.path.exists(f):
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    lines.extend(fh.readlines())
            except Exception:
                pass
    for f in sorted(glob.glob(os.path.join(LOG_DIR, "access.log.*.gz")))[-2:]:
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
                lines.extend(fh.readlines())
        except Exception:
            pass
    return lines

def parse(line):
    """retourne dict ou None. Format: IP - - [ts] "REQ" STATUS BYTES "REF" "UA" """
    try:
        parts = line.split('"')
        if len(parts) < 5:
            return None
        meta = parts[0].strip()
        req = parts[1].strip()
        stat = parts[2].strip().split()
        ref = parts[3].strip()
        ua = parts[5].strip() if len(parts) > 5 else ""
        if len(stat) < 2 or " " not in meta:
            return None
        ip = meta.split(" ")[0]
        ts = meta[meta.find("[")+1:meta.find("]")] if "[" in meta else ""
        method = req.split(" ")[0] if req else ""
        path = req.split(" ")[1] if len(req.split(" ")) > 1 else ""
        status = int(stat[0])
        return {"ip": ip, "ts": ts, "method": method, "path": path,
                "status": status, "ref": ref, "ua": ua}
    except Exception:
        return None

def main():
    stats = {
        "date": today.isoformat(), "hits": 0, "hits_pages": 0,
        "visiteurs_uniques": 0, "robots": 0, "erreurs_4xx": 0, "erreurs_5xx": 0,
        "mobile": 0, "desktop": 0, "top_pages": [], "top_referrers": [], "top_ua": []
    }
    ips = set(); pages = Counter(); refs = Counter(); uas = Counter()
    n = 0
    for line in read_lines():
        d = parse(line)
        if not d:
            continue
        n += 1
        stats["hits"] += 1
        ips.add(d["ip"])
        if d["ua"] and BOT_RE.search(d["ua"]):
            stats["robots"] += 1
        if 400 <= d["status"] < 500:
            stats["erreurs_4xx"] += 1
        if d["status"] >= 500:
            stats["erreurs_5xx"] += 1
        if MOB_RE.search(d["ua"]):
            stats["mobile"] += 1
        else:
            stats["desktop"] += 1
        if d["path"] and not ASSET_RE.search(d["path"]) and d["path"] not in ("/robots.txt", "/favicon.ico", "/apple-touch-icon.png"):
            stats["hits_pages"] += 1
            pages[d["path"].split("?")[0]] += 1
        if d["ref"] and "alfredstudio.mooo.com" not in d["ref"] and d["ref"] != "-":
            domain = re.sub(r'^https?://', "", d["ref"]).split("/")[0]
            refs[domain] += 1
        if d["ua"]:
            uas[d["ua"][:80]] += 1
    stats["total_lignes_parsees"] = n
    stats["visiteurs_uniques"] = len(ips)
    stats["top_pages"] = [{"page": p, "vues": c} for p, c in pages.most_common(8)]
    stats["top_referrers"] = [{"domaine": d, "clics": c} for d, c in refs.most_common(8)]
    stats["top_ua"] = [{"ua": u, "n": c} for u, c in uas.most_common(5)]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=1)
    hist = os.path.join(OUT_DIR, "history.json")
    history = {}
    if os.path.exists(hist):
        try:
            history = json.load(open(hist, encoding="utf-8"))
        except Exception:
            history = {}
    history[today.isoformat()] = stats
    with open(hist, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, indent=1)

    print("=== ANALYTICS SITE - " + stats["date"] + " ===")
    print("Lignes parsees:", stats["total_lignes_parsees"], "| Hits:", stats["hits"], "| Visiteurs uniques:", stats["visiteurs_uniques"])
    print("Hits pages:", stats["hits_pages"], "| Robots:", stats["robots"], "| 4xx:", stats["erreurs_4xx"], "| 5xx:", stats["erreurs_5xx"])
    print("Mobile:", stats["mobile"], "| Desktop:", stats["desktop"])
    print("Top pages:", ", ".join(t["page"] + " (" + str(t["vues"]) + ")" for t in stats["top_pages"][:5]))
    print("Top referrers:", ", ".join(t["domaine"] + " (" + str(t["clics"]) + ")" for t in stats["top_referrers"][:5]))
    print("Top UA:", " | ".join(t["ua"][:38] + " (" + str(t["n"]) + ")" for t in stats["top_ua"][:3]))

if __name__ == "__main__":
    main()
