"""Collecteur sentiment economique (Eurostat ESI) - remplace le PMI payant.

Pourquoi : le score de croissance reposait sur le PMI composite S&P Global,
source PAYANTE -> le module utilisait une valeur figee du seed (24/07), jamais
rafraichie. Le PMI etait le dernier signal non branche du module.

L ESI (Economic Sentiment Indicator) est l equivalent LIBRE : enquete mensuelle
de la Commission europeenne aupres des entreprises et menages.
Dataset Eurostat ei_bssi_m_r2, indicateur BS-ESI-I.

PIEGES VERIFIES (2026-09-26) - ne pas les re-decouvrir :
  1. geo=EA20 (zone euro 20) s ARRETE en 2025-12 : serie complete 1980-01 ->
     2025-12 (552 mois pleins), AUCUNE valeur en 2026. geo=EA19 : rien du tout.
     L agregat A JOUR est EA21 (zone euro 21) -> 2026-08. On tente EA21 puis EA20.
  2. s_adj=NSA ne renvoie AUCUNE valeur pour ces agregats : utiliser SA.
  3. Decodage JSON-stat : quand plusieurs dimensions ont une taille > 1, l index
     plat n est pas reconstituable de facon fiable a partir des listes de
     modalites. On ne decode donc QUE si geo et s_adj sont fixes (toutes les
     dimensions sauf le temps ont alors une taille de 1). C est ce qui rend
     l attribution des periodes sure.

Ajoute le 2026-09-26.
"""

import json, urllib.request, statistics
from ..models import DataPoint, CollectorResult

BASE = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        "ei_bssi_m_r2")

# Ordre de preference des agregats : EA21 (a jour) puis EA20 (repli, s arrete 2025-12).
GEOS = ["EA21", "EA20"]
S_ADJ = "SA"
MEAN_MONTHS = 84          # cycle Gave 7 ans

# indicateur -> (cle interne, libelle affiche)
TARGETS = {
    "BS-ESI-I":     ("esi_sentiment", "ESI sentiment"),
    "BS-ICI-BAL":   ("confiance_industrie", "Confiance industrie"),
    "BS-SCI-BAL":   ("confiance_services", "Confiance services"),
    "BS-CSMCI-BAL": ("confiance_consommateur", "Confiance consommateur"),
}

# Seul esi_sentiment alimente le score de croissance (cf. scoring_engine.W_MAP).


def _fetch(indic, geo):
    url = (BASE + "?indic=" + indic + "&geo=" + geo + "&s_adj=" + S_ADJ
           + "&format=JSON")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as fp:
        return json.loads(fp.read())


def _decode(raw, geo):
    """Decode JSON-stat en ne gardant que la serie demandee.

    Sur : ne fonctionne que parce que geo et s_adj sont fixes dans la requete
    (toutes les dimensions sauf le temps ont une taille de 1).
    """
    dims = raw["dimension"]; order = raw["id"]
    sizes = raw.get("size") or [len(dims[o]["category"]["index"]) for o in order]
    out = {}
    for k, v in raw.get("value", {}).items():
        pos = int(k); rem = pos; codes = []
        for o, sz in zip(order, sizes):
            idx = rem % sz; rem //= sz
            m = dims[o]["category"]["index"]
            codes.append([cd for cd, pi in m.items() if int(pi) == idx][0])
        d = dict(zip(order, codes))
        if d.get("geo") == geo and d.get("s_adj") == S_ADJ:
            out[d["time"]] = v
    return out


def _serie(indic):
    """Retourne (serie triee, geo utilise, erreurs). Chaine EA21 -> EA20."""
    errs = []
    for geo in GEOS:
        try:
            vals = _decode(_fetch(indic, geo), geo)
            if vals:
                return sorted(vals.items()), geo, errs
            errs.append("Eurostat ESI: aucune valeur pour " + geo)
        except Exception as e:
            errs.append("Eurostat ESI " + geo + ": " + str(e))
    return [], None, errs


def collect_esi():
    pts, errs = [], []
    for code, (ind, label) in TARGETS.items():
        serie, geo, e = _serie(code)
        errs += e
        if not serie:
            errs.append("Eurostat ESI: serie introuvable " + label)
            continue
        nums = [v for _, v in serie]
        cur = nums[-1]
        prev = nums[-2] if len(nums) >= 2 else None
        mean7 = (statistics.mean(nums[-MEAN_MONTHS:])
                 if len(nums) >= MEAN_MONTHS else None)
        extra = {"code": code, "geo": geo, "s_adj": S_ADJ,
                 "mean_7y": mean7, "mean_months": MEAN_MONTHS,
                 "source_tier": "official", "latest_available": True,
                 "source_note": ("Eurostat " + code + " (" + label + "), geo "
                                 + geo + ", " + S_ADJ)}
        if geo != GEOS[0]:
            extra["fallback_note"] = ("agregat " + GEOS[0]
                                      + " indisponible, repli sur " + geo)
        pts.append(DataPoint("croissance", ind, cur, prev, "index",
                             "Eurostat ESI (ei_bssi_m_r2)", serie[-1][0], extra))
    return CollectorResult(pts, errs, "Eurostat-ESI")
