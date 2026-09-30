"""Transition Detector - score 0-100 risque de changement de regime."""
from .config import load_config

def transition_score(inds):
    cfg = load_config()["transition"]
    s = 0
    # Croissance : ESI live si present, sinon PMI seed.
    pmi = inds.get("esi_sentiment") or inds.get("pmi_composite")
    if pmi:
        s += 30 if pmi["score"] < 45 else (15 if pmi["score"] < 55 else 0)
    isv = inds.get("inflation_services")
    if isv:
        s += 25 if isv["score"] < 50 else 0
    br = inds.get("brent")
    if br:
        s += 15 if br["score"] < 50 else 0
    dep = inds.get("taux_depot")
    if dep:
        s += 15 if dep["score"] < 60 else 0
    g = inds.get("geo")
    if g:
        s += 15 if g["score"] < 45 else 0
    s = min(100, s)
    if s >= cfg["high"]: lab = "Changement fortement probable"
    elif s >= cfg["probable"]: lab = "Transition probable"
    elif s >= cfg["surveillance"]: lab = "Surveillance"
    else: lab = "Regime stable"
    return {"score": s, "label": lab}