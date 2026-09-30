"""
Module technique — analyse ffprobe d'une vidéo

Métriques :
- Résolution, codec, durée, bitrate
- Black frames detection
- Freeze frames detection
- Score technique /30
"""

import json, subprocess
from pathlib import Path


def analyze_technical(video_path: Path) -> dict:
    """Analyse technique complète via ffprobe"""
    result = {
        "black_frames": [],
        "freeze_frames": [],
        "score": 0,
        "details": [],
    }

    # Infos flux
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(video_path)],
        capture_output=True, text=True
    )
    info = json.loads(probe.stdout)

    streams = {s["codec_type"]: s for s in info.get("streams", [])}
    vstream = streams.get("video", {})
    astream = streams.get("audio", {})
    fmt = info.get("format", {})

    w, h = vstream.get("width", 0), vstream.get("height", 0)
    codec = vstream.get("codec_name", "?").lower()
    duration = float(fmt.get("duration", 0))
    bitrate = int(fmt.get("bit_rate", 0))

    result["resolution"] = f"{w}x{h}"
    result["codec"] = codec
    result["duration"] = round(duration, 2)
    result["bitrate_kbps"] = round(bitrate / 1000) if bitrate else 0
    result["fps"] = vstream.get("r_frame_rate", "?")
    result["audio_codec"] = astream.get("codec_name", "aucun")
    result["audio_channels"] = astream.get("channels", 0)

    # Détection black frames
    black = subprocess.run(
        ["ffmpeg", "-i", str(video_path),
         "-vf", "blackdetect=d=0.5:pix_th=0.10",
         "-f", "null", "-"],
        capture_output=True, text=True
    )
    black_events = []
    for line in black.stderr.split("\n"):
        if "black_duration:" in line:
            parts = line.strip().split()
            for p in parts:
                if p.startswith("black_duration:"):
                    try:
                        dur = float(p.split(":")[1])
                        black_events.append({"duration": round(dur, 2)})
                    except ValueError:
                        pass
    result["black_frames"] = black_events

    # Détection freeze frames
    freeze = subprocess.run(
        ["ffmpeg", "-i", str(video_path),
         "-vf", "freezedetect=d=0.3:n=0.05",
         "-f", "null", "-"],
        capture_output=True, text=True
    )
    freeze_events = []
    for line in freeze.stderr.split("\n"):
        if "freeze_duration:" in line:
            parts = line.strip().split()
            for p in parts:
                if p.startswith("freeze_duration:"):
                    try:
                        dur = float(p.split(":")[1])
                        freeze_events.append({"duration": round(dur, 2)})
                    except ValueError:
                        pass
    result["freeze_frames"] = freeze_events

    # Scoring technique (/30)
    score = 0
    details = []

    # Résolution (max 10)
    if w == 1920 and h == 1080:
        score += 10
        details.append("✅ Résolution 1920×1080")
    elif w == 1080 and h == 1920:
        score += 5
        details.append("⚠️  Résolution portrait 1080×1920")
    else:
        details.append(f"❌ Résolution non standard : {w}x{h}")

    # Durée (max 5)
    if 40 <= duration <= 60:
        score += 5
        details.append(f"✅ Durée {duration}s dans la cible [40-60]")
    elif 30 <= duration <= 80:
        score += 3
        details.append(f"⚠️  Durée {duration}s hors cible idéale")
    else:
        details.append(f"❌ Durée {duration}s trop courte/longue")

    # Codec (max 5)
    if codec in ("h264", "libx264"):
        score += 5
        details.append("✅ Codec H.264")
    elif codec in ("hevc", "h265"):
        score += 3
        details.append("⚠️  Codec H.265 (compatibilité réduite)")
    else:
        details.append(f"⚠️  Codec non standard : {codec}")

    # Black frames (max 5, -1 par occurrence)
    penalty = min(len(black_events), 5)
    score += max(0, 5 - penalty)
    if black_events:
        details.append(f"⚠️  {len(black_events)} black frame(s) (perte de {penalty} pts)")
    else:
        details.append("✅ Pas de black frames")

    # Freeze frames (max 5, -1 par occurrence)
    penalty = min(len(freeze_events), 5)
    score += max(0, 5 - penalty)
    if freeze_events:
        details.append(f"⚠️  {len(freeze_events)} freeze frame(s) (perte de {penalty} pts)")
    else:
        details.append("✅ Pas de freeze frames")

    result["score"] = max(0, min(30, score))
    result["details"] = details

    return result