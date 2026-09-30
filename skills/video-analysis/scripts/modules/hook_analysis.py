"""
Module Hook Microscope — analyse dense 0-10s des vidéos pipeline

Adapté de claude-watch (taoufik123-collab/claude-watch) — hook.py + frames.py
Apporte :
  - Extraction à 2 fps sur les 10 premières secondes
  - Transcription word-level Whisper (alignement mot → frame)
  - Score de hook et pattern détecté

Les 10 premières secondes décident de la rétention. Ce module les traite
avec une densité 10× supérieure au scan normal.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

HOOK_DURATION = 10.0
HOOK_FPS = 2.0
MAX_HOOK_FRAMES = 25


def auto_fps(duration_seconds: float, max_frames: int = 100) -> tuple[float, int]:
    """Budget de frames adaptatif — courte durée = dense, longue = cap."""
    if duration_seconds <= 0:
        return 1.0, 1
    if duration_seconds <= 30:
        target = min(max_frames, max(12, int(round(duration_seconds))))
    elif duration_seconds <= 60:
        target = min(max_frames, 40)
    elif duration_seconds <= 180:
        target = min(max_frames, 60)
    elif duration_seconds <= 600:
        target = min(max_frames, 80)
    else:
        target = max_frames
    fps = min(target / duration_seconds, 2.0)
    return fps, min(max_frames, max(1, int(round(fps * duration_seconds))))


def extract_frames(
    video_path: str,
    out_dir: Path,
    fps: float = HOOK_FPS,
    resolution: int = 512,
    max_frames: int = MAX_HOOK_FRAMES,
    start_seconds: float = 0.0,
    end_seconds: float = HOOK_DURATION,
) -> list[dict]:
    """Extrait les frames du hook via ffmpeg."""
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg requis pour le hook microscope.")

    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("frame_*.jpg"):
        f.unlink()

    output_pattern = str(out_dir / "frame_%04d.jpg")
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start_seconds:.3f}",
        "-to", f"{end_seconds:.3f}",
        "-i", str(Path(video_path).resolve()),
        "-vf", f"fps={fps},scale={resolution}:-2",
        "-frames:v", str(max_frames),
        "-q:v", "4",
        output_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("Échec extraction frames hook: %s", result.stderr.strip())
        return []

    frames = sorted(out_dir.glob("frame_*.jpg"))
    offset = start_seconds
    return [
        {"index": i, "timestamp": round(offset + (i / fps if fps > 0 else 0), 2),
         "path": str(p)}
        for i, p in enumerate(frames)
    ]


def transcribe_hook(
    video_path: str,
    out_dir: Path,
) -> dict:
    """Transcrit les 10 premières secondes avec timestamps word-level.

    Utilise ffmpeg pour extraire l'audio puis appelle le script whisper
    du pipeline si disponible. Renvoie segments et mots alignés.
    """
    result = {"words": [], "segments": [], "text": ""}

    if shutil.which("ffmpeg") is None:
        return result

    hook_audio = out_dir / "hook_audio.mp3"
    try:
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(Path(video_path).resolve()),
            "-vn", "-acodec", "libmp3lame", "-ar", "16000",
            "-ac", "1", "-b:a", "64k",
            "-t", str(HOOK_DURATION),
            str(hook_audio.resolve()),
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.warning("Extraction audio hook échouée: %s", e.stderr)
        return result

    # Essai de transcription via whisper si disponible
    # Utilisation du package whisper installe"whisper.py"
    import importlib.util; spec = importlib.util.find_spec("whisper"); whisper_script = Path(spec.origin) if spec and spec.origin else Path("/nonexistent")
    if not whisper_script.exists():
        logger.debug("Pas de module whisper disponible, transcription hook sautée")
        return result

    try:
        sys.path.insert(0, str(whisper_script.parent))
        import whisper as whisper_pkg
        model = whisper_pkg.load_model("base")
        transcribe_result = model.transcribe(str(hook_audio), word_timestamps=True, language="fr")
        segments = transcribe_result.get("segments", [])
        result["segments"] = segments
        # Construction des mots avec timestamps si disponible
        words = []
        for seg in segments:
            if isinstance(seg, dict) and "words" in seg:
                words.extend(seg["words"])
            elif isinstance(seg, dict) and "text" in seg:
                words.append({
                    "word": seg["text"],
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 1),
                })
        result["words"] = words
        result["text"] = " ".join(
            s.get("text", "") for s in segments if isinstance(s, dict)
        )
    except Exception as e:
        logger.warning("Transcription hook échouée: %s", e)

    return result


def analyze_hook(
    video_path: str,
    out_dir: Path,
    full_duration: float = 0.0,
) -> dict:
    """Analyse complète du hook 0-10s.

    Args:
        video_path: Chemin vers la vidéo
        out_dir: Répertoire de sortie
        full_duration: Durée totale (pour décider si l'analyse est utile)

    Returns:
        dict avec frames, transcription, score et analyse
    """
    # Skip si vidéo trop courte (< 30s, pas de hook à analyser)
    if 0 < full_duration < 30:
        return {
            "ran": False,
            "reason": "vidéo <30s, pas d'analyse hook séparée",
            "frames": [], "words": [], "segments": [], "text": "",
            "hook_score": None, "hook_pattern": None,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    hook_dir = out_dir / "hook_microscope"

    # 1. Extraction frames denses (2 fps)
    frames = extract_frames(video_path, hook_dir)

    # 2. Transcription word-level
    transcript = transcribe_hook(video_path, out_dir)

    # 3. Analyse heuristique du pattern de hook
    text = transcript.get("text", "")
    hook_pattern = _detect_hook_pattern(text, frames)
    hook_score = _score_hook(text, frames)

    return {
        "ran": True,
        "frames": frames,
        "words": transcript.get("words", []),
        "segments": transcript.get("segments", []),
        "text": text,
        "hook_score": hook_score,
        "hook_pattern": hook_pattern,
        "frame_count": len(frames),
    }


def _detect_hook_pattern(text: str, frames: list[dict]) -> str | None:
    """Détecte le pattern de hook utilisé (question, chiffre choc, etc.)."""
    if not text:
        return None

    text_lower = text.lower()

    # Patterns de hook typiques YouTube finance
    patterns = [
        ("question", any(text_lower.startswith(q) for q in
                         ["est-ce que", "quoi", "comment", "pourquoi",
                          "quel", "quelle", "vous", "tu veux", "sais-tu"])),
        ("chiffre_choc", any(c in text for c in ["%", "€", "$", "million",
                                                  "milliard", "fois", "000"])),
        ("contraire", any(c in text_lower for c in
                          ["ne faites pas", "erreur", "fausse", "évitez",
                           "arrêtez", "pire", "catastrophe"])),
        ("promesse", any(c in text_lower for c in ["va changer", "découvrez",
                                                    "révèle", "secret",
                                                    "personne ne"])),
        ("urgence", any(c in text_lower for c in ["maintenant",
                                                   "avant qu'il", "trop tard",
                                                   "urgence"])),
    ]

    matched = [name for name, ok in patterns if ok]
    if matched:
        return matched[0]

    # Fallback: nombre de frames en 10s → rythme visuel
    if len(frames) >= 15:
        return "montage_rapide"
    elif len(frames) >= 8:
        return "intro_parlee"

    return "standard"


def _score_hook(text: str, frames: list[dict]) -> float | None:
    """Score heuristique du hook sur 10."""
    if not text and not frames:
        return None

    score = 5.0  # baseline

    # Texte présent
    if text:
        score += 1.0
        # Hook court et punchy
        if len(text.split()) <= 15:
            score += 1.0
        # Question = engagement
        if "?" in text:
            score += 1.0
        # Chiffres = autorité
        if any(c in text for c in ["%", "€", "$", "million"]):
            score += 1.0

    # Rythme visuel
    if len(frames) >= 15:  # changement visuel fréquent
        score += 1.0
    elif len(frames) >= 8:
        score += 0.5

    return min(10.0, round(score, 1))