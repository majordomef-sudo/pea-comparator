
"""
llm_router.py — Routage dynamique des modèles LLM pour minimiser les coûts.
Choisit le modèle selon la complexité de la tâche.
"""
import os, json
from pathlib import Path

# Modèles disponibles (coût décroissant)
MODELS = {
    "ultra_cheap": {  # Tâches triviales: classification, extraction simple
        "model": "google/gemma-4-31b-it",
        "max_tokens": 256,
        "cost_per_call": 0.0,  # Gratuit
    },
    "standard": {  # Génération de contenu, scripts
        "model": "deepseek/deepseek-v4.1-flash",
        "max_tokens": 1500,
        "cost_per_call": 0.00015,
    },
    "expert": {  # Audit, analyse complexe, refactoring
        "model": "deepseek/deepseek-v4-pro",
        "max_tokens": 4000,
        "cost_per_call": 0.002,
    },
}

def select_model(task_type="standard"):
    """Sélectionne le modèle adapté à la tâche."""
    return MODELS.get(task_type, MODELS["standard"])

def estimate_cost(model_info, prompt_tokens=500, completion_tokens=500):
    """Estimation du coût d'un appel."""
    return model_info["cost_per_call"]

def select_for_prompt(prompt, max_tokens=1500):
    """Sélection intelligente basée sur le prompt."""
    prompt_len = len(prompt.split())
    
    if prompt_len < 50 and max_tokens <= 256:
        return MODELS["ultra_cheap"]
    elif prompt_len > 500 or max_tokens > 2000:
        return MODELS["expert"]
    else:
        return MODELS["standard"]

def get_model_string(task_type="standard"):
    """Retourne le string du modèle pour l'API OpenRouter."""
    return MODELS[task_type]["model"]
