"""Test scenario Q3 (stagflation) - prouve la detection de transition."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from macro_gave.indicator_engine import score
from macro_gave.scoring_engine import category_scores
from macro_gave.regime_detector import detect
from macro_gave.transition_detector import transition_score
from macro_gave.allocation_signal import allocation_signal
from macro_gave.models import DataPoint

pts = [
 DataPoint("croissance","pmi_composite",44.5,None,"","scenario","2026-01-01",{},True),
 DataPoint("inflation","inflation_services",4.7,None,"","scenario","2026-01-01",{},True),
 DataPoint("inflation","inflation_energie",12.0,None,"","scenario","2026-01-01",{},True),
 DataPoint("energie","brent",118.0,None,"","scenario","2026-01-01",{},True),
 DataPoint("bce","taux_depot",3.0,None,"","scenario","2026-01-01",{},True),
 DataPoint("geo","statut",1.0,None,"","scenario","2026-01-01",{"statut":"escalade"},True),
]
inds = score(pts)
cs,_ = category_scores(inds)
d = detect(inds, cs, pts)
ts = transition_score(inds)
alloc = allocation_signal(d, ts)
print("Quadrant detecte:", d["quadrant"])
print("Transition:", ts)
print("Allocation:", alloc["level"], "|", alloc["message"])
assert d["quadrant"] == "Q3", "echec detection Q3"
assert ts["score"] >= 50, "transition score trop faible"
print("TEST Q3: PASS")