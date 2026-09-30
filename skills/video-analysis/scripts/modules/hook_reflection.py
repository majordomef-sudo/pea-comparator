"""
Module d'auto-réflexion hook — log les scores et ajuste le pipeline

Déclenché après chaque analyse vidéo :
1. Log le score hook + pattern dans l'historique auto-réflexion
2. Si 3 vidéos consécutives ont hook_score < 6 → ajuste le prompt du pipeline
3. Recommande des patterns de hook sous-performants

Usage programmatique :
  from hook_reflection import log_hook_score, get_hook_score_trend
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
REFLECTION_DIR = WORKSPACE / "state" / "auto-reflection"
HOOK_HISTORY_FILE = REFLECTION_DIR / "hook_history.json"
PIPELINE_FILE = WORKSPACE / "skills" / "alfred_cron" / "nightly_orchestrator.py"


# Seuils de déclenchement
HOOK_ALERT_THRESHOLD = 6.5  # DEPRECIE le 27/09/2026 : score interne non correle a l attention reelle
RETENTION_ALERT_THRESHOLD = 5.0  # retention_score /10 (echelle percentile) : 5 = mediane de la chaine
CONSECUTIVE_FAILURES = 3    # nombre d'échecs consécutifs avant ajustement


def _load_history() -> list[dict]:
    """Charge l'historique des scores hook."""
    if HOOK_HISTORY_FILE.exists():
        try:
            return json.loads(HOOK_HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_history(history: list[dict]) -> None:
    """Sauvegarde l'historique."""
    REFLECTION_DIR.mkdir(parents=True, exist_ok=True)
    HOOK_HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def log_hook_score(
    video_name: str,
    hook_score: float | None,
    hook_pattern: str | None,
    frame_count: int,
    duration: float,
    retention_pct: float | None = None,
    retention_score: float | None = None,
) -> dict:
    """Log le score hook d'une vidéo et retourne les ajustements recommandés."""
    history = _load_history()

    entry = {
        "video": video_name,
        "timestamp": datetime.now().isoformat(),
        "hook_score": hook_score,
        "hook_pattern": hook_pattern,
        "frame_count": frame_count,
        "duration": round(duration, 1),
    }
    if retention_pct is not None:
        entry["retention_pct"] = round(float(retention_pct), 2)
    if retention_score is not None:
        entry["retention_score"] = float(retention_score)

    history.append(entry)

    # Garder max 50 entrées
    if len(history) > 50:
        history = history[-50:]

    _save_history(history)

    # Analyse de tendance
    recommendation = _analyze_trend(history)
    if recommendation:
        entry["adjustment"] = recommendation

    return entry


def _analyze_trend(history: list[dict]) -> dict | None:
    """Analyse la tendance et recommande un ajustement.
    Recalibre le 27/09/2026 : on juge sur la RETENTION reelle (retention_score, echelle
    percentile : 5 = mediane de la chaine) et non plus sur hook_score, un score interne
    qui prenait 4 valeurs pour 50 videos et se revelait anti-correle aux vues."""
    scored = [h for h in history if h.get("retention_score") is not None]
    metric, threshold = "retention_score", RETENTION_ALERT_THRESHOLD
    if len(scored) < CONSECUTIVE_FAILURES:
        legacy = [h for h in history if h.get("hook_score") is not None]
        if len(legacy) < CONSECUTIVE_FAILURES:
            return None
        scored, metric, threshold = legacy, "hook_score", HOOK_ALERT_THRESHOLD
    last_n = scored[-CONSECUTIVE_FAILURES:]
    low = [h for h in last_n if h[metric] < threshold]
    if len(low) < CONSECUTIVE_FAILURES:
        return None
    avg = sum(h[metric] for h in last_n) / len(last_n)
    return {
        "alert": True,
        "metric": metric,
        "message": (
            f"Retention faible {CONSECUTIVE_FAILURES} fois de suite "
            f"(moyenne {avg:.1f}/10 sur {metric}). "
            f"Patterns rencontres : {[h.get('hook_pattern') for h in last_n]}. "
            f"Ajustement du prompt pipeline recommande."
        ),
        "avg_score": round(avg, 1),
        "patterns_seen": [h.get("hook_pattern") for h in last_n],
        "adjustment_type": "prompt_hook",
    }


def get_hook_score_trend() -> dict:
    """Retourne les stats de tendance des scores hook."""
    history = _load_history()
    scored = [h for h in history if h.get("hook_score") is not None]

    if not scored:
        return {"total": 0, "avg": None, "trend": "unknown"}

    recent = scored[-5:] if len(scored) >= 5 else scored
    all_scores = [h["hook_score"] for h in recent]

    return {
        "total": len(scored),
        "avg": round(sum(all_scores) / len(all_scores), 1),
        "last_5": [h["hook_score"] for h in recent[-5:]],
        "last_patterns": [h.get("hook_pattern") for h in recent[-5:]],
        "trend": "up" if all_scores[-1] > all_scores[0] else "down" if all_scores[-1] < all_scores[0] else "stable",
    }


def suggest_hook_prompt_adjustment(history: list[dict] | None = None) -> str | None:
    """Génère une suggestion d'ajustement du prompt pipeline pour améliorer le hook.

    Retourne le texte à ajouter/remplacer dans le prompt, ou None si OK.
    """
    if history is None:
        history = _load_history()

    scored = [h for h in history if h.get("hook_score") is not None]
    if len(scored) < CONSECUTIVE_FAILURES:
        return None

    last_n = scored[-CONSECUTIVE_FAILURES:]
    low = [h for h in last_n if h["hook_score"] < HOOK_ALERT_THRESHOLD]
    if len(low) < CONSECUTIVE_FAILURES:
        return None

    # Patterns qui ont échoué
    failed_patterns = set(h.get("hook_pattern") for h in low if h.get("hook_pattern"))

    suggestion_lines = [
        "\n--- RENFORCEMENT HOOK (auto-ajusté par analyse vidéo) ---",
        "⚠️ ATTENTION : les hooks précédents n'ont pas accroché.",
        "Renforce l'accroche de Segment 1 :",
    ]

    if "standard" in failed_patterns or not failed_patterns:
        suggestion_lines.extend([
            "- Ouvre PAR un chiffre choc (pourcentage, euros) dans les 2 premiers mots",
            "- Ajoute 'vous' dans les 3 premiers mots pour interpellation personnelle",
            "- Exemple : '83% de vos économies...' / '2400€ par an...'",
        ])
    if "question" not in failed_patterns:
        suggestion_lines.append(
            "- Termine la 1ère phrase par un point d'interrogation"
        )

    return "\n".join(suggestion_lines)


def apply_hook_adjustment_to_pipeline(suggestion: str) -> bool:
    """Ajoute la suggestion de renforcement hook dans le prompt du pipeline.

    Retourne True si appliqué.
    """
    if not PIPELINE_FILE.exists():
        return False

    content = PIPELINE_FILE.read_text()

    # Vérifie si la suggestion existe déjà
    if "RENFORCEMENT HOOK" in content:
        return False  # déjà appliqué

    # Insérer la suggestion juste avant "--- STRATÉGIE DU HOOK"
    marker = '--- STRATÉGIE DU HOOK (inspiré Finary) ---'
    if marker in content:
        content = content.replace(marker, f"{suggestion}\n\n{marker}")
        PIPELINE_FILE.write_text(content)
        return True

    return False


def summarize_hook_trend() -> str:
    """Résumé lisible de la tendance hook pour les rapports."""
    trend = get_hook_score_trend()
    history = _load_history()
    scored = [h for h in history if h.get("hook_score") is not None]

    if trend["avg"] is None:
        return "Aucune données hook"

    lines = [
        f"📊 Tendance hook ({trend['total']} vidéos analysées) :",
        f"  Moyenne : {trend['avg']}/10",
        f"  Derniers : {trend['last_5']}",
        f"  Patterns : {trend['last_patterns']}",
        f"  Tendance : {trend['trend']}",
    ]

    if trend["avg"] < HOOK_ALERT_THRESHOLD:
        lines.append("  ⚠️ Hook systématiquement faible — ajustement pipeline recommandé")

    return "\n".join(lines)