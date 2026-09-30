"""Scoring Engine - scores par categorie + score global pondere."""
from .config import load_config

# croissance : esi_sentiment (live) OU pmi_composite (seed) - un seul emis a la
# fois, la moyenne sur les cles presentes selectionne donc le bon tout seul.
# W_MAP est desormais PILOTE PAR LA CONFIG (2026-09-26, decision d'Eric).
#
# Deux indicateurs secondaires peuvent entrer ou non dans la moyenne de leur
# categorie, via des drapeaux de config :
#   ENERGY["ttf_in_score"]     -> ajoute "ttf"      a la categorie energie
#   OECD_CLI["cli_in_score"]   -> ajoute "cli_oecd" a la categorie croissance
#
# Eric a demande de les ACTIVER tous les deux le 2026-09-26 (TTF dans l'energie,
# CLI dans la croissance). Les drapeaux restent dans la config pour que la
# decision reste reversible sans toucher au code.
#
# Note croissance : esi_sentiment et pmi_composite ne sont jamais emis en meme
# temps (l'ESI live remplace le seed PMI), donc la moyenne sur les cles PRESENTES
# selectionne le bon automatiquement. Le CLI, lui, peut cohabiter avec l'ESI :
# c'est un signal de momentum complementaire, pas un doublon.
BASE_W_MAP = {"croissance":["esi_sentiment","pmi_composite"], "inflation":["inflation_services"],
              "energie":["brent"], "bce":["taux_depot"], "geo":["geo"]}


def w_map():
    """Construit la carte categorie -> indicateurs en lisant les drapeaux de config."""
    cfg = load_config()
    m = {k: list(v) for k, v in BASE_W_MAP.items()}
    if cfg.get("oecd_cli", {}).get("cli_in_score"):
        if "cli_oecd" not in m["croissance"]:
            m["croissance"].append("cli_oecd")
    if cfg.get("energy", {}).get("ttf_in_score"):
        if "ttf" not in m["energie"]:
            m["energie"].append("ttf")
    return m

def category_scores(ind_scores):
    cfg = load_config()
    weights = cfg["scoring"]["weights"]
    cat_scores = {}
    for cat, inds in w_map().items():
        vals = [ind_scores[i]["score"] for i in inds if i in ind_scores]
        cat_scores[cat] = round(sum(vals)/len(vals)) if vals else 0
    return cat_scores, weights

def global_score(cat_scores, weights):
    numer = sum(cat_scores.get(k,0)*w for k,w in weights.items())
    total_w = sum(weights.values())
    return round(numer/total_w) if total_w else 0

def categorize(gs, cfg):
    th_g = cfg["scoring"]["global_threshold_green"]
    th_y = cfg["scoring"]["global_threshold_yellow"]
    if gs >= th_g: return "green"
    if gs >= th_y: return "yellow"
    return "red"