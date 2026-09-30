"""Allocation Signal - PUREMENT ANALYTIQUE, aucune execution d'ordre.

Table pilotee par config.QUADRANTS : les 4 quadrants du modele Gave sont
desormais couverts (avant : seuls Q2 et Q3 etaient traites, Q1 et Q4
tombaient dans un message generique).

Regle de securite inchangee et non negociable : do_not_execute = True.
Aucun ordre n'est jamais passe, aucune position n'est modifiee.
"""
from .config import load_config


def allocation_signal(regime, ts):
    cfg = load_config() or {}
    quads = cfg.get("quadrants", {}) or {}
    tr = cfg.get("transition", {}) or {}
    thr_y = tr.get("surveillance", 26)
    thr_r = tr.get("probable", 51)

    q = regime.get("quadrant")
    base = quads.get(q) or {}

    rec = {
        "do_not_execute": True,
        "quadrant": q,
        "nom": base.get("nom", ""),
        "level": base.get("level", "yellow"),
        "alloc": base.get("alloc"),
        "favorise": base.get("favorise", []),
        "defavorise": base.get("defavorise", []),
        "message": "",
    }

    parts = []
    tscore = ts.get("score", 0)

    if regime.get("zone_indecise"):
        parts.append("Zone indecise (" + ", ".join(regime.get("neutrals", []))
                     + " dans la bande) : quadrant precedent conserve.")

    if base:
        parts.append(q + " - " + base.get("nom", "") + " : " + base.get("commentaire", ""))
        a = base.get("alloc") or {}
        if a:
            parts.append("Dosage indicatif : actions " + str(a.get("actions", "?"))
                         + "% / obligations " + str(a.get("obligations", "?"))
                         + "% / or " + str(a.get("or", "?"))
                         + "% / matieres premieres " + str(a.get("commodities", "?"))
                         + "% / cash " + str(a.get("cash", "?")) + "%.")
        if base.get("favorise"):
            parts.append("Favorise : " + ", ".join(base["favorise"]) + ".")
    else:
        parts.append("Quadrant inconnu (" + str(q) + ") : aucune recommandation produite.")

    # Modulation par le risque de changement de regime
    if tscore >= thr_r:
        rec["level"] = "red"
        parts.append("Risque de changement de regime eleve (" + str(tscore)
                     + "/100) : prudence renforcee.")
    elif tscore >= thr_y and rec["level"] == "green":
        rec["level"] = "yellow"
        parts.append("Vigilance : indice de transition " + str(tscore) + "/100.")
    else:
        parts.append("Indice de transition " + str(tscore) + "/100.")

    parts.append("ANALYTIQUE uniquement - aucune execution automatique.")
    rec["message"] = " ".join(p for p in parts if p)
    return rec
