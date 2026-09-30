"""
Module learning — système d'apprentissage continu

Surveille les scores d'analyse, détecte les patterns récurrents,
génère des leçons pour le pipeline, et applique des correctifs auto.

Fonctions :
- store_analysis() → sauvegarde historique
- detect_patterns() → repère les erreurs récurrentes
- generate_lessons() → produit des leçons pour le prompt LLM
- apply_auto_fixes() → patch la config du pipeline si pattern confirmé
"""

import json, os, re
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

WORKSPACE = Path.home() / ".openclaw" / "workspace"
STATE_DIR = WORKSPACE / "state" / "video_analysis"
HISTORY_FILE = STATE_DIR / "history.json"
PATTERNS_FILE = STATE_DIR / "patterns.json"
LESSONS_FILE = STATE_DIR / "lessons.json"
OVERRIDES_FILE = STATE_DIR / "config_overrides.json"

# Seuil de détection des patterns (occurrences avant alerte)
PATTERN_THRESHOLD = 2  # Alerter après 2 occurrences du même problème


def _ensure_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for f in [HISTORY_FILE, PATTERNS_FILE, LESSONS_FILE, OVERRIDES_FILE]:
        if not f.exists():
            f.write_text("[]" if f != OVERRIDES_FILE else "{}")


# ── STORE ──────────────────────────────────────────────────────────

def store_analysis(video_name: str, report: dict) -> dict:
    """Stocke le résultat d'analyse dans l'historique et met à jour les patterns"""
    _ensure_state()

    entry = {
        "video": video_name,
        "timestamp": report.get("timestamp", datetime.now().isoformat()),
        "score_global": report.get("scores", {}).get("global", 0),
        "scores": report.get("scores", {}),
        "improvements": [imp["action"] for imp in report.get("improvements", [])],
        "category": report.get("category", "?"),
    }

    history = json.loads(HISTORY_FILE.read_text())
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))

    print(f"[LEARNING] Analyse stockée : {video_name} ({entry['score_global']}/100)")

    return entry


# ── PATTERNS ───────────────────────────────────────────────────────

def detect_patterns() -> dict:
    """Analyse l'historique pour détecter des patterns d'échecs récurrents"""
    _ensure_state()

    history = json.loads(HISTORY_FILE.read_text())
    if len(history) < 2:
        return {
            "patterns": [], "trend": None, "weak_modules": {},
            "total_analyzed": len(history),
            "avg_global": history[0]["score_global"] if history else 0,
            "last_5_scores": [h["score_global"] for h in history],
        }

    # Compter les améliorations suggérées récurrentes
    all_improvements = []
    for h in history:
        all_improvements.extend(h.get("improvements", []))

    improvement_counter = Counter(all_improvements)
    recurring = [
        {"pattern": imp, "count": count, "frequency": f"{count}/{len(history)} vidéos"}
        for imp, count in improvement_counter.most_common(10)
        if count >= PATTERN_THRESHOLD
    ]

    # Tendances des scores
    scores = [h.get("score_global", 0) for h in history]
    trend = None
    if len(scores) >= 3:
        recent = scores[-3:]
        if recent[2] > recent[0]:
            trend = "📈 Amélioration"
        elif recent[2] < recent[0]:
            trend = "📉 Dégradation"
        else:
            trend = "➡️ Stable"

    # Patterns par module
    module_scores = defaultdict(list)
    for h in history:
        sc = h.get("scores", {})
        for mod, val in sc.items():
            module_scores[mod].append(val)

    weak_modules = {}
    for mod, vals in module_scores.items():
        avg = sum(vals) / len(vals)
        max_score = {"technical": 30, "content": 30, "audio": 20, "virality": 20}.get(mod, 20)
        ratio = avg / max_score
        if ratio < 0.5:
            weak_modules[mod] = {
                "avg_score": round(avg, 1),
                "max_score": max_score,
                "ratio": f"{ratio:.0%}",
                "videos": len(vals),
            }

    result = {
        "patterns": recurring,
        "trend": trend,
        "weak_modules": weak_modules,
        "total_analyzed": len(history),
        "avg_global": round(sum(scores) / len(scores), 1) if scores else 0,
        "last_5_scores": scores[-5:] if len(scores) >= 5 else scores,
    }

    PATTERNS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result


# ── LESSONS ────────────────────────────────────────────────────────

def generate_lessons() -> list:
    """Génère des leçons apprises à injecter dans le prompt LLM du pipeline"""
    patterns = detect_patterns()
    history = json.loads(HISTORY_FILE.read_text())

    lessons = []

    # Leçon 1 : Problèmes récurrents
    for p in patterns.get("patterns", []):
        lesson = f"⚠️ Problème récurrent ({p['count']}x) : {p['pattern']}"
        if lesson not in lessons:
            lessons.append(lesson)

    # Leçon 2 : Modules faibles
    for mod, data in patterns.get("weak_modules", {}).items():
        emoji = {"technical": "🎬", "content": "📝", "audio": "🔊", "virality": "📈"}.get(mod, "❓")
        lessons.append(
            f"{emoji} Module faible : {mod} (moy. {data['avg_score']}/{data['max_score']})"
        )

    # Leçon 3 : Améliorations qui ont fonctionné
    if history:
        # Trouver la vidéo avec le meilleur score récent
        best = max(history[-5:], key=lambda h: h.get("score_global", 0), default=None)
        worst = min(history[-5:], key=lambda h: h.get("score_global", 0), default=None)
        if best and best["score_global"] >= 70:
            lessons.append(
                f"🏆 Meilleure vidéo : {best.get('video', '?')} ({best['score_global']}/100)"
            )
        if worst and worst["score_global"] < 50:
            lessons.append(
                f"❌ Pire vidéo : {worst.get('video', '?')} ({worst['score_global']}/100)"
            )

    # Leçon 4 : Statistiques globales
    if patterns.get("total_analyzed", 0) > 0:
        lessons.append(
            f"📊 Stats : {patterns['total_analyzed']} vidéos analysées, "
            f"moyenne {patterns['avg_global']}/100, tendance {patterns['trend'] or 'N/A'}"
        )


    # Sauvegarder
    LESSONS_FILE.write_text(json.dumps(lessons, indent=2, ensure_ascii=False))

    return lessons


def _retention_block(min_videos: int = 5, top: int = 3) -> str:
    """Bloc d apprentissage fonde sur la RETENTION reelle (averageViewPercentage).
    Ajoute le 27/09/2026 : le pipeline n apprenait que de scores internes non correles
    a l attention reelle (hook_score : 4 valeurs pour 50 videos, anti-correle aux vues)."""
    path = WORKSPACE / "state" / "retention_scores.json"
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    vids = [v for v in data.get("videos", []) if v.get("fiable") and v.get("retention_score") is not None]
    if len(vids) < min_videos:
        return ""
    ref = data.get("reference", {})
    order = sorted(vids, key=lambda v: -float(v["retention_score"]))
    wins = order[:top]
    loss = [v for v in reversed(order) if float(v["retention_score"]) < 4.0][:top]
    out = "\n--- CE QUI RETIENT VRAIMENT LES SPECTATEURS (YouTube Analytics) ---\n"
    out += "Reference chaine : retention mediane %s %% vu sur %s videos.\n" % (ref.get("median_pct"), ref.get("n"))
    out += "Ouvertures qui ont le MIEUX retenu l audience (imite la STRUCTURE, ne recopie jamais le texte) :\n"
    for v in wins:
        out += "- [%s %% vu] %s\n" % (v.get("avg_pct"), (v.get("opening") or v.get("title", ""))[:120])
    if loss:
        out += "Ouvertures qui ont fait PARTIR l audience (a ne pas reproduire) :\n"
        for v in loss:
            out += "- [%s %% vu] %s\n" % (v.get("avg_pct"), (v.get("opening") or v.get("title", ""))[:120])
    out += "Priorite : retenir au-dela des 15 premieres secondes (42 % des videos perdent l audience avant).\n---\n"
    return out


def get_prompt_lessons() -> str:
    """Retourne les leçons formatées pour injection dans le prompt LLM"""
    lessons = generate_lessons()

    if not lessons:
        return ""

    text = "\n\n--- LEÇONS APPRISES (auto-analysis) ---\n"
    text += "Voici les problèmes récurrents détectés sur les vidéos précédentes. "
    text += "CORRIGE-LES dans le script de cette vidéo :\n"
    for l in lessons:
        text += f"- {l}\n"
    text += "---\n"
    text += _retention_block()

    return text


# ── AUTO-FIXES ─────────────────────────────────────────────────────

def apply_auto_fixes(patterns: dict, pipeline_paths: dict = None) -> list:
    """Applique des correctifs automatiques basés sur les patterns détectés"""
    fixes = []

    if pipeline_paths is None:
        pipeline_paths = {
            "orchestrator": WORKSPACE / "pipeline" / "pipeline_orchestrator.py",
        }

    weak = patterns.get("weak_modules", {})

    # Fix audio si le volume est systématiquement bas
    if "audio" in weak and weak["audio"]["avg_score"] < 10:
        fixes.append({
            "fix": "volume_boost",
            "reason": f"Audio systématiquement faible ({weak['audio']['avg_score']}/20)",
            "action": "Augmenter le gain audio dans scene_composer",
            "applied": False,
        })

    # Fix contenu si hook/CTA manquent
    if "content" in weak and weak["content"]["avg_score"] < 15:
        fixes.append({
            "fix": "prompt_hook_cta",
            "reason": f"Contenu systématiquement faible ({weak['content']['avg_score']}/30)",
            "action": "Renforcer les instructions HOOK + CTA dans le prompt LLM",
            "applied": False,
        })

    recurring = [p.get("pattern", "") for p in patterns.get("patterns", [])]

    if "Réduire les silences dans la voix-off" in recurring:
        fixes.append({
            "fix": "auto_trim_silence",
            "reason": "Pattern récurrent détecté",
            "action": "Réduire automatiquement les silences audio",
            "applied": False,
        })

    if "Augmenter le rythme de coupe" in recurring:
        fixes.append({
            "fix": "faster_cuts",
            "reason": "Pattern récurrent détecté",
            "action": "Réduire la durée moyenne des plans",
            "applied": False,
        })

    if "Ajouter un hook viral en ouverture" in recurring:
        fixes.append({
            "fix": "stronger_hook",
            "reason": "Pattern récurrent détecté",
            "action": "Renforcer automatiquement le hook du segment 1",
            "applied": False,
        })

    # Sauvegarder
    OVERRIDES_FILE.write_text(json.dumps(fixes, indent=2, ensure_ascii=False))

    return fixes


# ── ORCHESTRATION ──────────────────────────────────────────────────

def analyze_and_learn(video_path: str, script_path: str = None) -> dict:
    """Point d'entrée unique : analyse la vidéo, stocke, apprend, retourne le rapport"""
    from analyze_video import analyze  # Import depuis le dossier sibling
    import importlib.util
    import sys

    # Importer analyze_video comme module
    anal_path = WORKSPACE / "skills" / "video-analysis" / "scripts" / "analyze_video.py"
    spec = importlib.util.spec_from_file_location("analyze_video", anal_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["analyze_video"] = mod
    spec.loader.exec_module(mod)

    # Analyser
    report = mod.analyze(video_path, script_path)

    # Stocker
    video_name = Path(video_path).stem
    entry = store_analysis(video_name, report)

    # Patterns + leçons
    patterns = detect_patterns()
    lessons = generate_lessons()

    # Auto-fixes
    fixes = apply_auto_fixes(patterns)

    # Résumé
    report["learning"] = {
        "entry": entry,
        "patterns": patterns.get("patterns", []),
        "lessons": lessons,
        "auto_fixes": fixes,
    }

    return report


# Exécution directe pour test
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(analyze_and_learn(sys.argv[1]))
    else:
        print("Usage: python learning.py <video_path> [script_path]")


# ── INIT ───────────────────────────────────────────────────────────

_ensure_state()