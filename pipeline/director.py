#!/usr/bin/env python3
"""
director.py — Le "Cerveau" du Studio de Production
Définit les directives de qualité et les critères de succès pour chaque étape du pipeline.
Inspiré d'OpenMontage : transforme un script linéaire en une série de décisions agentiques.
"""

class StageDirector:
    """Directives spécialisées par étape du pipeline."""
    
    # STAGE 1: SCRIPTING
    SCRIPT_DIRECTIVE = {
        "goal": "Créer un script à haute rétention",
        "criteria": [
            "Le hook doit être un paradoxe ou une donnée chiffrée vérifiable",
            "Au moins un des segments 1 à 3 doit contenir une donnée chiffrée fiable",
            "Zéro jargon 'guru', focus sur la science et la psychologie",
            "Rythme rapide : phrases courtes, impact maximal"
        ],
        "fail_signal": "Trop de blabla, manque de données, hook faible"
    }

    # STAGE 2: ASSETS
    ASSET_DIRECTIVE = {
        "goal": "Générer des visuels cohérents et haut de gamme",
        "criteria": [
            "L'image doit correspondre à l'émotion du segment",
            "Esthétique 'Dark Luxury' / 'Financial Minimalist'",
            "Pas de texte généré dans l'image (évite les hallucinations)",
            "Lumière cinématique, focus net"
        ],
        "fail_signal": "Image floue, incohérence thématique, texte bizarre"
    }

    # STAGE 3: AUDIO
    AUDIO_DIRECTIVE = {
        "goal": "Produire une narration captivante",
        "criteria": [
            "Vitesse de parole optimisée (-5% pour la clarté)",
            "Zéro silence prolongé (> 0.5s)",
            "Prononciation parfaite des termes techniques",
            "Contraste marqué entre Voix A (Expert) et Voix B (Provocateur)"
        ],
        "fail_signal": "Robotique, silences gênants, erreurs de prononciation"
    }

    # STAGE 4: FINAL COMPOSITION (The Edit)
    EDIT_DIRECTIVE = {
        "goal": "Maximiser le dynamisme visuel",
        "criteria": [
            "Un clip distinct par segment, avec mouvement interne et stat card lisible",
            "Utilisation systématique du Ken Burns (zoom/pan)",
            "Alignement parfait entre le mot prononcé et l'apparition du sous-titre",
            "Overlays (stat cards) synchronisés avec les chiffres"
        ],
        "fail_signal": "Plans trop longs, désynchronisation audio/texte"
    }

    @classmethod
    def get_directive(cls, stage_name: str) -> dict:
        directives = {
            "script": cls.SCRIPT_DIRECTIVE,
            "assets": cls.ASSET_DIRECTIVE,
            "audio": cls.AUDIO_DIRECTIVE,
            "edit": cls.EDIT_DIRECTIVE,
        }
        return directives.get(stage_name, {})

    @classmethod
    def validate_gate(cls, stage_name: str, report: dict) -> bool:
        """
        Décide si le résultat d'une étape est suffisant pour passer à la suivante.
        Retourne True si OK, False si on doit recommencer.
        """
        # Logique de validation basée sur le rapport de l'étape
        # Par exemple, pour le script :
        if stage_name == "script":
            if report.get("guru_score", 0) > 2 or not report.get("has_data", False):
                return False
        
        # Pour la vidéo finale (QA)
        if stage_name == "edit":
            if report.get("score", 0) < 70:
                return False
        
        return True
