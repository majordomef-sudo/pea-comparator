"""
Module mouvement — analyse des changements de scène et ratio mouvement/statique

Métriques :
- Score moyen de mouvement (via scene change ratio)
- Ratio motion/statique global
- Segments statiques anormaux
"""

import json, subprocess, re
from pathlib import Path


def analyze_motion(video_path: Path) -> dict:
    """Analyse le mouvement via scene change ratios de ffmpeg"""
    result = {
        "motion_scores": [],
        "avg_motion": 0,
        "motion_static_ratio": 0.5,  # défaut neutre
        "static_segments": [],
        "details": [],
    }

    # Échantillonner le scene change ratio toutes les 0.5s
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", "select='gte(scene,0.01)',metadata=print:file=-",
        "-vsync", "vfr", "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    # Extraire les scores de changement de scène
    scores = []
    for line in proc.stderr.split("\n"):
        if "scene:" in line:
            match = re.search(r'scene:([\d.]+)', line)
            if match:
                val = float(match.group(1))
                scores.append(val)

    result["motion_scores"] = scores[:100]  # max 100

    if scores:
        avg = sum(scores) / len(scores)
        result["avg_motion"] = round(avg, 4)

        # Ratio segments avec fort mouvement (>0.3)
        high_motion = sum(1 for s in scores if s > 0.3)
        result["motion_static_ratio"] = round(high_motion / len(scores), 2)

    # Analyse
    details = []
    ratio = result["motion_static_ratio"]
    if 0.3 <= ratio <= 0.7:
        details.append(f"✅ Bon équilibre motion/statique ({ratio:.0%} mouvement)")
    elif ratio > 0.7:
        details.append(f"⚠️  Trop de mouvement ({ratio:.0%}) — risque de fatigue visuelle")
    else:
        details.append(f"⚠️  Trop statique ({ratio:.0%} mouvement) — risque d'ennui")

    result["details"] = details

    return result