#!/usr/bin/env python3
"""export_site.py - Exporte l'etat macro vers web/pea-comparator/quadrant.json.

But : afficher le quadrant Gave sur le site public (demande d'Eric, 2026-09-26).
Le site est statique : il consomme un JSON fige, regenere a chaque run du
pipeline. Aucun appel API cote navigateur, aucune donnee personnelle.

GARDE-FOU ABSOLU : ce fichier ne contient AUCUN ordre. L'allocation est
analytique et pedagogique (do_not_execute=True en amont). Le JSON porte
"analytique": true et le site affiche un avertissement explicite.
"""
import json, sys, os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from macro_gave.run_pipeline import run
from macro_gave.config import load_config

import re as _re, calendar as _cal
from datetime import date as _date


def _periode_fin(p):
    """Fin de periode -> date. Gere YYYY-Qn / YYYY-MM-DD / YYYY-MM / YYYY."""
    t = str(p or "").strip()
    m = _re.match(r"^(\d{4})-Q([1-4])$", t)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        return _date(y, q * 3, _cal.monthrange(y, q * 3)[1])
    m = _re.match(r"^(\d{4})-(\d{2})-(\d{2})$", t)
    if m:
        return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _re.match(r"^(\d{4})-(\d{2})$", t)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return _date(y, mo, _cal.monthrange(y, mo)[1])
    m = _re.match(r"^(\d{4})$", t)
    if m:
        return _date(int(m.group(1)), 12, 31)
    return None


def _age_jours(p):
    d = _periode_fin(p)
    if not d:
        return None
    return (datetime.now(timezone.utc).date() - d).days


WS = pathlib_ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(WS, "web", "pea-comparator", "quadrant.json")


def construire():
    # alert=False : l'export ne doit JAMAIS declencher d'alerte Telegram.
    # La cadence d'alerte reste celle du pipeline planifie (lundi 08:30, 1er 09:00).
    res = run(collect=True, alert=False)
    reg, ts, alloc = res["regime"], res["ts"], res["alloc"]
    cfg = load_config()
    q = reg.get("quadrant")
    # Les axes sont exposes par regime_detector sous reg["detail"] (cle "axes"
    # n'existe pas : mon premier export sortait un dict vide). Chaque axe porte
    # valeur, moyenne_7a, periode, ecart_pp, band et classe.
    axes = reg.get("detail") or {}
    # --- Fraicheur des donnees (2026-09-27) : un quadrant peut etre juste dans sa
    # methode et faux dans son actualite. On expose l age reel de chaque axe pour
    # que personne ne lise un Q1 comme une info du jour.
    for _n, _ax in axes.items():
        if isinstance(_ax, dict):
            _ax["age_jours"] = _age_jours(_ax.get("periode"))
    _ages = {k: v.get("age_jours") for k, v in axes.items()
             if isinstance(v, dict) and v.get("age_jours") is not None}
    _age_max = max(_ages.values()) if _ages else None
    _SEUIL = 180
    _perime = bool(_age_max is not None and _age_max > _SEUIL)
    if _age_max is None:
        _msg = "Age des donnees indisponible."
    elif _perime:
        _msg = ("Donnee la plus ancienne : J+%d (> %d j). Le regime affiche peut ne plus "
                "correspondre a la conjoncture actuelle : a confirmer a la prochaine "
                "publication des comptes nationaux / de l IPCH." % (_age_max, _SEUIL))
    else:
        _msg = "Donnee la plus ancienne : J+%d." % _age_max
    fraicheur = {
        "age_max_jours": _age_max,
        "seuil_jours": _SEUIL,
        "perime": _perime,
        "par_axe": _ages,
        "message": _msg,
    }
    # Les quadrants : nom + allocation, depuis la config (source unique de verite)
    quadrants = {}
    for code, d in (cfg.get("quadrants") or {}).items():
        quadrants[code] = {
            "nom": d.get("nom"), "croissance": d.get("croissance"),
            "inflation": d.get("inflation"), "level": d.get("level"),
            "favorise": d.get("favorise"), "commentaire": d.get("commentaire"),
        }
    return {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "quadrant": q,
        "nom": (cfg.get("quadrants", {}).get(q) or {}).get("nom"),
        "confidence": reg.get("confidence"),
        "zone_indecise": bool(reg.get("zone_indecise")),
        "bande": reg.get("band"),
        "axes": axes,
        "fraicheur": fraicheur,
        "transition": ts.get("score"),
        "transition_label": ts.get("label") or ts.get("niveau"),
        "global": res["gs"],
        "scores": res["cat"],
        "allocation": {"level": alloc.get("level"), "message": alloc.get("message")},
        "quadrants": quadrants,
        "analytique": True,
        "methode": "Gavekal : quadrant croissance/inflation vs moyenne de cycle 7 ans",
        "avertissement": ("Indicateur analytique et pedagogique. Aucun ordre, "
                          "aucune execution automatique. Ne constitue pas un conseil "
                          "en investissement."),
    }


if __name__ == "__main__":
    d = construire()
    with open(DEST, "w", encoding="utf-8") as fp:
        json.dump(d, fp, ensure_ascii=False, indent=1)
    print("ecrit : " + DEST)
    print(json.dumps(d, ensure_ascii=False, indent=1)[:1400])
