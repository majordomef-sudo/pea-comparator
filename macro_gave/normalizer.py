"Normalizer: calcule variations/tendances sur 1, 3, 6 mois (recent history en DB)."
from . import db

def trends(category, indicator):
    hist = db.history(category, indicator, limit=7)
    if len(hist) < 2:
        return {"mom":0, "m3":0, "m6":0}
    vals = [h["value"] for h in hist if h.get("value") is not None]
    if len(vals) < 2:
        return {"mom":0,"m3":0,"m6":0}
    def chg(a, b):
        if a is None or b is None or b==0:
            return 0
        return round((a-b)/b*100.0, 2) if isinstance(a,(int,float)) and isinstance(b,(int,float)) else 0
    return {"mom": chg(vals[0], vals[1]), "m3": chg(vals[0], vals[2]) if len(vals)>2 else None, "m6": chg(vals[0], vals[5]) if len(vals)>5 else None}
