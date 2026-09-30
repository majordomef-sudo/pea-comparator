#!/usr/bin/env python3
"""
silence_cutter.py - Silence cutter pré-assembly
Supprime les blancs audio avant composition vidéo.

Utilise ffmpeg silenceremove filter (purpose-built) pour détecter
et couper automatiquement les silences.

Usage:
    python3 silence_cutter.py input.mp4 output.mp4 [--threshold -40dB] [--min-duration 0.5]
"""

import argparse, json, os, shutil, subprocess, sys
from pathlib import Path


def _has_video(input_path: str) -> bool:
    """Vérifie si le fichier contient une piste vidéo."""
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_entries", "stream=codec_type", input_path]
    try:
        probe = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15, check=False
        )
        if probe.returncode != 0:
            print(
                f"[SilenceCutter] ⚠️ ffprobe vidéo échoué: "
                f"{probe.stderr.strip()[-300:]}"
            )
            return False
        data = json.loads(probe.stdout)
        return any(
            stream.get("codec_type") == "video"
            for stream in data.get("streams", [])
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as probe_error:
        print(f"[SilenceCutter] ⚠️ Analyse vidéo impossible: {probe_error}")
        return False


def cut_silence(input_path: str, output_path: str,
                threshold: str = "-40dB", min_duration: float = 0.3,
                keep_first: float = 1.5, keep_last: float = 1.5) -> bool:
    """
    Coupe les silences d'une vidéo via le filtre silenceremove.

    Préserve keep_first/keep_last secondes au début/fin
    (pour ne pas couper l'intro/outro volontaire).

    Retourne True si succès.
    """
    if not os.path.exists(input_path):
        print(f"[SilenceCutter] ❌ Fichier introuvable: {input_path}")
        return False

    # Détecter les silences avec silencedetect
    print(f"[SilenceCutter] Analyse: {input_path} (threshold={threshold}, min_dur={min_duration}s)")

    cmd_detect = [
        "ffmpeg", "-i", input_path, "-af",
        f"silencedetect=noise={threshold}:d={min_duration}",
        "-f", "null", "-"
    ]
    try:
        r = subprocess.run(cmd_detect, capture_output=True, text=True, timeout=300, check=False)
        if r.returncode != 0:
            print(f"[SilenceCutter] ❌ Détection FFmpeg échouée (code {r.returncode}): {r.stderr[-500:]}")
            return False
    except subprocess.TimeoutExpired:
        print("[SilenceCutter] ❌ Timeout")
        return False

    # Parser les silences
    segments = []
    current = {}
    for line in r.stderr.split("\n"):
        line = line.strip()
        if "silence_start:" in line:
            current["start"] = float(line.split("silence_start:")[1].strip())
        elif "silence_end:" in line and "start" in current:
            parts = line.split("silence_end:")
            current["end"] = float(parts[1].split("|")[0].strip())
            try:
                dur_part = line.split("duration:")[1].strip()
                current["duration"] = float(dur_part.split()[0])
            except (IndexError, ValueError):
                current["duration"] = current["end"] - current["start"]
            segments.append(current)
            current = {}

    if not segments:
        print("[SilenceCutter] ✅ Aucun silence - copie directe")
        shutil.copy2(input_path, output_path)
        return True

    # Obtenir la durée totale
    cmd_dur = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_entries", "format=duration", input_path
    ]
    try:
        dur_result = subprocess.run(
            cmd_dur,
            capture_output=True,
            text=True,
            timeout=30, check=False
        )
        if dur_result.returncode != 0:
            raise RuntimeError(
                dur_result.stderr.strip()[-500:]
                or f"code retour {dur_result.returncode}"
            )
        dur_data = json.loads(dur_result.stdout)
        total_dur = float(dur_data["format"]["duration"])
        if total_dur <= 0:
            raise ValueError(f"durée invalide: {total_dur}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError,
            TypeError, ValueError, RuntimeError) as duration_error:
        print(
            f"[SilenceCutter] ❌ Impossible de lire la durée: "
            f"{duration_error}"
        )
        return False

    # Filtrer les silences trop près du début/fin
    filtered = [s for s in segments
                if s["start"] > keep_first and s["end"] < total_dur - keep_last]

    if not filtered:
        print("[SilenceCutter] ✅ Aucun silence retenu (limites début/fin) - copie directe")
        shutil.copy2(input_path, output_path)
        return True

    total_silence = sum(s["duration"] for s in filtered)
    expected_out = total_dur - total_silence
    print(f"[SilenceCutter] 🗑️  {len(filtered)} silences, {total_silence:.1f}s (→ ~{expected_out:.1f}s estimé)")

    # Approche 1: Utiliser atrim avec concat pour couper précisément
    # Générer les trim filters
    has_vid = _has_video(input_path)

    trim_parts_v = []
    trim_parts_a = []
    last_end = 0.0
    
    for s in filtered:
        if s["start"] > last_end + 0.05:
            if has_vid:
                trim_parts_v.append(f"[0:v]trim=start={last_end:.3f}:end={s['start']:.3f},setpts=PTS-STARTPTS[v{len(trim_parts_v)+1}]")
            trim_parts_a.append(f"[0:a]atrim=start={last_end:.3f}:end={s['start']:.3f},asetpts=PTS-STARTPTS[a{len(trim_parts_a)+1}]")
        last_end = s["end"]

    # Dernier segment
    if total_dur > last_end + 0.1:
        if has_vid:
            trim_parts_v.append(f"[0:v]trim=start={last_end:.3f}:end={total_dur:.3f},setpts=PTS-STARTPTS[v{len(trim_parts_v)+1}]")
        trim_parts_a.append(f"[0:a]atrim=start={last_end:.3f}:end={total_dur:.3f},asetpts=PTS-STARTPTS[a{len(trim_parts_a)+1}]")

    if len(trim_parts_a) == 0:
        print("[SilenceCutter] ⚠️ Rien à garder")
        return False

    is_single = len(trim_parts_a) == 1

    if is_single and not has_vid:
        # Audio seul, un passage conservé : appliquer réellement atrim
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", trim_parts_a[0],
            "-map", "[a1]",
        ]
        cmd += _encoding_args(False, output_path)
    elif is_single and has_vid:
        # Single segment with video
        parts = trim_parts_v + trim_parts_a
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", ";".join(parts),
            "-map", "[v1]", "-map", "[a1]",
        ]
        cmd += _encoding_args(has_vid, output_path)
    elif not has_vid:
        # Audio only, multiple segments
        a_labels = "".join(f"[a{i+1}]" for i in range(len(trim_parts_a)))
        filter_str = ";".join(trim_parts_a)
        filter_str += f";{a_labels}concat=n={len(trim_parts_a)}:v=0:a=1[outa]"
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", filter_str,
            "-map", "[outa]",
        ]
        cmd += _encoding_args(False, output_path)
    else:
        # Video + audio, multiple segments
        v_labels = "".join(f"[v{i+1}]" for i in range(len(trim_parts_v)))
        a_labels = "".join(f"[a{i+1}]" for i in range(len(trim_parts_a)))
        filter_str = ";".join(trim_parts_v + trim_parts_a)
        filter_str += f";{v_labels}concat=n={len(trim_parts_v)}:v=1:a=0[outv]"
        filter_str += f";{a_labels}concat=n={len(trim_parts_a)}:v=0:a=1[outa]"
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", filter_str,
            "-map", "[outv]", "-map", "[outa]",
        ]
        cmd += _encoding_args(True, output_path)

    print(f"[SilenceCutter] ✂️  {len(trim_parts_a)} segment(s) → {output_path}")
    try:
        subprocess.run(cmd, check=True, timeout=600, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode()[:500]
        print(f"[SilenceCutter] ❌ Échec: {err}")
        return False
    except subprocess.TimeoutExpired:
        print("[SilenceCutter] ❌ Timeout")
        return False

    # Vérification
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        print("[SilenceCutter] ❌ Fichier de sortie invalide")
        return False

    out_size = os.path.getsize(output_path)
    out_dur = total_dur - total_silence
    print(f"[SilenceCutter] ✅ OK - {out_size/1024:.0f} KB (estimé {out_dur:.1f}s)")
    return True


def _encoding_args(has_video: bool, output_path: str) -> list:
    """Retourne les arguments d'encodage selon le type de fichier."""
    args = []
    if output_path.endswith(".wav"):
        args += ["-c:a", "pcm_s16le"]
    elif output_path.endswith(".mp3"):
        args += ["-c:a", "libmp3lame", "-q:a", "2"]
    else:
        if has_video:
            args += ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]
        args += ["-c:a", "aac", "-b:a", "96k"]
    args.append(output_path)
    return args


def main():
    parser = argparse.ArgumentParser(description="Coupe les silences d'une vidéo")
    parser.add_argument("input", help="Fichier vidéo source")
    parser.add_argument("output", help="Fichier vidéo destination")
    parser.add_argument("--threshold", default="-40dB",
                        help="Seuil de silence (ex: -35dB, -45dB)")
    parser.add_argument("--min-duration", type=float, default=0.3,
                        help="Durée minimale de silence en secondes")
    parser.add_argument("--keep-first", type=float, default=1.5,
                        help="Secondes à préserver au début")
    parser.add_argument("--keep-last", type=float, default=1.5,
                        help="Secondes à préserver à la fin")

    args = parser.parse_args()
    success = cut_silence(args.input, args.output, args.threshold,
                          args.min_duration, args.keep_first, args.keep_last)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()