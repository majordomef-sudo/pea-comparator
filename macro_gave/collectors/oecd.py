"""Collecteur OCDE - CLI (Composite Leading Indicator) - ajoute le 2026-09-26.

Ce que c est : l indicateur composite avance de l OCDE, construit par l OCDE
elle-meme a partir des series nationales. Ce n est donc PAS un miroir d Eurostat
(contrairement a DBnomics ou a l ICP de la BCE) : c est une compilation
independante. C est exactement ce qui manquait au module pour la croissance.

CE QUI A ETE DEBLOQUE (3 obstacles reels, tous documentes) :
1. HTTP 406 : sur les endpoints de STRUCTURE, le parametre format accepte
   structure | xml-structure-3.0.0 | sdmx-3.0 | json-structure-2.0.0. Pas jsondata.
2. HTTP 404 : la cle de donnees exige le NUMERO DE VERSION du dataflow. Pour
   DSD_KEI@DF_KEI c est 4.0 (et non 1.0) : version=4.0 en dur ci-dessous.
3. Parsing : le schema repond sous data.dataSets / data.structure, PAS a la
   racine dataSets/structure. Mon premier parseur lisait la racine et concluait
   a tort "aucune donnee" alors que la reponse faisait 7 Ko de series valides.

PERIMETRE : l OCDE ne publie PAS de CLI pour la zone euro (EA20, EA21, E4M, G4E
sont tous en 404). Le CLI n existe qu au niveau pays. On construit donc un PROXY
"quatre grands pays de la zone euro" (DEU, FRA, ITA, ESP) par moyenne simple.
C est une construction NOSSOIRE : elle est etiquetee comme telle partout
(extra.proxy=True) et ne doit jamais etre presentee comme un agregat OCDE.

ECONOMIE DE REQUETES : l union SDMX "+" permet d obtenir les 4 pays en UNE seule
requete (DEU+FRA+ITA+ESP.M.LI.....). Lecon de la journee : ne pas sonder sans
throttle, lire la structure plutot que deviner les cles.

CALIBRAGE : le CLI est un indice d AMPLITUDE ajustee, dont le 100 est la
tendance de long terme PAR CONSTRUCTION. Un neutre a 100 fixe est donc
legitime ici - contrairement a l ESI, qui est un solde d opinion qui derive et
pour lequel j ai du passer en cycle_relative.

Source : https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,4.0/
"""

import json, urllib.request
from ..models import DataPoint, CollectorResult
from ..config import load_config

CLE = "DEU+FRA+ITA+ESP.M.LI....."
URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,4.0/"
       + CLE + "?format=jsondata&lastNObservations=2")
PAYS = ["DEU", "FRA", "ITA", "ESP"]
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.sdmx.data+json;version=1.0.0"}


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as fp:
        return json.loads(fp.read())


def _lire_serie(d, k):
    dims = d["data"]["structure"]["dimensions"]["series"]
    tvals = [v.get("id") for v in
             d["data"]["structure"]["dimensions"]["observation"][0]["values"]]
    obs = d["data"]["dataSets"][0]["series"][k].get("observations", {})
    # PIEGE MAJEUR (bug corrige le 2026-09-26) : l OCDE renvoie la dimension
    # temps du PLUS RECENT au PLUS ANCIEN. Trier par index croissant donne donc
    # une liste en ordre DECROISSANT, et pts[-1] pointe la periode la plus
    # vieille. On trie explicitement sur la periode (ISO AAAA-MM, ordre
    # lexicographique = ordre chronologique).
    pts = [(tvals[int(x)], obs[x][0]) for x in obs]
    pts.sort(key=lambda t: t[0])
    return pts


def collect_cli():
    """CLI : 4 grands pays de la zone euro en une requete -> moyennes courante et precedente."""
    errs = []
    try:
        d = _get(URL)
    except Exception as e:
        return CollectorResult([], ["OCDE CLI: " + type(e).__name__ + " " + str(e)[:90]], "CLI/OCDE")

    sets = (d.get("data") or {}).get("dataSets") or []
    if not sets or not sets[0].get("series"):
        return CollectorResult([], ["OCDE CLI: aucune serie retournee"], "CLI/OCDE")

    dims = d["data"]["structure"]["dimensions"]["series"]
    par_pays, periodes = {}, set()
    for k in sets[0]["series"]:
        ref = dims[0]["values"][int(k.split(":")[0])].get("id")
        pts = _lire_serie(d, k)
        if ref in PAYS and pts:
            par_pays[ref] = pts
            periodes |= {p for p, _ in pts}

    if not par_pays:
        return CollectorResult([], ["OCDE CLI: aucun des 4 pays attendus"], "CLI/OCDE")

    manquants = [p for p in PAYS if p not in par_pays]
    if manquants:
        errs.append("OCDE CLI: pays manquants " + ",".join(manquants))

    # periode de reference = la plus recente disponible
    per = max(periodes)
    vals = {p: pts[-1][1] for p, pts in par_pays.items() if pts[-1][0] == per}
    prec = {}
    for p, pts in par_pays.items():
        for q, v in reversed(pts[:-1]):
            if q != per:
                prec[p] = v
                break
    if not vals:
        return CollectorResult([], ["OCDE CLI: aucune periode commune aux 4 pays"],
                               "CLI/OCDE")
    moy = round(sum(vals.values()) / len(vals), 3)
    moy_p = round(sum(prec.values()) / len(prec), 3) if prec else None

    cfg = load_config()["oecd_cli"]
    k = cfg.get("slope", 20.0)
    span = cfg.get("span_pts", 3.0)
    ecart = moy - cfg.get("neutral", 100.0)
    score = round(max(0.0, min(100.0, 50.0 + max(-span, min(span, ecart)) * k)))

    return CollectorResult([DataPoint(
        "croissance", "cli_oecd", moy, moy_p, "indice",
        "OCDE KEI (CLI, proxy 4 grands pays)", per,
        {"score_hint": score, "ecart_tendance": round(ecart, 3),
         "pays": {p: round(v, 3) for p, v in sorted(vals.items())},
         "proxy": True,
         "proxy_note": ("moyenne simple DEU/FRA/ITA/ESP - l OCDE ne publie pas "
                        "de CLI zone euro"),
         "source_tier": "official", "latest_available": True,
         "source_note": "OCDE SDMX, DSD_KEI@DF_KEI v4.0, MEASURE=LI"})], errs, "CLI/OCDE")
