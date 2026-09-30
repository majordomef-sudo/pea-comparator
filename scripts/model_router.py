#!/usr/bin/env python3
"""
model_router.py — Sélectionne le modèle LLM selon la complexité de la tâche.
Usage : python3 model_router.py <task_type>
        python3 model_router.py default   → deepseek/deepseek-v4.1-flash
        python3 model_router.py complex   → deepseek/deepseek-v4-pro
        python3 model_router.py free      → google/gemma-4-31b-it (fallback)

Principes Eric (27/06/2026) :
  - Default  : DeepSeek v4 Flash (quotidien, rapide)
  - Complexe : DeepSeek v4 Pro (audit, refacto critique)
  - Fallback : Gemma 4 31b free (quand Flash indisponible)
"""

import sys
import json

# Map tâche → modèle (sans préfixe openrouter/)
MODEL_MAP = {
    # Default
    "default": "deepseek/deepseek-v4.1-flash",
    "script": "deepseek/deepseek-v4.1-flash",
    "content": "deepseek/deepseek-v4.1-flash",
    "cron": "deepseek/deepseek-v4.1-flash",
    "chat": "deepseek/deepseek-v4.1-flash",
    "quick": "deepseek/deepseek-v4.1-flash",

    # Complex
    "complex": "deepseek/deepseek-v4-pro",
    "audit": "deepseek/deepseek-v4-pro",
    "security": "deepseek/deepseek-v4-pro",
    "refacto": "deepseek/deepseek-v4-pro",
    "expert": "deepseek/deepseek-v4-pro",

    # Fallback gratuit
    "free": "google/gemma-4-31b-it",
    "fallback": "google/gemma-4-31b-it",
    "test": "google/gemma-4-31b-it",
    "draft": "google/gemma-4-31b-it",
}

# Fallback chain si le modèle default est down
# Gemma 4 31b :free (gratuit) en fallback
FALLBACK_CHAIN = [
    "deepseek/deepseek-v4.1-flash",
    "deepseek/deepseek-v4-pro",
    "google/gemma-4-31b-it",
]


def get_model(task_type: str = "default", with_prefix: bool = True) -> str:
    """Retourne le modèle pour une tâche donnée.
    with_prefix=True  → openrouter/<model>
    with_prefix=False → <model> (pour appels API directs)
    """
    model = MODEL_MAP.get(task_type, MODEL_MAP["default"])
    if with_prefix:
        return f"openrouter/{model}"
    return model


def get_fallback_chain(with_prefix: bool = True) -> list:
    """Retourne la chaine de fallback."""
    if with_prefix:
        return [f"openrouter/{m}" for m in FALLBACK_CHAIN]
    return list(FALLBACK_CHAIN)



import json
from pathlib import Path
from datetime import datetime, timezone

COST_LOG = Path.home() / "output" / "logs" / "llm_costs.jsonl"

# Modèle -> prix par 1K tokens (source: OpenRouter)
MODEL_PRICES = {
    "deepseek/deepseek-v4.1-flash": {"in": 0.00015, "out": 0.00060},
    "deepseek/deepseek-v4-pro": {"in": 0.002, "out": 0.008},
    "google/gemma-4-31b-it": {"in": 0.0001, "out": 0.00034},
    "google/gemma-4-26b-a4b-it": {"in": 0.00007, "out": 0.00034},
}

def estimate_cost(model, prompt_tokens, completion_tokens):
    """Estime le coût US cent selon les prix OpenRouter."""
    prices = MODEL_PRICES.get(model, {"in": 0.0002, "out": 0.0008})
    return (prompt_tokens / 1000) * prices["in"] + (completion_tokens / 1000) * prices["out"]

def log_llm_call(model, prompt_tokens=0, completion_tokens=0, cost_usd=None):
    """Log un appel LLM dans llm_costs.jsonl."""
    try:
        if cost_usd is None:
            cost_usd = estimate_cost(model, prompt_tokens, completion_tokens)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(cost_usd, 6),
        }
        COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(COST_LOG, "a") as f:
            f.write(json.dumps(entry) + chr(10))
    except Exception as e:
        import sys
        print(f"[LLM TRACK] Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(get_model("default"))
    else:
        result = {
            "model": get_model(sys.argv[1], with_prefix=False),
            "full": get_model(sys.argv[1], with_prefix=True),
            "fallback_chain": get_fallback_chain(with_prefix=True),
        }
        print(json.dumps(result, indent=2))