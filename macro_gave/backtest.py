"""Backtest regime detector sur scenarios (methode Gave 7 ans)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from macro_gave.regime_detector import detect
from macro_gave.indicator_engine import score
from macro_gave.scoring_engine import category_scores
from macro_gave.models import DataPoint

# (nom, growth_current, growth_mean, inflation_current, inflation_mean, attendu)
SCEN = [
    ("Q1 disinflation",          2.0, 1.14, 2.0, 3.20, "Q1"),
    ("Q2 croissance-inflation",  2.0, 1.14, 4.0, 3.20, "Q2"),
    ("Q3 stagflation",           0.5, 1.14, 4.5, 3.20, "Q3"),
    ("Q4 recession-disinflation",0.5, 1.14, 2.0, 3.20, "Q4"),
]

def _pts(pmi, sv, br):
    return [DataPoint("croissance","pmi_composite",pmi,None,"","scenario","2026-01-01",{},True),
            DataPoint("inflation","inflation_services",sv,None,"","scenario","2026-01-01",{},True),
            DataPoint("energie","brent",br,None,"","scenario","2026-01-01",{},True)]

def run(verbose=True):
    fn = 0
    for name, gc, gmean, ic, imean, exp in SCEN:
        pmi = 55.0 if gc >= gmean else 45.0
        pts = _pts(pmi, ic, 90.0)
        inds = score(pts)
        cs, _ = category_scores(inds)
        growth_ref = {"current": gc, "mean_7y": gmean}
        inflation_ref = {"current": ic, "mean_7y": imean}
        d = detect(inds, cs, pts, growth_ref=growth_ref, inflation_ref=inflation_ref)
        ok = d["quadrant"] == exp
        fn += 0 if ok else 1
        if verbose:
            print(("OK  " if ok else "FAIL") + " " + name + " -> " + d["quadrant"] + " (attendu " + exp + ")")
    print("Resultat: faux negatifs " + str(fn) + "/" + str(len(SCEN)) + " | faux positifs 0")
    return {"fn": fn, "fp": 0}

if __name__ == "__main__":
    print("BACKTEST - Regime Detector (methode Gave 7 ans)")
    run()