#!/usr/bin/env python3
"""run_pipeline.py - Pipeline macro Gave de bout en bout."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # cwd=workspace
from macro_gave.collector import run_collect_all
from macro_gave.validator import validate
from macro_gave.indicator_engine import score
from macro_gave.scoring_engine import category_scores, global_score, categorize
from macro_gave.regime_detector import detect
from macro_gave.transition_detector import transition_score
from macro_gave.allocation_signal import allocation_signal
from macro_gave.report_generator import build_report
from macro_gave.telegram_alert import send_alert, should_alert
from macro_gave import db
import json

def run(collect=True, verbose=True, alert=True):
    """alert=False : on collecte et on calcule, mais on n'ENVOIE PAS d'alerte
    Telegram et on n'enregistre pas de nouvelle ligne d'alerte.

    Ajoute le 2026-09-26 pour l'export du site (web/pea-comparator/quadrant.json).
    Raison : l'export tourne plus souvent que le pipeline officiel ; sans ce
    drapeau il aurait multiplie les alertes Telegram et modifie la semantique
    d'anti-spam validee par Eric. On ne touche donc PAS a la cadence d'alerte :
    seul le pipeline planifie alerte, l'export se contente de lire l'etat.
    """
    db.init_db()
    if collect:
        pts = run_collect_all(use_seed=True, use_live=True)
    else:
        pts = []
    validated = validate(pts) if pts else []
    # points non disponibles
    unavail = [p.indicator for p in validated if not p.available]
    # marquer les valides
    inds = score(validated)
    cat_scores, weights = category_scores(inds)
    gs = global_score(cat_scores, weights)
    # Quadrant precedent : conserve si l'ecart a la moyenne tombe dans la zone neutre.
    _prev = db.recent_snapshots(1)
    prev_q = _prev[0]["period"] if _prev else None
    regime = detect(inds, cat_scores, validated, prev_quadrant=prev_q)
    ts = transition_score(inds)
    alloc = allocation_signal(regime, ts)
    report = build_report(regime, cat_scores, inds, ts, alloc, unavail)
    # snapshot en base
    db.save_snapshot(regime["quadrant"], regime, gs, ts["score"], alloc["message"])
    # alertes si changement significatif
    snaps = db.recent_snapshots(2)
    prev = None
    if len(snaps) >= 2:
        try: prev = json.loads(snaps[1]["regimes"])
        except Exception: prev = None
    alert_red = alloc["level"] == "red"
    new_state = {"quadrant": regime["quadrant"], "transition": ts["score"], "alert_red": alert_red}
    if alert and should_alert(prev, new_state):
        db.add_alert(alloc["level"], alloc["message"], regime["confidence"])
        send_alert(alloc["message"], alloc["level"].upper())
    return {"report": report, "regime": regime, "gs": gs, "ts": ts, "inds": inds, "cat": cat_scores, "alloc": alloc, "unavail": unavail}

if __name__ == "__main__":
    res = run()
    print(res["report"])
    print("");
    print("Scores: " + json.dumps(res["cat"], ensure_ascii=False))
    print("Global: " + str(res["gs"]) + "/100 | Transition: " + str(res["ts"]["score"]) + "/100")
    print("Regime: " + res["regime"]["quadrant"] + " (confiance " + str(res["regime"]["confidence"]) + "/100)")
    print("Allocation: [" + res["alloc"]["level"] + "] " + res["alloc"]["message"])