# -*- coding: utf-8 -*-
"""Score de retention 0-10 (echelle = percentile de la chaine) depuis averageViewPercentage.
Remplace le hook_score interne : 4 valeurs pour 50 videos, anti-correle aux vues.
Source state/retention.json (YouTube Analytics). Sorties : state/retention_scores.json
+ enrichissement de state/auto-reflection/hook_history.json. ASCII only."""
import json, os, re, glob, unicodedata
from pathlib import Path
WS = Path("/home/ubuntu/.openclaw/workspace")
OUT_DIR = Path("/home/ubuntu/output")
REF_MIN_VIEWS = 10
REF_FALLBACK_VIEWS = 5
REF_MIN_SAMPLES = 8

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return "".join(c for c in s.lower() if c.isalnum() or c == " ").strip()

def first_sentence(t):
    parts = re.split(r"(?<=[.!?])\s+", (t or "").strip())
    return parts[0] if parts else ""

# --- appariement nom de fichier local -> titre (via les JSON de script du pipeline)
_titles = {}

def resolve_title(video_name):
    if not video_name:
        return ""
    stem = os.path.basename(str(video_name))
    for ext in (".mp4", ".mov", ".webm"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
    if stem in _titles:
        return _titles[stem]
    cand = OUT_DIR / ("script-" + stem + ".json")
    title = ""
    if cand.exists():
        try:
            title = json.loads(cand.read_text(encoding="utf-8")).get("title", "") or ""
        except Exception:
            title = ""
    if not title:
        title = stem.replace("_", " ")
    _titles[stem] = title
    return title

src = json.loads((WS / "state/retention.json").read_text(encoding="utf-8"))
refs = [v for v in src if v["views"] >= REF_MIN_VIEWS]
note = "seuil %d vues" % REF_MIN_VIEWS
if len(refs) < REF_MIN_SAMPLES:
    refs = [v for v in src if v["views"] >= REF_FALLBACK_VIEWS]
    note = "seuil abaisse a %d vues (moins de %d videos a %d vues)" % (REF_FALLBACK_VIEWS, REF_MIN_SAMPLES, REF_MIN_VIEWS)
pcts = sorted(float(v["avg_pct"]) for v in refs)

def pct_at(q):
    if not pcts:
        return None
    return round(pcts[min(len(pcts) - 1, int(round(q * (len(pcts) - 1))))], 1)

reference = {"n": len(refs), "note": note, "min_views": REF_MIN_VIEWS,
             "median_pct": pct_at(0.5), "p25_pct": pct_at(0.25), "p75_pct": pct_at(0.75),
             "mean_pct": round(sum(pcts) / len(pcts), 1) if pcts else None}

def score_of(pct):
    if not pcts:
        return None
    lower = sum(1 for p in pcts if p < pct)
    equal = sum(1 for p in pcts if p == pct)
    return round(10.0 * (lower + 0.5 * equal) / len(pcts), 1)

vids = []
for v in src:
    pct = float(v["avg_pct"])
    sc = score_of(pct)
    fiable = v["views"] >= REF_MIN_VIEWS
    verdict = "gagnante" if (sc or 0) >= 7 else ("correcte" if (sc or 0) >= 4 else "perdante")
    if not fiable:
        verdict += " (echantillon mince)"
    vids.append({"id": v["id"], "title": v["title"], "views": v["views"], "avg_pct": round(pct, 2),
                 "avg_duration_s": float(v["avg_duration_s"]), "duration_s": v["duration_s"],
                 "retention_score": sc, "verdict": verdict, "fiable": fiable,
                 "opening": first_sentence(v.get("hook") or "")})
out = {"generated": "2026-09-27", "source": "state/retention.json (YouTube Analytics, 90 j)",
       "echelle": "percentile de la chaine : 5 = mediane, 10 = meilleure, 0 = pire",
       "fiabilite": "fiable = au moins %d vues ; en dessous le score est indicatif" % REF_MIN_VIEWS,
       "reference": reference, "videos": vids}
(WS / "state/retention_scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

# --- enrichir hook_history.json
hh = WS / "state" / "auto-reflection" / "hook_history.json"
if hh.exists():
    hist = json.loads(hh.read_text(encoding="utf-8"))
    idx = {norm(v["title"]): v for v in vids}
    n = 0
    for h in hist:
        t = resolve_title(h.get("video", ""))
        v = idx.get(norm(t))
        if v:
            h["retention_pct"] = v["avg_pct"]
            h["retention_score"] = v["retention_score"]
            h["retention_fiable"] = v["fiable"]
            n += 1
    hh.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    print("hook_history.json enrichi :", n, "entrees /", len(hist))

print("=== REFERENCE CHAINE (%s) ===" % note)
print("  n=%d | mediane %s %% vu | p25 %s | p75 %s | moyenne %s %%" % (
    reference["n"], reference["median_pct"], reference["p25_pct"], reference["p75_pct"], reference["mean_pct"]))
print()
rel = [v for v in vids if v["fiable"]]
print("=== TOP 6 RETENTION (>= %d vues, score 0-10) ===" % REF_MIN_VIEWS)
for v in sorted(rel, key=lambda x: -x["retention_score"])[:6]:
    print("  %4.1f/10 | %5.1f %% vu | %3d vues | %s" % (v["retention_score"], v["avg_pct"], v["views"], v["title"][:46]))
print()
print("=== FLOP 6 RETENTION (>= %d vues) ===" % REF_MIN_VIEWS)
for v in sorted(rel, key=lambda x: x["retention_score"])[:6]:
    print("  %4.1f/10 | %5.1f %% vu | %3d vues | %s" % (v["retention_score"], v["avg_pct"], v["views"], v["title"][:46]))
print()
print("  videos ecartees du classement (moins de %d vues) : %d" % (REF_MIN_VIEWS, len(vids) - len(rel)))
print("ecrit : state/retention_scores.json")
