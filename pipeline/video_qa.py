#!/usr/bin/env python3
"""
🎬 Video QA — Pré-validation qualité vidéo avant upload
Inspiré de OpenMontage CompositionValidator + CompositionValidator.
Vérifie : black frames, silence audio, freeze frames, résolution, bitrate.

Usage:
  from video_qa import run_video_qa
  report = run_video_qa("/path/to/video.mp4")
"""

import json, subprocess, re, logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("video-qa")

from pipeline.pipeline_config import load_config
_CONFIG = load_config()
_VIDEO_CFG = _CONFIG.get("video", {})
_QA_CFG = _CONFIG.get("qa", {})
EXPECTED_WIDTH, EXPECTED_HEIGHT = map(int, _VIDEO_CFG.get("resolution", "1080x1920").split("x"))

# Seuils
BLACK_FRAME_THRESHOLD = 0.1        # 10% de luminance max pour considérer "black"
SILENCE_THRESHOLD_DB = -50.0       # dB seuil silence
FREEZE_THRESHOLD = 0.004           # variation max entre frames pour freeze
MAX_BLACK_PCT = float(_QA_CFG.get("max_black_pct", 5.0))                # % max toléré de black frames
MAX_SILENCE_PCT = float(_QA_CFG.get("max_silence_pct", 15.0))             # filet de securite sur le TOTAL
MAX_SILENCE_EVENT_S = float(_QA_CFG.get("max_silence_event_s", 2.0))    # duree max d un TROU de silence
INTRO_GRACE_S = float(_QA_CFG.get("intro_grace_s", 3.5))                # carton de titre = silence normal au debut
MIN_DURATION_S = float(_VIDEO_CFG.get("min_duration_s", 60.0))               # durée minimale acceptable
MAX_DURATION_S = float(_VIDEO_CFG.get("max_duration_s", 62.0))             # durée maximale
MIN_BITRATE = int(_QA_CFG.get("min_bitrate", 300000))              # bitrate vidéo min
MAX_BLACK_DURATION_S = 4.0        # durée max d'un black frame continu


def _run_ffmpeg_cmd(cmd: list, timeout: int = 60) -> tuple[str, str]:
    """Run ffmpeg/ffprobe and return (stdout, stderr)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        error = proc.stderr.strip()[-1000:] or f"Code retour {proc.returncode}"
        raise RuntimeError(f"Commande QA échouée: {error}")
    return proc.stdout, proc.stderr


def check_black_frames(video_path: str, timeout: int = 60) -> dict:
    """
    Détecte les black frames via le filtre blackdetect de FFmpeg.
    Retourne {black_detected: bool, black_duration_total, black_pct, frames: [...]}
    """
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"blackdetect=d={BLACK_FRAME_THRESHOLD}:pic_th=0.98",
        "-f", "null", "-",
    ]
    _, stderr = _run_ffmpeg_cmd(cmd, timeout)

    black_events = []
    total_black = 0.0
    for line in stderr.split("\n"):
        m = re.search(r"black_duration:([\d.]+)", line)
        if m:
            dur = float(m.group(1))
            black_events.append({"duration": dur, "detail": line.strip()})
            total_black += dur

    # Get total duration for percentage
    duration = _get_duration(video_path)
    pct = (total_black / duration * 100) if duration > 0 else 0

    return {
        "check": "black_frames",
        "passed": total_black <= MAX_BLACK_DURATION_S and pct <= MAX_BLACK_PCT,
        "total_black_seconds": round(total_black, 2),
        "max_continuous_black": round(max([e["duration"] for e in black_events], default=0), 2),
        "black_pct": round(pct, 1),
        "events": black_events[:20],
    }


def check_silence(video_path: str, timeout: int = 60) -> dict:
    """
    Détecte les segments silencieux via silencedetect.
    """
    cmd = [
        "ffmpeg", "-i", video_path,
        "-af", f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d=0.5",
        "-f", "null", "-",
    ]
    _, stderr = _run_ffmpeg_cmd(cmd, timeout)

    silence_events = []
    total_silence = 0.0
    current_start = None

    for line in stderr.split("\n"):
        start_m = re.search(r"silence_start:\s*([\d.]+)", line)
        end_m = re.search(r"silence_end:\s*([\d.]+)", line)

        if start_m:
            current_start = float(start_m.group(1))
        elif end_m and current_start is not None:
            end = float(end_m.group(1))
            dur = end - current_start
            silence_events.append({"start": round(current_start, 2), "end": round(end, 2), "duration": round(dur, 2)})
            total_silence += dur
            current_start = None

    duration = _get_duration(video_path)
    pct = (total_silence / duration * 100) if duration > 0 else 0

    # Le total de silence ne discrimine pas : le silence structurel (carton de titre +
    # transitions entre segments) vaut deja 8.5 a 9.3% sur les videos saines, contre un
    # seuil a 10%. Mesures du 27/09/2026 : videos saines = aucun evenement > 0.8s apres
    # l intro ; video defaut = trou de 3.0s apres le hook (total 13.0%). On juge donc le
    # TROU, le total restant un filet de securite.
    longest = max(silence_events, key=lambda e: e["duration"], default=None)
    long_holes = [
        e for e in silence_events
        if e["duration"] > MAX_SILENCE_EVENT_S and e["start"] >= INTRO_GRACE_S
    ]
    detail = "total %.1f%% ; plus long trou %.1fs a %.1fs" % (
        pct,
        longest["duration"] if longest else 0.0,
        longest["start"] if longest else 0.0,
    )
    return {
        "check": "silence",
        "passed": (pct <= MAX_SILENCE_PCT) and not long_holes,
        "detail": detail,
        "total_silence_seconds": round(total_silence, 2),
        "silence_pct": round(pct, 1),
        "longest_event_s": round(longest["duration"], 2) if longest else 0.0,
        "long_holes": long_holes,
        "events": silence_events[:20],
    }


def check_resolution_bitrate(video_path: str) -> dict:
    """
    Vérifie résolution, codec, bitrate via ffprobe.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name,bit_rate",
        "-of", "json",
        video_path,
    ]
    stdout, _ = _run_ffmpeg_cmd(cmd, 15)

    try:
        data = json.loads(stdout)
        stream = data.get("streams", [{}])[0]
    except (json.JSONDecodeError, IndexError):
        return {"check": "resolution", "passed": False, "error": "ffprobe parse failed"}

    width = stream.get("width", 0)
    height = stream.get("height", 0)
    codec = stream.get("codec_name", "unknown")
    bitrate_str = stream.get("bit_rate", "0")
    bitrate = int(bitrate_str) if bitrate_str and bitrate_str.isdigit() else 0

    is_horizontal = width > height
    is_short = min(width, height) < 720
    issues = []
    if width != EXPECTED_WIDTH or height != EXPECTED_HEIGHT:
        issues.append(f"Résolution incorrecte: {width}x{height}, attendu {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")

    if width < 720 or height < 720:
        issues.append(f"Résolution basse: {width}x{height}")
    if bitrate <= 0:
        issues.append("Bitrate vidéo absent ou non mesurable")
    elif bitrate < MIN_BITRATE:
        issues.append(f"Bitrate bas: {bitrate//1000}kbps")
    if codec not in ("h264", "hevc", "vp9", "av1"):
        issues.append(f"Codec non standard: {codec}")

    return {
        "check": "resolution",
        "passed": len(issues) == 0,
        "width": width,
        "height": height,
        "codec": codec,
        "bitrate_kbps": bitrate // 1000,
        "is_horizontal": is_horizontal,
        "is_short": is_short,
        "issues": issues,
    }


def check_frame_integrity(video_path: str, timeout: int = 30) -> dict:
    """
    Vérifie l'intégrité des frames (freeze, corruption).
    """
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"freezedetect=n={FREEZE_THRESHOLD}:d=1",
        "-f", "null", "-",
    ]
    _, stderr = _run_ffmpeg_cmd(cmd, timeout)

    freeze_events = []
    total_freeze = 0.0
    for line in stderr.split("\n"):
        m = re.search(r"freeze_duration:([\d.]+)", line)
        if m:
            dur = float(m.group(1))
            freeze_events.append({"duration": dur, "detail": line.strip()})
            total_freeze += dur

    return {
        "check": "frame_integrity",
        "passed": total_freeze < 1.0,
        "total_freeze_seconds": round(total_freeze, 2),
        "events": freeze_events[:10],
    }


def check_audio_levels(video_path: str, timeout: int = 30) -> dict:
    """
    Vérifie les niveaux audio via le filtre volumedetect de FFmpeg.
    Vérifie que max_volume < 0dB (pas de clipping) ET mean_volume > -20dB.
    """
    cmd = [
        "ffmpeg", "-i", video_path,
        "-af", "volumedetect",
        "-f", "null", "-",
    ]
    _, stderr = _run_ffmpeg_cmd(cmd, timeout)

    mean_volume = None
    max_volume = None
    for line in stderr.split("\n"):
        mean_m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", line)
        max_m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", line)
        if mean_m:
            mean_volume = float(mean_m.group(1))
        if max_m:
            max_volume = float(max_m.group(1))

    issues = []
    if mean_volume is None or max_volume is None:
        issues.append("Piste audio absente ou niveaux audio non mesurables")
    if max_volume is not None and max_volume >= 0:
        issues.append(f"Clipping détecté (max_volume={max_volume}dB)")
    if mean_volume is not None and mean_volume < -20:
        issues.append(f"Volume trop bas (mean_volume={mean_volume}dB, attendu > -20dB)")

    return {
        "check": "audio_levels",
        "passed": len(issues) == 0,
        "mean_volume_db": round(mean_volume, 1) if mean_volume is not None else None,
        "max_volume_db": round(max_volume, 1) if max_volume is not None else None,
        "issues": issues,
    }


def check_av_sync(video_path: str, timeout: int = 30) -> dict:
    """
    Vérifie la synchro audio/vidéo en comparant les timestamps des deux flux.
    Delta entre le premier audio et le premier vidéo timestamp < 1s = OK.
    """
    try:
        # Récupérer le premier PTS de la vidéo
        v_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "packet=pts_time",
            "-read_intervals", "%+#1",
            "-of", "csv=p=0",
            video_path,
        ]
        v_out, _ = _run_ffmpeg_cmd(v_cmd, timeout)
        first_v_pts = None
        for line in v_out.strip().split("\n"):
            line = line.strip()
            if line and line != "N/A":
                try:
                    first_v_pts = float(line.rstrip(","))
                    break
                except ValueError:
                    continue

        # Récupérer le premier PTS de l'audio
        a_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "packet=pts_time",
            "-read_intervals", "%+#1",
            "-of", "csv=p=0",
            video_path,
        ]
        a_out, _ = _run_ffmpeg_cmd(a_cmd, timeout)
        first_a_pts = None
        for line in a_out.strip().split("\n"):
            line = line.strip()
            if line and line != "N/A":
                try:
                    first_a_pts = float(line.rstrip(","))
                    break
                except ValueError:
                    continue

        if first_v_pts is not None and first_a_pts is not None:
            delta = abs(first_v_pts - first_a_pts)
            return {
                "check": "av_sync",
                "passed": delta < 1.0,
                "first_video_pts_s": round(first_v_pts, 3),
                "first_audio_pts_s": round(first_a_pts, 3),
                "delta_s": round(delta, 3),
                "issues": [] if delta < 1.0 else [f"Décalage A/V de {delta:.3f}s (> 1s)"],
            }

        return {
            "check": "av_sync",
            "passed": False,
            "first_video_pts_s": first_v_pts,
            "first_audio_pts_s": first_a_pts,
            "delta_s": None,
            "issues": [],
            "not_checked": True,
            "detail": "Impossible de lire les PTS — synchro non vérifiée"
        }

    except Exception as e:
        return {
            "check": "av_sync",
            "passed": False,
            "issues": [f"Erreur de vérification A/V: {e}"],
            "not_checked": True,
        }


def _get_duration(video_path: str) -> float:
    """Récupère la durée de la vidéo en secondes."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        video_path,
    ]
    stdout, _ = _run_ffmpeg_cmd(cmd, 10)
    try:
        return float(stdout.strip())
    except (ValueError, TypeError):
        return 0.0


def run_video_qa(video_path: str, timeout: int = 120) -> dict:
    """
    Exécute la QA complète sur une vidéo.
    
    Returns:
        dict: {
            "passed": bool,
            "score": int (0-100),
            "checks": [...],
            "summary": str
        }
    """
    path = Path(video_path)
    if not path.exists():
        return {"passed": False, "score": 0, "summary": f"Fichier introuvable: {video_path}", "checks": []}

    duration = _get_duration(video_path)
    log.info(f"🎬 Video QA: {path.name} ({duration:.1f}s)")

    checks = []

    # 1. Durée
    duration_ok = MIN_DURATION_S <= duration <= MAX_DURATION_S
    checks.append({
        "check": "duration",
        "passed": duration_ok,
        "duration_s": round(duration, 1),
        "detail": f"{duration:.1f}s (limites: {MIN_DURATION_S}-{MAX_DURATION_S}s)",
    })

    # 2. Résolution
    checks.append(check_resolution_bitrate(video_path))

    # 3. Black frames
    checks.append(check_black_frames(video_path, timeout))

    # 4. Silence
    checks.append(check_silence(video_path, timeout))

    # 5. Freeze frames
    checks.append(check_frame_integrity(video_path, timeout))

    # 6. Audio levels (volumedetect)
    checks.append(check_audio_levels(video_path, timeout))

    # 7. A/V sync
    checks.append(check_av_sync(video_path, timeout))

    # Score (100 = parfait)
    checked = checks
    passed_checks = sum(1 for c in checked if c.get("passed", False))
    total_checks = len(checked)
    score = int((passed_checks / total_checks) * 100) if total_checks > 0 else 0

    # Résumé
    failed = [c["check"] for c in checked if not c.get("passed", False)]
    if failed:
        summary = f"⚠️ {score}/100 — Échecs: {', '.join(failed)}"
    else:
        summary = f"✅ {score}/100 — Tout OK"

    return {
        "passed": bool(checked) and all(c.get("passed", False) for c in checked),
        "score": score,
        "duration_s": round(duration, 1),
        "summary": summary,
        "checks": checks,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: video_qa.py <video_path>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    report = run_video_qa(sys.argv[1])
    print(json.dumps(report, indent=2, ensure_ascii=False))