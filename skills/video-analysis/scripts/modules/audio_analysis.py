"""
Module audio — analyse de la piste audio

Métriques :
- Niveaux audio (RMS, peak, loudness)
- Silences détectés
- Présence voix-off
- Score audio /20
"""

import json, subprocess, re
from pathlib import Path


def analyze_audio(video_path: Path) -> dict:
    """Analyse la piste audio via ffprobe astats + silencedetect"""
    result = {
        "has_audio": False,
        "silences": [],
        "total_silence_duration": 0,
        "audio_metrics": {},
        "score": 0,
        "details": [],
    }

    # Vérifier présence audio
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", str(video_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError(
            f"ffprobe audio échoué: "
            f"{probe.stderr.strip()[-500:] or probe.returncode}"
        )
    try:
        streams = json.loads(probe.stdout).get("streams", [])
    except json.JSONDecodeError as probe_error:
        raise RuntimeError(
            f"Réponse ffprobe audio invalide: {probe.stdout!r}"
        ) from probe_error
    astream = next(
        (
            stream for stream in streams
            if stream.get("codec_type") == "audio"
        ),
        None,
    )

    if not astream:
        result["details"].append("❌ Aucune piste audio")
        return result

    result["has_audio"] = True
    result["audio_codec"] = astream.get("codec_name", "?")
    result["audio_channels"] = astream.get("channels", 0)
    result["sample_rate"] = astream.get("sample_rate", "?")

    # Analyse louder (EBU R128)
    loudnorm = subprocess.run(
        ["ffmpeg", "-i", str(video_path),
         "-af", "loudnorm=I=-16:LRA=11:TP=-1.5:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True, check=False
    )
    if loudnorm.returncode != 0:
        raise RuntimeError(
            f"Analyse LUFS échouée: {loudnorm.stderr.strip()[-500:]}"
        )

    # Extraire les métriques loudnorm
    loud_data = {}
    in_json = False
    json_lines = []
    for line in loudnorm.stderr.split("\n"):
        if "{" in line:
            in_json = True
        if in_json:
            json_lines.append(line)
        if "}" in line and in_json:
            break

    if json_lines:
        try:
            loud_text = "\n".join(json_lines)
            loud_data = json.loads(loud_text)
        except json.JSONDecodeError:
            pass

    result["audio_metrics"]["loudness"] = loud_data.get("input_i", "?")
    result["audio_metrics"]["loudness_range"] = loud_data.get("input_lra", "?")
    result["audio_metrics"]["true_peak"] = loud_data.get("input_tp", "?")

    # Détection silences
    silence = subprocess.run(
        ["ffmpeg", "-i", str(video_path),
         "-af", "silencedetect=d=0.5:n=-30dB",
         "-f", "null", "-"],
        capture_output=True, text=True, check=False
    )
    if silence.returncode != 0:
        raise RuntimeError(
            f"Détection des silences échouée: {silence.stderr.strip()[-500:]}"
        )

    silences = []
    current_start = None

    for line in silence.stderr.split("\n"):
        if "silence_start:" in line:
            match = re.search(r'silence_start:\s*([\d.]+)', line)
            if match:
                current_start = float(match.group(1))
        if "silence_end:" in line:
            match = re.search(r'silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)', line)
            if match:
                end = float(match.group(1))
                dur = float(match.group(2))
                silences.append({"start": round(current_start or 0, 2),
                                 "end": round(end, 2),
                                 "duration": round(dur, 2)})

    result["silences"] = silences[:30]

    # Obtenir la durée totale
    probe2 = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(video_path)],
        capture_output=True, text=True, check=False
    )
    if probe2.returncode != 0:
        raise RuntimeError(
            f"ffprobe durée audio échoué: {probe2.stderr.strip()[-500:]}"
        )
    total_dur = float(
        json.loads(probe2.stdout).get("format", {}).get("duration", 0)
    )

    # Exclure du score les silences éditoriaux du titre et de la fin.
    editorial_silences = [
        event for event in silences
        if (
            event["start"] <= 0.5
            and event["end"] <= 4.5
        ) or (
            total_dur > 0
            and event["start"] >= total_dur - 5.5
        )
    ]
    scored_silences = [
        event for event in silences
        if event not in editorial_silences
    ]

    detected_silence = round(
        sum(event["duration"] for event in silences),
        2
    )
    scored_silence = round(
        sum(event["duration"] for event in scored_silences),
        2
    )

    result["detected_silence_duration"] = detected_silence
    result["editorial_silences"] = editorial_silences
    result["total_silence_duration"] = scored_silence

    # Scoring audio (/20)
    score = 0
    details = []

    # Présence de voix-off, hors silences éditoriaux intentionnels
    silence_ratio = scored_silence / total_dur if total_dur > 0 else 0
    if silence_ratio < 0.2:
        score += 8
        details.append("✅ Voix-off présente sur >80% de la durée utile")
    elif silence_ratio < 0.4:
        score += 5
        details.append(
            f"⚠️  Voix-off présente sur "
            f"{100 - silence_ratio * 100:.0f}% de la durée utile"
        )
    else:
        score += 2
        details.append(
            f"❌ Trop de silence interne ({silence_ratio * 100:.0f}%)"
        )

    # Silences internes supérieurs à 1 seconde
    long_silences = sum(
        1 for event in scored_silences
        if event["duration"] > 1.0
    )
    if long_silences == 0:
        score += 5
        details.append("✅ Pas de silence interne >1s")
    else:
        score += max(0, 5 - long_silences)
        details.append(
            f"⚠️  {long_silences} silence(s) interne(s) >1s"
        )

    if editorial_silences:
        details.append(
            f"ℹ️  {len(editorial_silences)} silence(s) éditorial(aux) "
            f"exclu(s) du score"
        )

    # Volume (vérification basique)
    try:
        loud_val = float(loud_data.get("input_i", -20))
        if -16 <= loud_val <= -3:
            score += 4
            details.append(f"✅ Volume correct ({loud_val:.1f} LUFS)")
        elif -20 <= loud_val <= -1:
            score += 2
            details.append(f"⚠️  Volume à ajuster ({loud_val:.1f} LUFS)")
        else:
            details.append(f"⚠️  Volume anormal ({loud_val:.1f} LUFS)")
    except (ValueError, TypeError):
        score += 2
        details.append("⚠️  Volume non mesurable")

    # Clipping (vérification basique)
    try:
        peak = float(loud_data.get("input_tp", -3))
        if peak > -0.9:
            score += 1
            details.append(f"⚠️  Risque de clipping (peak {peak:.1f} dBTP)")
        else:
            score += 3
            details.append(f"✅ Pas de clipping (peak {peak:.1f} dBTP)")
    except (ValueError, TypeError):
        score += 2
        details.append("⚠️  Clipping non mesurable")

    result["score"] = max(0, min(20, score))
    result["details"] = details

    return result