"""Report Generator - rapport mensuel texte."""
from datetime import datetime

def build_report(regime, cat_scores, inds, ts, alloc, unavailable):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    r = []
    r.append("===== MACRO REGIME REPORT =====")
    r.append("Date: " + now)
    _lab = (regime.get("label") or "").strip()
    r.append("Regime actuel: " + regime["quadrant"] + ("  \u2014  " + _lab if _lab else "")
             + "   Confiance: " + str(regime["confidence"]) + "/100")
    r.append("")
    r.append("Transition Q2->Q3: " + str(ts["score"]) + "/100 - " + ts["label"])
    r.append("")
    det = regime.get("detail") or {}
    if det:
        band = regime.get("band") or {}
        r.append("QUADRANT (methode Gave, cycle 7 ans, zone neutre +-"
                 + str(band.get("croissance", "?")) + "pp / +-"
                 + str(band.get("inflation", "?")) + "pp)")
        for name in ("croissance", "inflation"):
            d = det.get(name) or {}
            if d.get("valeur") is not None:
                r.append("  " + name.capitalize() + ": " + str(d.get("valeur"))
                         + " vs moyenne 7 ans " + str(d.get("moyenne_7a"))
                         + "  (ecart " + str(d.get("ecart_pp")) + " pp)  -> "
                         + str(d.get("classe", "?")).upper())
            else:
                r.append("  " + name.capitalize() + ": donnee indisponible")
        if regime.get("zone_indecise"):
            r.append("  ZONE INDECISE : " + ", ".join(regime.get("neutrals", []))
                     + " dans la bande -> quadrant precedent conserve"
                     + (" (" + regime["quadrant"] + ")" if regime.get("quadrant_provisoire") else ""))
        r.append("")
    for cat in ("croissance","inflation","energie","bce","geo"):
        v = cat_scores.get(cat)
        icon = {0:"NA",1:"?"}.get(v is None and 0 or 1, "?")
        r.append("- " + cat.capitalize() + " : score " + str(v) if v is not None else "- " + cat.capitalize() + " : DATA UNAVAILABLE")
    r.append("")
    for k, d in inds.items():
        tag = {"green":"OK","yellow":"VIG","red":"ALERT","grey":"NA"}[d["status"]]
        r.append("  " + tag + " " + d["label"] + ": " + str(d["value"]))
    r.append("")
    r.append("ALLOCATION (analytique, jamais executee):")
    r.append("  [" + alloc["level"].upper() + "] " + alloc["message"])
    r.append("")
    if unavailable:
        r.append("Donnees indisponibles: " + ", ".join(unavailable))
        r.append("(confiance diminuee : " + str(regime["confidence"]) + "/100)")
    r.append("")
    if not inds:
        concl = ("Donnees insuffisantes : aucun indicateur n est disponible, "
                 "aucune conclusion de regime ne peut etre tiree. Le quadrant "
                 + regime.get("quadrant", "?") + " provient de la classification "
                 "de cycle 7 ans (Eurostat), pas des scores d indicateurs.")
    else:
        concl = ("Le regime est " + regime["quadrant"] + " avec un indice de transition de " + str(ts["score"]) + "/100. ")
        if regime.get("zone_indecise"):
            concl += ("Ecart a la moyenne de cycle dans la zone neutre (+-"
                      + str((regime.get("band") or {}).get("croissance", "?"))
                      + "pp) : regime CONSIDERE COMME STABLE, quadrant precedent conserve. ")
        concl += ("La croissance tient et l inflation reste maitrisee." if ts["score"] <= 25 else "Des signaux de vigilance apparaissent : surveiller croissance (ESI) et inflation services." if ts["score"] <= 50 else "Les signaux convergent vers une transition vers le Quadrant 3 : renforcer les poches defensives (analyse uniquement).")
    r.append("CONCLUSION: " + concl)
    return "\n".join(r)