"""
Module rapport — agrège les scores et génère les améliorations

Inclut désormais les données du hook microscope et hero frames
(importées de claude-watch taoufik123-collab/claude-watch)
"""

from datetime import datetime
from pathlib import Path


def _generate_improvements(
    tech: dict, scenes: dict, motion: dict,
    audio: dict, content: dict, virality: dict,
    hook: dict | None = None,
) -> list:
    """Génère des suggestions d'amélioration basées sur les faiblesses détectées"""
    improvements = []

    # Technique
    if tech.get("score", 30) < 20:
        if tech.get("black_frames"):
            improvements.append({
                "action": "Corriger les black frames",
                "reason": f"{len(tech['black_frames'])} black frame(s) détecté(s)",
                "impact": len(tech['black_frames']),
                "patch": {
                    "description": "Ajouter -vf crop ou pad pour éliminer les bords noirs",
                    "file": "",
                    "change": "Ajouter cropdetect/crop avant encodage",
                    "old_text": "",
                    "new_text": "",
                }
            })
        if tech.get("freeze_frames"):
            improvements.append({
                "action": "Corriger les freeze frames",
                "reason": f"{len(tech['freeze_frames'])} freeze frame(s)",
                "impact": len(tech['freeze_frames']),
                "patch": None,
            })
        dur = tech.get("duration", 0)
        if dur < 40:
            improvements.append({
                "action": "Allonger la durée de la vidéo",
                "reason": f"Durée actuelle: {dur}s (cible 40-60s)",
                "impact": 3,
                "patch": {
                    "description": "Augmenter le nombre de scènes dans le pipeline",
                    "file": "",
                    "change": "Ajouter une scène ou rallonger les voix off",
                    "old_text": "",
                    "new_text": "",
                }
            })
        elif dur > 60:
            improvements.append({
                "action": "Réduire la durée de la vidéo",
                "reason": f"Durée actuelle: {dur}s (cible max 60s)",
                "impact": 3,
                "patch": None,
            })

    # Contenu
    cs = content.get("score", 30)
    if cs < 20:
        hook_data = content.get("hook", {})
        if not hook_data.get("has_hook"):
            improvements.append({
                "action": "Ajouter un hook plus percutant dans les 5 premières secondes",
                "reason": "Aucun hook détecté en ouverture",
                "impact": 8,
                "patch": {
                    "description": "Renforcer le prompt LLM pour générer un hook systématique",
                    "file": "",
                    "change": "Ajouter 'Commence par une question ou un chiffre choc' dans le prompt",
                    "old_text": "",
                    "new_text": "",
                }
            })
        if content.get("data_count", 0) < 2:
            improvements.append({
                "action": "Ajouter des données chiffrées",
                "reason": f"Seulement {content['data_count']} donnée(s) chiffrée(s)",
                "impact": 4,
                "patch": {
                    "description": "Renforcer l'exigence de données chiffrées dans le prompt LLM",
                    "file": "",
                    "change": "Ajouter 'Inclus AU MOINS 2 chiffres, %, millions ou euros' dans le prompt",
                    "old_text": "",
                    "new_text": "",
                }
            })
        if not content.get("cta", {}).get("has_cta"):
            improvements.append({
                "action": "Ajouter un call-to-action en fin de vidéo",
                "reason": "Aucun CTA détecté",
                "impact": 5,
                "patch": {
                    "description": "Ajouter 'N'oublie pas de t'abonner' systématiquement",
                    "file": "",
                    "change": "Ajouter ligne CTA dans le template de scène finale",
                    "old_text": "",
                    "new_text": "",
                }
            })
        if content.get("forbidden_words"):
            improvements.append({
                "action": "Supprimer les mots interdits du script",
                "reason": f"Mots: {', '.join(content['forbidden_words'][:3])}",
                "impact": 3,
                "patch": None,
            })
        if content.get("guru_score", 0) > 3:
            improvements.append({
                "action": "Réduire le ton 'gourou' du script",
                "reason": f"Guru score: {content['guru_score']}/10",
                "impact": 3,
                "patch": None,
            })

    # Audio
    if audio.get("score", 20) < 12:
        if audio.get("total_silence_duration", 0) > 5:
            improvements.append({
                "action": "Réduire les silences dans la voix-off",
                "reason": f"{audio['total_silence_duration']}s de silence total",
                "impact": 3,
                "patch": None,
            })
        if not audio.get("has_audio", False):
            improvements.append({
                "action": "Ajouter une piste audio voix-off",
                "reason": "Aucun audio détecté",
                "impact": 8,
                "patch": None,
            })

    # Viralité
    vs = virality.get("score", 20)
    if vs < 10:
        vf = virality.get("factors", {})
        if vf.get("transitions_per_min", 0) < 6:
            improvements.append({
                "action": "Augmenter le rythme de coupe",
                "reason": f"Seulement {vf['transitions_per_min']} transitions/min",
                "impact": 3,
                "patch": None,
            })
        if not vf.get("has_hook"):
            improvements.append({
                "action": "Ajouter un hook viral en ouverture",
                "reason": "Hook absent — essentiel pour la rétention",
                "impact": 5,
                "patch": None,
            })
        if not vf.get("has_cta"):
            improvements.append({
                "action": "Ajouter un CTA pour l'engagement",
                "reason": "CTA absent — réduit l'engagement",
                "impact": 3,
                "patch": None,
            })

    # Hook microscope (nouveau depuis claude-watch)
    if hook and hook.get("ran"):
        hook_score = hook.get("hook_score")
        if hook_score is not None and hook_score < 6:
            improvements.append({
                "action": "Améliorer le hook des 10 premières secondes",
                "reason": f"Score hook: {hook_score}/10 — pattern: {hook.get('hook_pattern', 'inconnu')}",
                "impact": 8,
                "patch": {
                    "description": "Revoir l'ouverture du script : question, chiffre choc ou promesse forte",
                    "file": "",
                    "change": "Renforcer le hook LLM : démarrer par une question ou un fait choquant",
                    "old_text": "",
                    "new_text": "",
                }
            })
        if hook.get("frame_count", 0) < 8:
            improvements.append({
                "action": "Augmenter le rythme visuel des 10 premières secondes",
                "reason": f"Seulement {hook['frame_count']} changements visuels dans le hook (cible >8)",
                "impact": 5,
                "patch": {
                    "description": "Ajouter des transitions rapides en ouverture",
                    "file": "",
                    "change": "Augmenter la fréquence de cuts dans les 10 premières secondes",
                    "old_text": "",
                    "new_text": "",
                }
            })

    # Scene-change frames (nouveau)
    scene_changes = scenes.get("scene_change_frames", [])
    if scene_changes and len(scene_changes) < 3:
        improvements.append({
            "action": "Ajouter des transitions visuelles",
            "reason": f"Seulement {len(scene_changes)} plans détectés — vidéo trop statique",
            "impact": 4,
            "patch": None,
        })

    # Limiter à 10 améliorations max
    improvements.sort(key=lambda x: x["impact"], reverse=True)
    return improvements[:10]


def generate_report(
    tech: dict, scenes: dict, motion: dict,
    audio: dict, content: dict, virality: dict,
    hook: dict | None = None,
    hero_frames: list | None = None,
    vision_analysis: dict | None = None,
) -> dict:
    """Génère le rapport complet avec scores et améliorations

    Nouveau: intègre hook microscope et hero frames (claude-watch).
    """

    # Poids: technique 30%, contenu 30%, audio 20%, viralité 20%
    tech_score = tech.get("score", 0)
    content_score = content.get("score", 0)
    audio_score = audio.get("score", 0)
    virality_score = virality.get("score", 0)

    global_score = round(
        tech_score + content_score + audio_score + virality_score
    )

    # Catégorie
    if global_score >= 85:
        category = "Excellent 🏆"
    elif global_score >= 70:
        category = "Bon 👍"
    elif global_score >= 50:
        category = "Correct ⚠️"
    else:
        category = "À améliorer 🔧"

    improvements = _generate_improvements(tech, scenes, motion, audio, content, virality, hook)

    report = {
        "video": None,
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "scores": {
            "global": global_score,
            "technical": tech_score,
            "content": content_score,
            "audio": audio_score,
            "virality": virality_score,
        },
        "modules": {
            "technical": tech,
            "scenes": scenes,
            "motion": motion,
            "audio": audio,
            "content": content,
            "virality": virality,
        },
        "vision_analysis": vision_analysis or {},
        "improvements": improvements,
        "summary": (
            f"Score {global_score}/100 — {category}. "
            f"Technique {tech_score}/30, Contenu {content_score}/30, "
            f"Audio {audio_score}/20, Viralité {virality_score}/20. "
            f"{len(improvements)} amélioration(s) suggérée(s)."
        ),
    }

    # Intégration hook microscope
    if hook and hook.get("ran"):
        report["hook_microscope"] = {
            "ran": True,
            "hook_score": hook.get("hook_score"),
            "hook_pattern": hook.get("hook_pattern"),
            "frame_count": hook.get("frame_count", 0),
            "text": hook.get("text", ""),
        }
        report["summary"] += (
            f" Hook: {hook.get('hook_score', '?')}/10 ({hook.get('hook_pattern', 'N/A')})."
        )

    # Intégration hero frames
    if hero_frames:
        report["hero_frames"] = [
            {"index": f.get("index"), "timestamp": f.get("timestamp"),
             "path": f.get("path")}
            for f in hero_frames
        ]

    return report