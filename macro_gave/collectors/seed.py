"seed data source - data/seed_reference.json (Gave)."
import json, pathlib
from ..models import DataPoint, CollectorResult

SEED = pathlib.Path(__file__).parent.parent / "data" / "seed_reference.json"

def load_seed():
    if SEED.exists():
        return json.loads(SEED.read_text())
    return {}

CATS = []
META = {"croissance":["pmi_composite","pmi_manufacturier","pmi_services"],
        "inflation":["inflation_globale","inflation_sous_jacente","inflation_services","inflation_energie"],
        "energie":["brent","ttf"]}

def _build(sd):
    for cat, keys in META.items():
        for k in keys:
            item = sd.get(cat, {}).get(k)
            if item:
                CATS.append(DataPoint(cat, k, item.get("value"), item.get("previous"),
                    item.get("unit",""), "REFGEN:"+item.get("source","manual"), item.get("published",""),
                    {"reference":True}))
    for k in ("taux_depot","taux_refinancement"):
        it = sd.get("bce", {}).get(k)
        if it:
            CATS.append(DataPoint("bce", k, it.get("value"), None, it.get("unit",""), "REFGEN:BCE", it.get("published",""), {"reference":True}))
    g = sd.get("geo", {})
    CATS.append(DataPoint("geo", "statut", 0.0 if g.get("statut")=="stable" else 1.0, None, "", "REFGEN:veille", g.get("published",""), {"statut":g.get("statut","stable"),"events":g.get("events",[]),"reference":True}))

def collect_seed():
    sd = load_seed()
    if not sd:
        return CollectorResult([], ["seed absent"], "seed")
    _build(sd)
    return CollectorResult(CATS, [], "seed_reference")