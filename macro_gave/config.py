"""Configuration centralisee du pipeline macro Gave. Tous les seuils configurable ici."""
import os, json, copy
from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
DB_PATH = DATA_DIR / "macro_gave.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Table complete des 4 quadrants (modele Gave).
# Croissance / inflation sont mesurees par rapport a leur TENDANCE DE CYCLE 7 ANS.
# "alloc" = dosage INDICATIF (analytique, jamais execute). Somme = 100.
QUADRANTS = {
    "Q1": {
        "croissance": "haute", "inflation": "basse",
        "nom": "Point d'equilibre (Goldilocks)",
        "level": "green",
        "favorise": ["actions", "obligations"],
        "defavorise": ["or", "matieres premieres", "cash"],
        "alloc": {"actions": 75, "obligations": 15, "or": 5,
                  "commodities": 2, "cash": 3},
        "commentaire": ("Croissance au-dessus de sa tendance, inflation contenue. "
                        "Actions et obligations portent le portefeuille : c'est le regime "
                        "ou le risque est le mieux paye. Laisser composer."),
    },
    "Q2": {
        "croissance": "haute", "inflation": "haute",
        "nom": "Boom inflationniste",
        "level": "green",
        "favorise": ["matieres premieres", "energie", "valeur/cycliques", "or",
                     "obligations indexees"],
        "defavorise": ["obligations longues"],
        "alloc": {"actions": 65, "obligations": 15, "or": 9,
                  "commodities": 6, "cash": 5},
        "commentaire": ("Croissance et inflation au-dessus de leur tendance. L'inflation "
                        "recompense les actifs reels et penalise le nominal : surponderer "
                        "or et matieres premieres, eviter la duration longue."),
    },
    "Q3": {
        "croissance": "basse", "inflation": "haute",
        "nom": "Stagflation",
        "level": "red",
        "favorise": ["or", "matieres premieres", "cash", "actifs reels"],
        "defavorise": ["actions", "obligations", "credit"],
        "alloc": {"actions": 50, "obligations": 21, "or": 12,
                  "commodities": 8, "cash": 9},
        "commentaire": ("Croissance sous sa tendance et inflation au-dessus : le pire "
                        "quadrant pour un portefeuille classique, actions ET obligations "
                        "souffrent en meme temps. Renforcer or, matieres premieres et cash."),
    },
    "Q4": {
        "croissance": "basse", "inflation": "basse",
        "nom": "Deflation / recession",
        "level": "yellow",
        "favorise": ["obligations longues", "cash", "actions defensives et qualite"],
        "defavorise": ["matieres premieres", "cycliques", "credit risque"],
        "alloc": {"actions": 58, "obligations": 25, "or": 7,
                  "commodities": 2, "cash": 8},
        "commentaire": ("Croissance et inflation sous leur tendance. La baisse des taux "
                        "fait le travail : la duration devient l'amie du portefeuille, "
                        "allonger les obligations et reduire l'or."),
    },
}

PMI = {
    "green": 50.0, "yellow_min": 48.0, "red": 48.0,
    "red_consecutive_months": 2, "trend_months": [3, 6],
}

INFLATION = {
    "services_threshold_yellow": 3.5,
    "acceleration_mom_pp": 0.3, "trend_months": [3, 6],
}

# ESI Eurostat - equivalent libre du PMI payant (dataset ei_bssi_m_r2).
# CALIBRAGE (2026-09-26) : mode "cycle_relative" = on compare l ESI a SA
# PROPRE moyenne 7 ans, comme les axes du quadrant (methode Gave).
# Pourquoi pas le 100 fixe : la zone euro est structurellement SOUS 100
# depuis 2019 ; un neutre fixe a 100 la noterait "faible" en permanence,
# ce qui est un biais de niveau, pas un signal de cycle.
# ex. reel 2026-08 : ESI 98,4 vs moyenne 7 ans 98,39 -> ecart +0,01 pt
# -> score 50 (pile sur la tendance). Le neutre fixe aurait donne 40.
# span_pts = ecart (en points d ESI) qui sature le score en 0 ou 100.
SENTIMENT = {"mode": "cycle_relative", "span_pts": 3.0, "mean_months": 84,
             "neutral": 100.0, "slope": 5.0, "yellow_low": 97.0}

# Seuils de niveau TTF (EUR/MWh), ajoutes le 2026-09-26 avec le branchement live.
# Reference historique : le TTF a explose a >300 en 2022, est revenu ~25-35 en
# 2023-2024, et se situe dans la fourchette 26-84 sur les 52 dernieres semaines.
# >70 = tension marquee ; 50-70 = vigilance ; <50 = detendu.
# ttf_in_score=False : le TTF est COLLECTE, SCORE et AFFICHE mais n'entre PAS
# encore dans la moyenne de la categorie energie (qui reste sur le Brent seul).
# Raison : passer de 1 a 2 indicateurs dans une categorie change la ponderation
# implicite, donc le score global. C'est une decision de methodologie qui revient
# a Eric - on la rend reversible par un simple booleen plutot que de l'imposer.
# CLI OCDE (indicateur composite avance). Le 100 est la tendance de long terme
# PAR CONSTRUCTION de l indice -> un neutre fixe a 100 est legitime ici (a la
# difference de l ESI, qui derive et demande un calage cycle_relative).
# cli_in_score=False : le CLI est collecte, score et affiche, mais n entre pas
# encore dans la moyenne de la categorie croissance (qui reste ESI). Meme
# logique que ttf_in_score : decision reversible cote config, pas imposee.
OECD_CLI = {"neutral": 100.0, "slope": 20.0, "span_pts": 3.0, "cli_in_score": True}

ENERGY = {"brent_mom_pct_alarm": 10.0, "ttf_mom_pct_alarm": 15.0, "volatility_high": 0.05,
          "ttf_high": 70.0, "ttf_mid": 50.0, "ttf_in_score": True}

ECB = {"max_rate_percent": 4.0, "default_stance": "pause"}

GEO = {"impact_weight_energy": 0.5, "keywords": ["sanctions","escalade","moyen-orient","brent","conflit","guerre"]}

SCORING = {
    "weights": {"croissance": 0.25, "inflation": 0.25, "energie": 0.20, "bce": 0.20, "geo": 0.10},
    "global_threshold_green": 70, "global_threshold_yellow": 50,
}

TRANSITION = {"high": 76, "probable": 51, "surveillance": 26, "stable": 25}

FRESHNESS = {"pmi": 45, "inflation": 45, "energie": 5, "bce": 60, "geo": 7,
             # Plafond DUR pour les sources officielles (Eurostat/BCE) : on accepte
             # la derniere periode publiee meme ancienne en age calendaire, mais
             # jamais au-dela de ce seuil (anti-derive silencieuse).
             "official_max_age_days": 550}

DEFAULT_CONFIG = {
    "pmi": PMI, "sentiment": SENTIMENT, "inflation": INFLATION, "energy": ENERGY,
    "oecd_cli": OECD_CLI,
    "ecb": ECB, "geo": GEO, "quadrants": QUADRANTS, "scoring": SCORING, "transition": TRANSITION, "freshness": FRESHNESS, "quadrant": {"services_threshold": 3.3, "energy_th": 5.0,
                  "growth_band_pp": 0.2, "inflation_band_pp": 0.2},
}

def load_config(path=None):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    p = path or (BASE / "config.override.json")
    if p.exists():
        try:
            over = json.loads(p.read_text())
            for k, v in over.items():
                if isinstance(v, dict) and k in cfg:
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception as e:
            print("[CONFIG] override invalide: " + str(e))
    return cfg

def save_config(cfg, path=None):
    p = path or (BASE / "config.override.json")
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    cfg = load_config()
    print("Config: " + str(len(cfg)) + " sections")
