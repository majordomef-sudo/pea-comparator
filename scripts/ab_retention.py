# -*- coding: utf-8 -*-
"""Mesure du test A/B ab_001 sur la RETENTION (averageViewPercentage), plus sur les vues.
Prospectif : videos assignees par le pipeline. Retrospectif : historique, pour la baseline."""
import json, re, unicodedata
from pathlib import Path
WS = Path("/home/ubuntu/.openclaw/workspace")
ret = json.loads((WS / "state/retention.json").read_text(encoding="utf-8"))
abp = WS / "state" / "auto-reflection" / "ab-testing.json"
ab = json.loads(abp.read_text(encoding="utf-8")) if abp.exists() else {"tests": []}

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return "".join(c for c in s.lower() if c.isalnum() or c == " ").strip()

by_title = {}
for v in ret:
    by_title.setdefault(norm(v["title"]), v)

def first_sentence(t):
    parts = re.split(r"(?<=[.!?])\s+", (t or "").strip())
    return parts[0] if parts else ""

def arm_of(text):
    return "A" if first_sentence(text).endswith("?") else "B"

# ---- PROSPECTIF : affectations reelles du pipeline
tests = ab.get("tests", [])
t = next((x for x in tests if x.get("id") == "ab_001"), None)
if t is None:
    print("ab_001 absent"); raise SystemExit(0)
assigns = t.get("assignments", [])
print("=== PROSPECTIF : %d video(s) assignee(s) par le pipeline ===" % len(assigns))
pro = {"A": [], "B": []}
for a in assigns:
    v = by_title.get(norm(a.get("title", "")))
    line = "  %s | %s | %s" % (a.get("date"), a.get("variant"), (a.get("title") or "")[:44])
    if v:
        line += " -> %s vues | %s %% vu | %ss" % (v["views"], v["avg_pct"], v["avg_duration_s"])
        if v["views"] > 0:
            pro[a["variant"]].append(v)
    else:
        line += " -> pas encore de donnees Analytics"
    print(line)

# ---- RETROSPECTIF : baseline sur l historique
print()
post = [v for v in ret if v.get("hook")]
rel = [v for v in post if v["views"] >= 10]
print("=== RETROSPECTIF (baseline honnete) : %d videos avec accroche connue, dont %d >= 10 vues ===" % (len(post), len(rel)))
def stats(arr):
    if not arr:
        return None
    p = sorted(x["avg_pct"] for x in arr)
    return {"n": len(arr), "pct_moyen": round(sum(p)/len(p), 1), "pct_median": round(p[len(p)//2], 1),
            "duree_moy_s": round(sum(float(x["avg_duration_s"]) for x in arr)/len(arr), 1),
            "vues_moy": round(sum(x["views"] for x in arr)/len(arr), 1)}
res = {"mesure": "averageViewPercentage (retention)", "collecte_le": "2026-09-27",
       "prospectif": {}, "retrospectif": {}}
for arm in ("A", "B"):
    arr = [v for v in rel if arm_of(v.get("hook", "")) == arm]
    st = stats(arr)
    res["retrospectif"]["variante_" + arm] = st
    lab = "A (question)" if arm == "A" else "B (constat/bascule)"
    print("  variante %-18s %s" % (lab, st if st else "aucune donnee"))
    arrp = pro[arm]
    res["prospectif"]["variante_" + arm] = stats(arrp)
if not pro["A"] and not pro["B"]:
    res["prospectif"]["statut"] = "en attente : aucune video assignee n a encore de donnees de retention"
print()
print("=== VERDICT ===")
ra, rb = res["retrospectif"].get("variante_A"), res["retrospectif"].get("variante_B")
if ra and rb:
    ecart = ra["pct_moyen"] - rb["pct_moyen"]
    seuil = 5.0
    print("  ecart de retention A - B : %+.1f points (n=%d vs %d)" % (ecart, ra["n"], rb["n"]))
    if abs(ecart) < seuil or min(ra["n"], rb["n"]) < 5:
        print("  -> NON CONCLUANT : %s. On collecte encore." % (
            "ecart inferieur au seuil de %.0f pts" % seuil if abs(ecart) < seuil else "un bras a moins de 5 videos"))
    else:
        print("  -> AVANTAGE variante %s (provisoire, retrospective)" % ("A" if ecart > 0 else "B"))
res["retrospectif"]["seuil_decision_pts"] = 5.0
res["retrospectif"]["min_videos_par_bras"] = 5
res["retrospectif"]["avertissement"] = ("Retrospectif = quasi-experience, pas une assignation aleatoire. "
                                        "Correlation avec la portee possible. A confirmer par le prospectif.")
t["results"] = res
t["metric"] = "averageViewPercentage (retention YouTube Analytics, 90 j)"
abp.write_text(json.dumps(ab, indent=2, ensure_ascii=False), encoding="utf-8")
(WS / "state/ab_retention.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
print()
print("ecrit : state/ab_retention.json + results dans ab-testing.json")
