"""
Module scènes — détection de transitions + extraction scene-change frames

Ajout depuis claude-watch (taoufik123-collab/claude-watch):
  - extract_scene_change_frames() — 1 frame par plan détecté
  - auto_fps() — budget de frames adaptatif à la durée
  - Fallback uniforme quand trop peu de cuts (vidéos statiques)

Métriques :
  - Nombre de transitions (cuts)
  - Durée moyenne des plans
  - Taux de transitions par minute
  - Frames extraites par plan
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def auto_fps(duration_seconds: float, max_frames: int = 100) -> tuple[float, int]:
    """Budget de frames adaptatif — courte durée = dense, longue = cap.

    Même logique que claude-watch frames.py: le coût en tokens est dominé
    par le nombre de frames, donc on scale en fonction de la durée.
    """
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


def analyze_scenes(video_path: Path) -> dict:
    """Détecte les transitions de scènes via ffmpeg scene detection"""
    result = {
        "transitions": [],
        "total_cuts": 0,
        "avg_shot_duration": 0,
        "transitions_per_min": 0,
        "details": [],
    }

    # Obtenir la durée totale
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(video_path)],
        capture_output=True, text=True
    )
    fmt = json.loads(probe.stdout).get("format", {})
    total_duration = float(fmt.get("duration", 0))
    result["duration"] = round(total_duration, 2)

    if total_duration <= 0:
        result["details"].append("⚠️  Durée nulle, impossible d'analyser les scènes")
        return result

    # Détection de scènes via ffmpeg scene filter
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", "select='gt(scene,0.3)',showinfo",
        "-vsync", "vfr", "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    # Extraire les timestamps de transitions
    timestamps = []
    for line in proc.stderr.split("\n"):
        if "pts_time:" in line:
            match = re.search(r'pts_time:([\d.]+)', line)
            if match:
                timestamps.append(float(match.group(1)))

    # Calculer les durées entre transitions
    shot_durations = []
    prev_ts = 0.0
    for ts in sorted(timestamps):
        shot_durations.append(ts - prev_ts)
        prev_ts = ts
    # Dernier plan
    shot_durations.append(total_duration - prev_ts)

    n_cuts = len(timestamps)
    avg_shot = total_duration / (n_cuts + 1) if n_cuts > 0 else total_duration
    trans_per_min = n_cuts / (total_duration / 60) if total_duration > 0 else 0

    result["transitions"] = [round(t, 2) for t in sorted(timestamps)[:50]]
    result["total_cuts"] = n_cuts
    result["avg_shot_duration"] = round(avg_shot, 2)
    result["transitions_per_min"] = round(trans_per_min, 1)
    result["shot_durations"] = [round(d, 2) for d in shot_durations[:20]]

    # Analyse
    details = []
    if n_cuts == 0:
        details.append("⚠️  Aucune transition détectée — vidéo statique")
    elif trans_per_min >= 8:
        details.append(f"✅ Rythme soutenu : {trans_per_min:.1f} transitions/min")
    elif trans_per_min >= 4:
        details.append(f"⚠️  Rythme modéré : {trans_per_min:.1f} transitions/min")
    else:
        details.append(f"⚠️  Rythme lent : {trans_per_min:.1f} transitions/min")

    if 3 <= avg_shot <= 7:
        details.append(f"✅ Durée plan moyenne idéale : {avg_shot:.1f}s")
    elif 2 <= avg_shot <= 10:
        details.append(f"⚠️  Durée plan moyenne acceptable : {avg_shot:.1f}s")
    else:
        details.append(f"⚠️  Durée plan moyenne extrême : {avg_shot:.1f}s")

    result["details"] = details

    return result


def extract_scene_change_frames(
    video_path: Path,
    out_dir: Path,
    scene_threshold: float = 0.3,
    resolution: int = 512,
    max_frames: int = 100,
    uniform_fallback_min: int = 10,
) -> list[dict]:
    """Extrait UNE frame par plan détecté (scene-change), pas N/secondes.

    Adapté de claude-watch frames.py::extract_scene_change().

    Avantage vs extraction uniforme:
      - Coût token constant quelle que soit la durée (borné par nombre de cuts)
      - Capture chaque changement visuel significatif
      - Pas de frames redondantes d'un même plan

    Fallback: si trop peu de cuts (< uniform_fallback_min), passe en
    échantillonnage uniforme (vidéos statiques = talking heads).

    Note ffmpeg:
      subprocess.run liste = pas de shell, donc pas besoin de quotes.
      Les virgules dans l'expression select doivent être échappées avec
      \\, (backslash + virgule) pour que ffmpeg les interprète comme
      des virgules littérales et non des séparateurs de filtres.
    """
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg requis.")

    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("scene_*.jpg"):
        f.unlink()

    # Échapper les virgules pour ffmpeg: \,
    bs_comma = "\\,"
    select_expr = f"eq(n{bs_comma}0)+gt(scene{bs_comma}{scene_threshold})"

    output_pattern = str(out_dir / "scene_%04d.jpg")

    # Pas de quotes autour de select= car subprocess n'a pas de shell
    vf = f"select={select_expr},metadata=mode=print:file=-,scale={resolution}:-2"

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video_path.resolve()),
        "-vf", vf,
        "-vsync", "vfr",
        "-frames:v", str(max_frames),
        "-q:v", "4",
        output_pattern,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Scene-change extraction échouée: %s", result.stderr.strip())
        return []

    # Récupérer les pts_time des frames extraites
    pts_times: list[float] = []
    for stream in (result.stdout, result.stderr):
        for line in stream.splitlines():
            line = line.strip()
            if "pts_time" in line:
                for tok in line.split():
                    if tok.startswith("pts_time:"):
                        try:
                            pts_times.append(float(tok.split(":", 1)[1]))
                        except ValueError:
                            pass
                    elif tok.startswith("pts_time="):
                        try:
                            pts_times.append(float(tok.split("=", 1)[1]))
                        except ValueError:
                            pass

    frames = sorted(out_dir.glob("scene_*.jpg"))

    # Fallback: trop peu de frames = vidéo statique → passage en uniforme
    if len(frames) < uniform_fallback_min:
        logger.info("Trop peu de cuts (%d), fallback extraction uniforme", len(frames))
        for f in frames:
            f.unlink()
        fps, target = auto_fps(_get_duration(video_path), max_frames=max_frames)
        return _extract_uniform(video_path, out_dir, fps, resolution, target)

    offset = 0.0
    if len(pts_times) < len(frames):
        pts_times += [0.0] * (len(frames) - len(pts_times))

    return [
        {
            "index": i,
            "timestamp": round(offset + pts_times[i], 2),
            "path": str(p),
            "type": "scene-change",
        }
        for i, p in enumerate(frames)
    ]


def _get_duration(video_path: Path) -> float:
    """Retourne la durée de la vidéo en secondes."""
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(video_path)],
        capture_output=True, text=True,
    )
    data = json.loads(probe.stdout or "{}").get("format", {})
    return float(data.get("duration", 0))


def _extract_uniform(
    video_path: Path,
    out_dir: Path,
    fps: float,
    resolution: int,
    max_frames: int,
) -> list[dict]:
    """Extraction uniforme de fallback (vidéo statique)."""
    output_pattern = str(out_dir / "scene_%04d.jpg")
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video_path.resolve()),
        "-vf", f"fps={fps},scale={resolution}:-2",
        "-frames:v", str(max_frames),
        "-q:v", "4",
        output_pattern,
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    frames = sorted(out_dir.glob("scene_*.jpg"))
    return [
        {
            "index": i,
            "timestamp": round(i / fps if fps > 0 else 0, 2),
            "path": str(p),
            "type": "uniform-fallback",
        }
        for i, p in enumerate(frames)
    ]