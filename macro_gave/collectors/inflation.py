"""Collecteur inflation (IPCH zone euro) - chaine Eurostat -> BCE ICP.

Source primaire : Eurostat prc_hicp_manr, geo EA20, unit RCH_A (glissement annuel).
Source de repli  : BCE Data Portal, dataflow ICP, cle M.U2.N.<item>.4.ANR.

Pourquoi un repli : les deux axes du quadrant venaient d Eurostat SEUL -> un seul
point de defaillance pour tout le regime. La BCE republie l IPCH (produit
Eurostat) : c est donc un MIROIR, qui apporte de la DISPONIBILITE en cas de panne
d API, PAS de la validation independante. Une revision Eurostat deplacerait les
deux series. A ne pas confondre dans le rapport.

NUANCE MESUREE (2026-09-26) : le miroir n est pas numeriquement identique.
Sur 2025-12, Eurostat donne 2,0 % et la BCE 1,9 % (poste global). Ecart de 0,1 pp,
vraisemblablement lie a la zone de reference (EA20 vs U2) ou a un millesime
different. C est une raison de plus de NE PAS presenter le repli comme une
contre-verification.

Correspondance des postes :
   global            Eurostat CP00           <-> BCE 000000 (Overall index)
   sous-jacente      Eurostat TOT_X_NRG_FOOD <-> BCE XEF000 (excl. energy and food)
   services          Eurostat SERV           <-> BCE SERV00 (Services)
   energie           Eurostat NRG            <-> BCE NRGY00 (Energy)

Ajoute le 2026-09-26.
"""

import json, urllib.request
from ..models import DataPoint, CollectorResult

# ECOICOP v2 (prc_hicp_minr) : dataset vivant, dimension coicop18.
# L'ancien prc_hicp_manr (coicop) est FIGE au 2025-12 depuis le 04/02/2026.
EUROSTAT_BASE = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/"
                 "data/prc_hicp_minr?geo=EA20&unit=RCH_A&coicop18=")
EUROSTAT_BASE_V1 = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/"
                    "data/prc_hicp_manr?geo=EA20&unit=RCH_A&coicop=")
ECB_BASE = ("https://data-api.ecb.europa.eu/service/data/ICP/"
            "M.U2.N.{item}.4.ANR?format=jsondata&lastNObservations=2")
UA = {"User-Agent": "Mozilla/5.0"}

# cle interne -> (code Eurostat coicop, code BCE ICP_ITEM, libelle)
# cle interne -> (code ECOICOP v2, code v1 de repli, code BCE ICP, libelle)
# Correspondance v2 <-> v1 : TOTAL<->CP00, TOT_X_NRG_FOOD identique,
# SERV<->SERV, NRG<->NRG.
TARGETS = {
    "inflation_globale":       ("TOTAL",           "CP00",           "000000", "inflation globale"),
    "inflation_sous_jacente":  ("TOT_X_NRG_FOOD",  "TOT_X_NRG_FOOD", "XEF000", "inflation sous-jacente"),
    "inflation_services":      ("SERV",            "SERV",           "SERV00", "inflation services"),
    "inflation_energie":       ("NRG",             "NRG",            "NRGY00", "inflation energie"),
}


def _get_json(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as fp:
        return json.loads(fp.read())


def _decode_eurostat(raw, geo="EA20"):
    """Decode JSON-stat. Fiable ici car geo/unit/coicop sont fixes."""
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
        if d.get("geo") == geo:
            out[d["time"]] = v
    return out


def _from_eurostat(code_v2, code_v1=None):
    """ECOICOP v2 d'abord ; repli v1 seulement si la v2 ne donne rien d'au moins 2026."""
    last_err = None
    try:
        raw = _get_json(EUROSTAT_BASE + code_v2 + "&format=JSON")
        vals = _decode_eurostat(raw)
        if vals and max(vals.keys()) >= "2026-01":
            t = sorted(vals.keys())
            return vals[t[-1]], t[-1], (vals[t[-2]] if len(t) >= 2 else None)
        last_err = ValueError("v2 sans donnee 2026 (dataset fige ?)")
    except Exception as e:
        last_err = e
    if code_v1:
        raw = _get_json(EUROSTAT_BASE_V1 + code_v1 + "&format=JSON")
        vals = _decode_eurostat(raw)
        if not vals:
            raise ValueError("aucune valeur Eurostat")
        t = sorted(vals.keys())
        return vals[t[-1]], t[-1], (vals[t[-2]] if len(t) >= 2 else None)
    raise last_err or ValueError("aucune valeur Eurostat")


def _from_ecb(item):
    """BCE ICP : reponse en serie unique -> observations indexees 0..n-1."""
    raw = _get_json(ECB_BASE.format(item=item))
    times = [v.get("id") for v in
             raw["structure"]["dimensions"]["observation"][0]["values"]]
    series = list(raw["dataSets"][0]["series"].values())[0]["observations"]
    pts = []
    for k in sorted(series, key=lambda x: int(x)):
        pts.append((times[int(k)], series[k][0]))
    if not pts:
        raise ValueError("aucune valeur BCE")
    # ATTENTION : pts contient des tuples (periode, valeur) -> ne PAS ecrire
    # "cur, pub = pts[-1]", ce qui inverserait la valeur et la date (bug corrige
    # le 2026-09-26 : value valait "2025-12" et published_date valait 1.9).
    pub, cur = pts[-1]
    prev = pts[-2][1] if len(pts) >= 2 else None
    return cur, pub, prev


def collect():
    pts, errs = [], []
    for ind, (code_v2, code_v1, icp_item, label) in TARGETS.items():
        extra = {"code": code_v2, "source_tier": "official",
                 "dataset": "prc_hicp_minr (ECOICOP v2)",
                 "latest_available": True}
        try:
            cur, pub, prev = _from_eurostat(code_v2, code_v1)
            pts.append(DataPoint("inflation", ind, cur, prev, "%", "Eurostat API",
                                 pub, extra))
            continue
        except Exception as e:
            errs.append("Eurostat " + label + ": " + str(e)[:70])
        # --- repli BCE ---
        try:
            cur, pub, prev = _from_ecb(icp_item)
            extra["code"] = icp_item
            extra["fallback_note"] = "repli BCE ICP (Eurostat indisponible)"
            extra["source_note"] = ("BCE Data Portal ICP, cle M.U2.N."
                                    + icp_item + ".4.ANR")
            pts.append(DataPoint("inflation", ind, cur, prev, "%",
                                 "BCE Data Portal (ICP)", pub, extra))
            errs.append("BCE " + label + ": repli utilise")
        except Exception as e:
            errs.append("BCE " + label + ": " + str(e)[:70])
    return CollectorResult(pts, errs, "Eurostat+BCE")
