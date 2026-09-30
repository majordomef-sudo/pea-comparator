#!/usr/bin/env python3
"""
config_loader.py — Chargeur de configuration consolidé pour le pipeline Neuro-Finance.
Lit pipeline_config.yaml et exporte toutes les constantes utilisées par l'orchestrateur.
Remplace les blocs hardcodés du pipeline_orchestrator.py.
"""
import os
from pathlib import Path

# Importer les fonctions existantes de pipeline_config
from pipeline.pipeline_config import (
    load_config, load_secrets,
    cfg,
    # Mapping direct
    forbidden_words as _forbidden_words,
    guru_blacklist as _guru_blacklist,
    phonetic_fixes as _phonetic_fixes,
    default_tags as _default_tags,
    default_hashtags as _default_hashtags,
    desc_template as _desc_template,
    playlist_id as _playlist_id,
)

# ── Re-exports depuis pipeline_config.py ─────────────────────────────

def load_pipeline_config():
    """Charge et retourne la configuration complète, avec valeurs par défaut."""
    config = load_config()

    # Valeurs par défaut si sections manquantes
    defaults = {
        "forbidden": {
            "guru_blacklist": [
                "riche rapidement", "secret", "miracle", "liberté financière",
                "astuce", "gagner gros", "methode miracle", "devenir riche"
            ],
            "forbidden_words": [
                "hedge fund", "smart money", "leverage", "criterion", "storytelling",
                "dark pattern", "exit strategy", "deal", "trade", "trading", "trader",
                "broker", "asset", "liability", "equity", "bond", "bull market",
                "bear market", "spread", "swap", "default", "margin call", "portfolio",
                "capital gain", "cash flow", "pricing", "risk premium", "overhead",
                "fee", "rating", "investment bank", "private equity", "venture capital",
                "high frequency", "algorithmic", "behavioral finance", "mispricing",
                "volatility", "dinero", "mercado", "inversion", "ganancia", "perdida",
                "riesgo", "banco", "finanzas", "accion", "bono", "tasa", "negocio",
                "interes", "inversor", "ahorro", "deuda",
            ],
            "phonetic_fixes": {
                "cognitive": "cognitif", "cognition": "cognition",
                "behavioral": "comportemental", "algorithm": "algorithme",
                "algorithmic": "algorithmique", "default": "défaut",
                "leverage": "levier", "volatility": "volatilité",
                "portfolio": "portefeuille", "equity": "capitaux",
                "liability": "passif", "bond": "obligation",
                "premium": "prime", "rating": "notation", "criterion": "critère",
                "hedge fund": "fonds spéculatif", "smart money": "capitaux informés",
                "storytelling": "récit", "dark pattern": "manipulation",
                "exit strategy": "stratégie de sortie", "deal": "accord",
                "trade": "échange", "trading": "transaction",
                "trader": "opérateur", "broker": "courtier",
                "asset": "actif", "bull market": "marché haussier",
                "bear market": "marché baissier", "spread": "écart",
                "swap": "échange", "margin call": "appel de marge",
                "capital gain": "plus-value", "cash flow": "flux de trésorerie",
                "pricing": "tarification", "risk premium": "prime de risque",
                "overhead": "frais généraux", "fee": "commission",
                "investment bank": "banque d'affaires",
                "private equity": "capital-investissement",
                "venture capital": "capital-risque",
                "high frequency": "haute fréquence",
                "behavioral finance": "finance comportementale",
                "mispricing": "erreur de prix",
                "échouent": "font faillite",
                "s'évanouissent": "disparaissent",
                "disparaissent": "disparaissent",
            }
        },
        "youtube": {
            "playlist_id": "PLdwDhfX2NgAAuB6rWjAJpr4yETIM4_nmO",
            "default_tags": [
                "Neuro-Finance", "finance comportementale", "biais cognitifs",
                "investissement", "psychologie de l'argent", "éducation financière",
                "cerveau et argent", "antifragilité", "probabilités", "risque"
            ],
            "default_hashtags": "\n#NeuroFinance #FinanceComportementale #Investissement #PEA #ETF #Bourse #Patrimoine #IndépendanceFinancière #PsychologieDeLArgent",
        },
        "templates": {
            "rich_description": "",
        }
    }

    # Fusion des valeurs par défaut (ne pas écraser celles du YAML)
    for section, vals in defaults.items():
        if section not in config:
            config[section] = vals
        elif isinstance(vals, dict):
            for k, v in vals.items():
                if k not in config[section]:
                    config[section][k] = v

    return config


# ── Exports direct (utilise pipeline_config.py, fallback aux valeurs par défaut) ──

def get_guru_blacklist():
    return _guru_blacklist()

def get_forbidden_words():
    return _forbidden_words()

def get_phonetic_fixes():
    fixes = _phonetic_fixes()
    return fixes if fixes else load_pipeline_config()["forbidden"]["phonetic_fixes"]

def get_default_tags():
    tags = _default_tags()
    return tags if tags else load_pipeline_config()["youtube"]["default_tags"]

def get_default_hashtags():
    ht = _default_hashtags()
    return ht if ht else load_pipeline_config()["youtube"]["default_hashtags"]

def get_rich_description_template():
    tmpl = _desc_template()
    return tmpl if tmpl else load_pipeline_config()["templates"]["rich_description"]

def get_playlist_id():
    pid = _playlist_id()
    return pid if pid else load_pipeline_config()["youtube"]["playlist_id"]


# ── Pour compatibilité directe (accès comme des constantes) ──

# Ces fonctions wrapper sont appelées au chargement pour peupler les variables
# utilisées dans les fonctions validate_script_data, calculate_guru_score, etc.
GURU_BLACKLIST = get_guru_blacklist()
FORBIDDEN_WORDS = get_forbidden_words()
PHONETIC_FIXES = get_phonetic_fixes()
DEFAULT_TAGS = get_default_tags()
DEFAULT_HASHTAGS = get_default_hashtags()
RICH_DESC_TEMPLATE = get_rich_description_template()
PLAYLIST_ID = get_playlist_id()


print(f"[CONFIG_LOADER] Chargé: {len(GURU_BLACKLIST)} guru, {len(FORBIDDEN_WORDS)} forbidden, {len(PHONETIC_FIXES)} phonetic fixes")

