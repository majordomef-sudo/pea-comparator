"""Regime Detector - classe le quadrant (Q1-Q4) selon la methode Gave.
Compare croissance et inflation a LEUR TENDANCE DE CYCLE 7 ANS, pas a des seuils absolus.
En prod, les references sont requetees en live. En backtest, on les injecte."""
from . import gave_ref
from .config import load_config

# Quadrant -> (cote croissance, cote inflation)
PREV_SIDES = {"Q1": ("haut", "bas"), "Q2": ("haut", "haut"),
              "Q3": ("bas", "haut"), "Q4": ("bas", "bas")}

def _classify_growth():
    g = gave_ref.growth_refs()
    if not g: return "unknown", None
    return gave_ref.classify(g["current"], g["mean_7y"]), g

def _classify_inflation():
    i = gave_ref.inflation_refs()
    if not i: return "unknown", None
    return gave_ref.classify(i["current"], i["mean_7y"]), i

def detect(ind_scores, cat_scores, points=None, growth_ref=None, inflation_ref=None,
           prev_quadrant=None):
    """growth_ref/inflation_ref: dicts optionnels {current, mean_7y} pour backtest.
    None en prod -> requete API live."""
    # Zone neutre (dead band) : evite qu'un bruit de +/- 0,2 pp fasse basculer
    # le regime. Decision d'Eric, 2026-09-26.
    _cfg = load_config() or {}
    qcfg = _cfg.get("quadrant", {})
    gband = float(qcfg.get("growth_band_pp", 0.2))
    iband = float(qcfg.get("inflation_band_pp", 0.2))

    if growth_ref is not None:
        gd = growth_ref
    else:
        gd = gave_ref.growth_refs()
    if inflation_ref is not None:
        idt = inflation_ref
    else:
        idt = gave_ref.inflation_refs()

    gfl = gave_ref.classify(gd["current"], gd["mean_7y"], gband) if gd else "unknown"
    ifl = gave_ref.classify(idt["current"], idt["mean_7y"], iband) if idt else "unknown"
    gfl = gfl if gfl else "unknown"
    ifl = ifl if ifl else "unknown"

    def _strict(d, f):
        """Repli strict (>=) quand la dimension est neutre et sans historique."""
        if f in ("haut", "bas"):
            return f
        if not d or d.get("current") is None or d.get("mean_7y") is None:
            return "haut"
        return "haut" if d["current"] >= d["mean_7y"] else "bas"

    prev_g, prev_i = PREV_SIDES.get(prev_quadrant, (None, None))
    g_eff = gfl if gfl in ("haut", "bas") else (prev_g or _strict(gd, gfl))
    i_eff = ifl if ifl in ("haut", "bas") else (prev_i or _strict(idt, ifl))

    neutrals = [n for n, f in (("croissance", gfl), ("inflation", ifl)) if f == "neutre"]
    zone_indecise = bool(neutrals)

    if g_eff == "haut" and i_eff == "haut":    q = "Q2"
    elif g_eff == "haut" and i_eff == "bas":   q = "Q1"
    elif g_eff == "bas" and i_eff == "haut":   q = "Q3"
    else:                                      q = "Q4"

    vals = [v.get("score",0) for v in ind_scores.values()]
    conf = round(sum(vals)/len(vals)) if vals else 0

    def _detail(d, f, band):
        if not d:
            return {"classe": f, "band": band}
        return {"valeur": d.get("current"), "moyenne_7a": round(d["mean_7y"], 3),
                "periode": d.get("date"),
                "ecart_pp": round(d["current"] - d["mean_7y"], 3),
                "band": band, "classe": f}

    qlabel = ((_cfg.get("quadrants") or {}).get(q) or {}).get("nom", "")
    return {"quadrant": q, "confidence": conf, "label": qlabel,
            "growth_ok": g_eff == "haut", "inf_high": i_eff == "haut",
            "method": "gave-7y+band",
            "band": {"croissance": gband, "inflation": iband},
            "classe_brute": {"croissance": gfl, "inflation": ifl},
            "zone_indecise": zone_indecise, "neutrals": neutrals,
            "quadrant_provisoire": zone_indecise,
            "detail": {"croissance": _detail(gd, gfl, gband),
                       "inflation": _detail(idt, ifl, iband)}}
