# -*- coding: utf-8 -*-
"""Retention reelle par video (YouTube Analytics API) + croisement avec les hooks.
Lecture seule. Sauvegarde state/retention.json. ASCII only."""
import os, sys, json, datetime, unicodedata
sys.path.insert(0, "/home/ubuntu/.openclaw/workspace/skills/youtube_upload")
from stats import get_credentials
from googleapiclient.discovery import build

WS = "/home/ubuntu/.openclaw/workspace"
creds = get_credentials()
yta = build("youtubeAnalytics", "v2", credentials=creds)
yt = build("youtube", "v3", credentials=creds)

end = datetime.date.today()
start = end - datetime.timedelta(days=90)
rows, token = [], None
while True:
    req = yta.reports().query(ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
                              metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
                              dimensions="video", sort="-views", maxResults=200)
    if token:
        req = req.get("_unused")
    r = req.execute()
    rows.extend(r.get("rows", []))
    break
print("videos avec donnees analytics (90 j):", len(rows))
if not rows:
    print("aucune donnee -> arret")
    sys.exit(0)

ids = [x[0] for x in rows]
meta = {}
for i in range(0, len(ids), 50):
    d = yt.videos().list(part="snippet,contentDetails,statistics", id=",".join(ids[i:i+50])).execute()
    for v in d.get("items", []):
        meta[v["id"]] = v
print("metadonnees recuperees:", len(meta))

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return "".join(c for c in s.lower() if c.isalnum() or c == " ").strip()

hooks = {}
for p in [WS + "/tmp_hooks/hooks.json", WS + "/tmp_hooks/rows.json"]:
    if os.path.exists(p):
        try:
            d = json.load(open(p))
            items = d if isinstance(d, list) else list(d.values())
            for it in items:
                if not isinstance(it, dict):
                    continue
                t = it.get("title") or it.get("video") or ""
                if t:
                    hooks[norm(t)] = it
        except Exception as e:
            print("lecture", p, "echec:", str(e)[:80])
print("entrees hooks chargees:", len(hooks))

def iso_sec(s):
    if not s:
        return None
    s = s.replace("PT", "")
    h = m = 0
    if "H" in s:
        h = int(s.split("H")[0]); s = s.split("H")[1]
    if "M" in s:
        m = int(s.split("M")[0]); s = s.split("M")[1]
    sec = int(float(s.replace("S", ""))) if s.replace("S", "") else 0
    return h * 3600 + m * 60 + sec

out = []
for vid, views, minutes, avgdur, avgpct in rows:
    m = meta.get(vid, {})
    title = m.get("snippet", {}).get("title", "?")
    dur = iso_sec(m.get("contentDetails", {}).get("duration"))
    h = hooks.get(norm(title), {})
    out.append({"id": vid, "title": title, "views": views, "minutes": minutes,
                "avg_duration_s": avgdur, "avg_pct": round(avgpct, 2), "duration_s": dur,
                "hook": (h.get("hook") or h.get("first_sentence") or "")[:160],
                "hook_s": h.get("hook_s") or h.get("hook_seconds"),
                "pattern": h.get("pattern"), "opening": h.get("opening") or h.get("classe")})
json.dump(out, open(WS + "/state/retention.json", "w"), ensure_ascii=False, indent=1)

print()
print("=== 1. LES 12 PLUS VUES : vues | duree moyenne | %vu | duree video | titre ===")
for v in sorted(out, key=lambda x: -x["views"])[:12]:
    print("  %4d vues | %5s s | %6s %% | %5ss | %s" % (v["views"], v["avg_duration_s"], v["avg_pct"], v["duration_s"], v["title"][:52]))
print()
print("=== 2. LES 12 MEILLEURES RETENTIONS (>= 8 vues) ===")
for v in sorted([x for x in out if x["views"] >= 8], key=lambda x: -x["avg_pct"])[:12]:
    print("  %6s %% (%4d vues) | %5s s vus | duree %5s s | %s" % (v["avg_pct"], v["views"], v["avg_duration_s"], v["duration_s"], v["title"][:52]))
print()
n = len(out)
mv = sum(x["views"] for x in out) / n
mp = sum(x["avg_pct"] for x in out) / n
md = sum(float(x["avg_duration_s"]) for x in out) / n
print("=== 3. MOYENNES GLOBALES (90 j) ===")
print("  videos:", n, "| vues moy:", round(mv, 1), "| %%vu moy:", round(mp, 2), "| duree vue moy:", round(md, 1), "s")
crit = [x for x in out if x["views"] >= 20]
if crit:
    print("  videos >= 20 vues:", len(crit), "| %%vu moy:", round(sum(x["avg_pct"] for x in crit)/len(crit), 2),
          "| duree vue moy:", round(sum(float(x["avg_duration_s"]) for x in crit)/len(crit), 1), "s")
print()
print("=== 4. LE HOOK TIENT-IL ? (temps regarde en absolu) ===")
buckets = {"<5s (perdu d'entree)": 0, "5-15s (hook seulement)": 0, "15-40s (interesse)": 0, ">40s (captif)": 0}
for x in out:
    d = float(x["avg_duration_s"])
    if d < 5: buckets["<5s (perdu d'entree)"] += 1
    elif d < 15: buckets["5-15s (hook seulement)"] += 1
    elif d < 40: buckets["15-40s (interesse)"] += 1
    else: buckets[">40s (captif)"] += 1
for k, v in buckets.items():
    print("  %-26s %2d videos (%.0f %%)" % (k, v, 100.0*v/n))
print()
print("=== 5. CROISEMENT hook x retention (si hooks charges) ===")
grp = {}
for x in out:
    if not x["hook"]:
        continue
    hk = x["hook"].strip()
    cls = "question" if hk.endswith("?") else "affirmation/constat"
    grp.setdefault(cls, []).append(x)
for cls, arr in grp.items():
    if arr:
        print("  %-22s n=%2d | %%vu moy %.1f | duree vue moy %.1f s | vues moy %.1f" % (
            cls, len(arr), sum(a["avg_pct"] for a in arr)/len(arr),
            sum(float(a["avg_duration_s"]) for a in arr)/len(arr), sum(a["views"] for a in arr)/len(arr)))
