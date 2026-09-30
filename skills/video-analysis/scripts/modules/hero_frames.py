"""
Module Hero Frames — sélection intelligente des 3-5 frames clés d'une vidéo

Adapté de claude-watch (taoufik123-collab/claude-watch):
  frames.py::select_hero_frames()

Heuristique déterministe :
  1. Première frame du hook (0-10s) — capture le pattern d'ouverture
  2. Première frame du plan le plus dynamique (motion max)
  3. Première frame du plan le plus long
  4. + 1-2 frames uniformément réparties

Utile pour:
  - Rapport de qualité (images clés)
  - Thumbnail candidate
  - Blog / social media previews
"""

from __future__ import annotations

from pathlib import Path


def select_hero_frames(
    frames: list[dict],
    shot_data: list[dict] | None = None,
    hook_end: float = 10.0,
    max_hero: int = 5,
    min_hero: int = 3,
) -> list[dict]:
    """Sélectionne 3-5 'hero frames' représentatives.

    Args:
        frames: Liste de frames avec 'timestamp' et 'path'
        shot_data: Données de plans (optionnel, de scenes.py)
        hook_end: Fin de la zone hook en secondes
        max_hero: Maximum de hero frames
        min_hero: Minimum de hero frames

    Returns:
        Sous-ensemble ordonné des frames les plus représentatives
    """
    if not frames:
        return []

    chosen_indices: list[int] = []

    def _add(idx: int) -> None:
        if 0 <= idx < len(frames) and idx not in chosen_indices:
            chosen_indices.append(idx)

    # 1. Première frame dans la zone hook (0-10s)
    for i, f in enumerate(frames):
        if f["timestamp"] <= hook_end:
            _add(i)
            break

    # 2. Première frame du plan le plus dynamique
    if shot_data:
        # Les shots peuvent être des floats (timestamps) ou des dicts
        shot_dicts = []
        for s in shot_data:
            if isinstance(s, dict):
                shot_dicts.append(s)
            elif isinstance(s, (int, float)):
                # Float = timestamp de transition, créer un dict simple
                shot_dicts.append({"timestamp": float(s), "duration": 1.0})
        
        if shot_dicts:
            shots = sorted(
                shot_dicts,
                key=lambda s: (s.get("duration", 1) if isinstance(s.get("duration"), (int, float)) else 1)
                              * (s.get("transition_score", 1) if isinstance(s.get("transition_score"), (int, float)) else 1),
                reverse=True,
            )
            for shot in shots[:2]:
                start_t = float(shot.get("timestamp", 0))
                for i, f in enumerate(frames):
                    if f["timestamp"] >= start_t:
                        _add(i)
                        break

    # 3. Compléter avec des frames uniformément réparties si insuffisant
    if len(chosen_indices) < min_hero:
        gap = max(1, len(frames) // max_hero)
        for i in range(0, len(frames), gap):
            _add(i)
            if len(chosen_indices) >= max_hero:
                break

    chosen_indices = sorted(set(chosen_indices))[:max_hero]
    return [frames[i] for i in chosen_indices]


def describe_hero_frames(hero_frames: list[dict]) -> str:
    """Génère une description textuelle des hero frames pour le rapport."""
    if not hero_frames:
        return "Aucune hero frame sélectionnée"

    lines = [f"{len(hero_frames)} hero frame(s) :"]
    for i, f in enumerate(hero_frames):
        ts = f["timestamp"]
        minutes = int(ts // 60)
        seconds = int(ts % 60)
        lines.append(f"  {i+1}. `{Path(f['path']).name}` — t={minutes:02d}:{seconds:02d}")
    return "\n".join(lines)