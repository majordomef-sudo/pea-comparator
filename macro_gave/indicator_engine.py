"""Indicator Engine - score 0-100 et statut par indicateur."""
from .config import load_config

def _status(s):
    if s >= 70: return "green"
    if s >= 45: return "yellow"
    return "red"

def score(pts):
    cfg = load_config()
    out = {}
    by_ind = {(p.category, p.indicator): p for p in pts}

    # Croissance -> ESI Eurostat (live, libre) en priorite, sinon PMI (seed, payant).
    # Un seul des deux est emis : la moyenne de la categorie croissance
    # (cf. scoring_engine.W_MAP) selectionne donc toujours le bon.
    esi = by_ind.get(("croissance","esi_sentiment"))
    pmi = by_ind.get(("croissance","pmi_composite"))
    sent = cfg.get("sentiment", {})
    if esi and esi.available and esi.value is not None:
        v = esi.value
        mean7 = esi.extra.get("mean_7y")
        if sent.get("mode") == "cycle_relative" and mean7 is not None:
            # Compare a la tendance de cycle (comme les axes du quadrant) :
            # ecart 0 -> 50 ; ecart +/-span_pts -> 100 / 0.
            span = sent.get("span_pts", 3.0) or 3.0
            s = int(round(min(100, max(0, 50 + ((v - mean7) / span) * 50))))
        else:
            neu = sent.get("neutral", 100.0)
            slope = sent.get("slope", 5.0)
            ylow = sent.get("yellow_low", 97.0)
            if v >= neu:
                s = int(round(min(100, 50 + (v-neu)*slope)))
            elif v >= ylow:
                s = 40
            else:
                s = int(round(min(15, max(5, 50 + (v-neu)*slope))))
        out["esi_sentiment"] = {"score":s,"status":_status(s),"value":v,
                                "label":"ESI sentiment","source":esi.source,
                                "cycle_mean_7y":mean7}
    elif pmi and pmi.available and pmi.value is not None:
        v = pmi.value
        if v > 50: s = min(100, 50 + (v-50)*20)
        elif v >= 48: s = 40
        else: s = min(15, max(5, v-40))
        out["pmi_composite"] = {"score":s,"status":_status(s),"value":v,
                                "label":"PMI (seed, payant)","source":pmi.source}

    # Inflation services (cle du signal Q3)
    isv = by_ind.get(("inflation","inflation_services"))
    if isv and isv.available and isv.value is not None:
        v = isv.value
        if v < 3.5: s = 90
        elif v < 4.5: s = 55
        else: s = 20
        out["inflation_services"] = {"score":s,"status":_status(s),"value":v,"label":"Inflation services"}

    # Energie (Brent)
    br = by_ind.get(("energie","brent"))
    if br and br.available and br.value is not None:
        v = br.value
        if v > 110: s = 15
        elif v > 95: s = 45
        else: s = 90
        out["brent"] = {"score":s,"status":_status(s),"value":v,"label":"Brent"}

    # CLI OCDE (indicateur composite avance) - ajoute le 2026-09-26.
    # Affiche et score, mais HORS moyenne de categorie tant que
    # config OECD_CLI["cli_in_score"] est False.
    cl = by_ind.get(("croissance","cli_oecd"))
    if cl and cl.available and cl.value is not None:
        s = cl.extra.get("score_hint")
        if s is None:
            e = cl.value - load_config()["oecd_cli"].get("neutral", 100.0)
            s = round(max(0.0, min(100.0, 50.0 + e * 20.0)))
        out["cli_oecd"] = {"score":s,"status":_status(s),"value":cl.value,
                           "label":"CLI OCDE (proxy 4 grands)"}

    # TTF (gaz europeen) - ajoute le 2026-09-26, source Yahoo TTF=F.
    # Score de NIVEAU calibre sur l'histoire du TTF (voir config ENERGY) :
    # > ttf_high -> tension ; > ttf_mid -> vigilance ; sinon detendu.
    tf = by_ind.get(("energie","ttf"))
    if tf and tf.available and tf.value is not None:
        cfg_e = load_config()["energy"]
        v = tf.value
        if v > cfg_e.get("ttf_high", 70.0): s = 15
        elif v > cfg_e.get("ttf_mid", 50.0): s = 45
        else: s = 90
        out["ttf"] = {"score":s,"status":_status(s),"value":v,"label":"TTF gaz"}

    # BCE: taux depot bas = OK
    dep = by_ind.get(("bce","taux_depot"))
    if dep and dep.available and dep.value is not None:
        v = dep.value
        if v <= 2.5: s = 90
        elif v <= 3.5: s = 60
        else: s = 25
        out["taux_depot"] = {"score":s,"status":_status(s),"value":v,"label":"Taux depot BCE"}

    # Geo: statut stable = vert
    g = by_ind.get(("geo","statut"))
    if g and g.available:
        st = g.extra.get("statut","stable")
        s = 90 if st == "stable" else 25
        out["geo"] = {"score":s,"status":_status(s),"value":(0 if st=="stable" else 1),"label":"Geo: "+st}

    return out