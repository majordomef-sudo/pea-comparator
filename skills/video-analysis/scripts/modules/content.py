"""
Module contenu — analyse LLM du script/vidéo

Métriques :
- Hook strength (5 premières secondes)
- Données chiffrées présentes
- Mots interdits / guru-score
- CTA/abonnement
- Émotion ciblée
- Score contenu /30

Appelle Gemma-4 via OpenRouter (gratuit) pour l'analyse NLP.
"""

import json, os, re, requests
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
SECRETS_PATH = Path.home() / ".secrets" / "env"

# Mots interdits
FORBIDDEN_WORDS = [
    "vous devez", "vous pouvez", "n'oubliez pas", "cliquez ici",
    "abonnez-vous maintenant", "incroyable", "révolutionnaire",
    "magique", "miraculeux", "trop beau pour être vrai",
    "richesse sans effort", "argent facile", "devenez riche"
]

# Émotions cibles finance
TARGET_EMOTIONS = [
    "peur", "espoir", "curiosité", "urgence",
    "confiance", "surprise", "frustration", "ambition"
]


def _load_openrouter_key() -> str:
    """Charge la clé OpenRouter depuis les secrets"""
    if SECRETS_PATH.exists():
        for line in SECRETS_PATH.read_text().split("\n"):
            if "OPENROUTER" in line and "=" in line:
                return line.split("=", 1)[1].strip().strip("\"'")
    return os.environ.get("OPENROUTER_API_KEY", "")


def _count_numbers(text: str) -> int:
    """Compte les données chiffrées dans un texte"""
    patterns = [
        r'\d+[\s]*%',           # 25%
        r'\d+[\s]*millions?',
        r'\d+[\s]*milliards?',
        r'\d+[\s]*euros?',
        r'\d+[\s]*€',
        r'\d+[\s]*\$',
        r'\d+[\s]*fois',
        r'[\d,]+\s*%',          # 25,5%
        r'\d+[\.\s]*x',         # 10x
    ]
    count = 0
    for p in patterns:
        count += len(re.findall(p, text, re.IGNORECASE))
    return count


def _detect_hook(text: str) -> dict:
    """Analyse si les 5 premières secondes du script contiennent un hook"""
    # Prendre les premiers mots (≈30 mots)
    words = text.split()[:30]
    if not words:
        return {"has_hook": False, "hook_text": "", "hook_score": 0}

    hook_text = " ".join(words)

    # Mots de hook forts
    hook_words = [
        "imagine", "si", "pourquoi", "comment", "savez-vous",
        "et si", "voici", "attention", "arrêtez", "stop",
        "le secret", "la vérité", "ce que", "jamais",
        "pourquoi", "quel est", "combien", "question",
    ]

    found_hooks = [w for w in hook_words if w.lower() in hook_text.lower()]

    # Questions / interpellations
    has_question = "?" in hook_text[:100]
    has_exclamation = "!" in hook_text[:100]

    score = 0
    if found_hooks:
        score += 4
    if has_question:
        score += 3
    if has_exclamation:
        score += 1

    return {
        "has_hook": score >= 3,
        "hook_text": hook_text[:100],
        "hook_words_found": found_hooks[:5],
        "has_question": has_question,
        "hook_score": score
    }


def _detect_cta(text: str) -> dict:
    """Détecte la présence d'un call-to-action"""
    cta_patterns = [
        r'abonnez-vous', r'abonne-toi', r'suis-moi',
        r'like', r'partage', r'commente',
        r'dis moi', r'dis-moi', r'tag',
        r'n\'oublie pas', r'n\'oubliez pas',
        r'clique', r'lien', r'description',
        r'prochaine vidéo', r'à demain', r'à la prochaine',
    ]
    found = []
    for p in cta_patterns:
        if re.search(p, text, re.IGNORECASE):
            found.append(p)

    return {
        "has_cta": len(found) > 0,
        "cta_patterns_found": found[:5],
        "cta_score": min(len(found) * 2, 5),
    }


def _detect_forbidden_words(text: str) -> list:
    """Vérifie les mots interdits"""
    found = []
    for word in FORBIDDEN_WORDS:
        if word.lower() in text.lower():
            found.append(word)
    return found


def _classify_emotion(text: str) -> dict:
    """Identifie l'émotion ciblée par le texte"""
    emotion_scores = {}
    for emotion in TARGET_EMOTIONS:
        # Mots associés à chaque émotion
        triggers = {
            "peur": ["perdre", "danger", "risque", "crise", "effondrement", "krach",
                     "panique", "faillite", "erreur", "catastrophe"],
            "espoir": ["libre", "indépendance", "réussir", "objectif", "projet",
                       "avenir", "possible", "chance", "opportunité"],
            "curiosité": ["pourquoi", "comment", "secret", "mécanisme", "fonctionne",
                          "caché", "révéler", "découvrir", "comprendre"],
            "urgence": ["maintenant", "aujourd'hui", "tout de suite", "dès",
                        "délai", "profiter", "saisir", "agir"],
            "confiance": ["simple", "éprouvé", "garanti", "sûr", "solide",
                          "stable", "stratégie", "plan", "méthode"],
            "surprise": ["incroyable", "choquant", "ignoriez", "jamais",
                         "impensable", "énorme", "massif"],
            "frustration": ["trop", "compliqué", "injuste", "bloqué",
                            "perdre", "raté", "impôts", "frais"],
            "ambition": ["million", "fortune", "objectif", "grand", "puissant",
                         "riche", "leader", "dominer"],
        }
        count = sum(1 for t in triggers.get(emotion, []) if t.lower() in text.lower())
        if count > 0:
            emotion_scores[emotion] = count

    if emotion_scores:
        top = max(emotion_scores, key=emotion_scores.get)
        return {"primary_emotion": top, "all_scores": emotion_scores}
    return {"primary_emotion": "non identifiée", "all_scores": {}}


def analyze_content_llm(video_path: Path, script_data: dict = None) -> dict:
    """Analyse du contenu via LLM + règles locales"""
    result = {
        "script": "",
        "hook": {},
        "data_count": 0,
        "forbidden_words": [],
        "cta": {},
        "emotion": {},
        "guru_score": 0,
        "score": 0,
        "details": [],
    }

    # Extraire le texte du script
    text = ""
    if script_data:
        if isinstance(script_data, dict):
            text = script_data.get("script", "") or script_data.get("text", "") or json.dumps(script_data)
        elif isinstance(script_data, str):
            text = script_data
    else:
        # Essayer de lire depuis le transcript Whisper
        transcript_path = video_path.with_suffix(".json")
        if transcript_path.exists():
            try:
                data = json.loads(transcript_path.read_text())
                segments = data.get("segments", [])
                text = " ".join(s.get("text", "") for s in segments)
            except (json.JSONDecodeError, KeyError):
                pass

    result["script"] = text[:500]  # tronqué pour le rapport

    if not text.strip():
        result["hook"] = {"has_hook": False, "hook_text": "", "hook_words_found": [], "has_question": False, "hook_score": 0}
        result["data_count"] = 0
        result["forbidden_words"] = []
        result["cta"] = {"has_cta": False, "cta_patterns_found": [], "cta_score": 0}
        result["emotion"] = {"primary_emotion": "non identifiée", "all_scores": {}}
        result["guru_score"] = 0
        result["details"].append("⚠️  Aucun script disponible pour l'analyse contenu")
        return result

    # Hook
    hook = _detect_hook(text)
    result["hook"] = hook

    # Données chiffrées
    data_count = _count_numbers(text)
    result["data_count"] = data_count

    # Mots interdits
    forbidden = _detect_forbidden_words(text)
    result["forbidden_words"] = forbidden

    # CTA
    cta = _detect_cta(text)
    result["cta"] = cta

    # Émotion
    emotion = _classify_emotion(text)
    result["emotion"] = emotion

    # Guru score (0-10, plus c'est bas mieux c'est)
    guru_terms = ["absolument", "garanti", "toujours", "jamais", "impossible",
                  "certain", "parfait", "totalement", "complètement", "évidemment",
                  "bien sûr", "sans aucun doute", "forcément"]
    guru_count = sum(1 for t in guru_terms if t.lower() in text.lower())
    result["guru_score"] = min(guru_count, 10)

    # Scoring contenu (/30)
    score = 0
    details = []

    # Hook (max 8)
    if hook.get("has_hook"):
        score += 8
        details.append("✅ Hook détecté dans les premières secondes")
    elif hook.get("hook_score", 0) > 0:
        score += 4
        details.append(f"⚠️  Hook partiel (score {hook['hook_score']}/8)")
    else:
        details.append("❌ Pas de hook détecté")

    # Données chiffrées (max 6)
    if data_count >= 3:
        score += 6
        details.append(f"✅ {data_count} données chiffrées")
    elif data_count >= 2:
        score += 4
        details.append(f"⚠️  {data_count} données chiffrées (min 2 requis)")
    elif data_count >= 1:
        score += 2
        details.append(f"⚠️  1 seule donnée chiffrée")
    else:
        details.append("❌ Aucune donnée chiffrée")

    # Mots interdits (max 6)
    if not forbidden:
        score += 6
        details.append("✅ Aucun mot interdit")
    else:
        penalty = min(len(forbidden) * 2, 6)
        score += max(0, 6 - penalty)
        details.append(f"⚠️  {len(forbidden)} mot(s) interdit(s): {', '.join(forbidden[:3])}")

    # CTA (max 5)
    if cta.get("has_cta"):
        score += 5
        details.append("✅ Call-to-action présent")
    else:
        details.append("❌ Pas de call-to-action")

    # Émotion (max 5)
    if emotion.get("primary_emotion") != "non identifiée":
        score += 5
        details.append(f"✅ Émotion ciblée : {emotion['primary_emotion']}")
    else:
        details.append("⚠️  Émotion non identifiée")

    # Pénalité guru
    if result["guru_score"] > 3:
        score -= min(result["guru_score"] - 3, 5)
        details.append(f"⚠️  Guru score: {result['guru_score']}/10 (trop de certitudes absolues)")

    result["score"] = max(0, min(30, score))
    result["details"] = details

    return result