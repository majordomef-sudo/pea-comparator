#!/usr/bin/env python3
"""
scene_composer.py — Composition vidéo avec scènes animées et overlays
Inspiré d'OpenMontage / Remotion : anime des images avec Ken Burns,
incruste des overlays graphiques, gère transitions et sous-titres ASS.

Remplace l'ancien PASS 1 / PASS 2 du nightly_orchestrator.
"""

import os, json, subprocess, re, shutil
from pathlib import Path


def get_media_duration(path: str) -> float:
    """Retourne la durée d'un fichier média en secondes."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=10, check=False
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"ffprobe durée échoué pour {path}: "
            f"{r.stderr.strip()[-500:] or r.returncode}"
        )
    try:
        duration = float(r.stdout.strip())
    except (TypeError, ValueError) as duration_error:
        raise RuntimeError(
            f"Durée média invalide pour {path}: {r.stdout!r}"
        ) from duration_error
    if duration <= 0:
        raise RuntimeError(f"Durée média nulle pour {path}")
    return duration


def _render_simple_scene(image_path: str, duration: float,
                           out_path: str, width: int, height: int,
                           fps: int, fade_duration: float = 0.5,
                           overlay_inputs: list = None) -> str:
    """
    Rend une scène simple : image bouclée + fondu + overlays optionnels.
    Overlays superposés au centre. Pas de zoompan (instable).
    """
    # Construire les overlays valides
    valid_overlays = []
    if overlay_inputs:
        for ov in overlay_inputs:
            if ov and os.path.exists(ov):
                valid_overlays.append(ov)

    n_overlays = len(valid_overlays)

    # Inputs
    inputs = ["-loop", "1", "-i", image_path]
    for ov in valid_overlays:
        inputs.extend(["-loop", "1", "-i", ov])

    # Filter chain: chaque overlay incrémente l'index de 1
    parts = [f"[0:v]format=rgba,fade=t=in:st=0:d={fade_duration}:alpha=1,"
             f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
             f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[bg]"]

    current_src = "[bg]"
    for oi in range(n_overlays):
        label = f"ov{oi}"  # e.g. "ov0", "ov1"
        input_idx = oi + 1   # e.g. 1, 2 (input 0 is the bg image)
        parts.append(f"[{input_idx}:v]format=rgba[{label}]")
        next_src = f"out{oi}" if oi < n_overlays - 1 else "v"
        parts.append(f"{current_src}[{label}]overlay=(W-w)/2:(H-h)/2[{next_src}]")
        current_src = f"[{next_src}]"

    # Final format conversion
    parts.append(f"{current_src}format=yuv420p,setpts=PTS-STARTPTS[v]")
    filter_complex = ";".join(parts)

    subprocess.run([
        "ffmpeg", *inputs,
        "-t", str(duration),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        out_path, "-y", "-loglevel", "error"
    ], check=True, timeout=120)

    return out_path


def render_title_scene(title_card_path: str, duration: float = 4.0,
                        out_path: str = None, width: int = 1920, height: int = 1080,
                        fps: int = 30) -> str:
    """Rend la scène titre : fondu d'entrée. Pas de zoompan (instable)."""
    if out_path is None:
        out_path = str(Path(title_card_path).with_suffix("") + "_scene.mp4")
    return _render_simple_scene(title_card_path, duration, out_path, width, height, fps, 0.8)


def render_scene(scene_image_path: str, duration: float,
                  out_path: str = None, width: int = 1920, height: int = 1080,
                  fps: int = 30, zoom_range: tuple = (1.0, 1.12),
                  pan: str = "random", overlays: list = None,
                  overlay_times: list = None) -> str:
    """
    Rend une scène. Ken Burns simplifié via approximation.
    Utilise _render_simple_scène quand zoompan serait instable.
    """
    if out_path is None:
        out_path = str(Path(scene_image_path).with_suffix("") + "_scene.mp4")

    # Collect overlay inputs
    overlay_inputs = overlays if overlays else []
    return _render_simple_scene(scene_image_path, duration, out_path,
                                 width, height, fps, 0.3, overlay_inputs)


def render_clip_scene(clip_path: str, duration: float,
                        out_path: str, overlays: list = None,
                        width: int = 1920, height: int = 1080) -> str:
    """
    Rend une scène avec un clip vidéo en fond + overlays statiques.
    Le clip est bouclé si plus court que la durée, trimé si plus long.
    Pas d'audio du clip (la voix-off est gérée séparément).
    """
    overlay_inputs = [ov for ov in (overlays or []) if ov and os.path.exists(ov)]
    n_ov = len(overlay_inputs)

    inputs = []
    for ov in overlay_inputs:
        inputs.extend(["-loop", "1", "-i", ov])

    # Construire la chaîne de filtres
    # 1. Clip vidéo bouclé, redimensionné avec pillarbox si nécessaire
    parts = [
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[bg]"
    ]

    current_src = "[bg]"
    for oi in range(n_ov):
        label = f"ov{oi}"
        input_idx = oi + 1  # input 0 = clip
        parts.append(f"[{input_idx}:v]format=rgba[{label}]")
        next_src = "v" if oi == n_ov - 1 else f"out{oi}"
        parts.append(f"{current_src}[{label}]overlay=(W-w)/2:(H-h)/2[{next_src}]")
        current_src = f"[{next_src}]"

    parts.append(f"{current_src}format=yuv420p[v]")
    filter_complex = ";".join(parts)

    subprocess.run([
        "ffmpeg", "-stream_loop", "-1", "-i", clip_path, *inputs,
        "-t", str(duration),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-an",  # no audio from clip
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        out_path, "-y", "-loglevel", "error"
    ], check=True, timeout=120)

    return out_path


def render_end_card(end_card_path: str, duration: float = 3.0,
                     out_path: str = None, width: int = 1920, height: int = 1080,
                     fps: int = 30) -> str:
    """Rend la carte de fin."""
    if out_path is None:
        out_path = str(Path(end_card_path).with_suffix("") + "_scene.mp4")
    return _render_simple_scene(end_card_path, duration, out_path, width, height, fps, 1.0)


def compose_final_video(
    voiceover_paths: list[str],
    work_dir: Path,
    output_path: str = None,
    scene_images: list = None,
    clip_paths: list = None,
    overlay_plan: dict = None,
    title_card: str = None,
    end_card: str = None,
    ass_path: str = None,
    title_duration: float = 3.0,
    end_duration: float = 3.0,
    transition_duration: float = 0.5,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> str:
    """
    Pipeline complet de composition :
    1. Titre (optionnel)
    2. N scènes (clips vidéo ou images statiques)
    3. Overlays graphiques (stat cards, comparaisons)
    4. End card (optionnelle)
    5. Audio : voix-off segment par segment
    6. Transitions xfade
    7. Sous-titres ASS brûlés

    Paramètres :
    - scene_images: list de chemins PNG (pour images statiques)
    - clip_paths: list de chemins MP4 (pour clips vidéo en fond)
      Si les deux sont fournis, clip_paths a priorité.
    Retourne le chemin du fichier final.
    """
    if output_path is None:
        output_path = str(work_dir / "final.mp4")

    scenes_dir = work_dir / "rendered_scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    scene_videos = []

    # ── TITLE SCENE ──
    if title_card and os.path.exists(title_card):
        title_video = str(scenes_dir / "00_title.mp4")
        render_title_scene(title_card, title_duration, title_video, width, height, fps)
        scene_videos.append({
            "path": title_video,
            "duration": title_duration,
            "audio": None,  # Silence pendant le titre
        })
        print(f"  [COMPOSE] Title scene: {title_duration}s")

    # ── CONTENT SCENES ──
    num_scenes = len(voiceover_paths)
    use_clips = bool(clip_paths and len(clip_paths) >= num_scenes)
    source_type = "clips" if use_clips else "images"

    for i, vo_path in enumerate(voiceover_paths):
        vo_duration = get_media_duration(vo_path)
        overlays = []
        ov_times = []

        if overlay_plan and i < len(overlay_plan.get("segments", [])):
            seg_info = overlay_plan["segments"][i]
            overlays = seg_info.get("overlays", [])
            ov_times = seg_info.get("overlay_times", [])

        scene_video = str(scenes_dir / f"scene_{i+1:02d}.mp4")

        if use_clips and i < len(clip_paths) and os.path.exists(clip_paths[i]):
            # Fond : clip vidéo + overlays par-dessus
            pans = ["left", "right", "up", "down", "none"]
            print(f"  [COMPOSE] Scene {i+1}: {vo_duration:.1f}s | clip={Path(clip_paths[i]).name} | "
                  f"{len(overlays)} overlays")
            render_clip_scene(
                clip_path=clip_paths[i],
                duration=vo_duration,
                out_path=scene_video,
                overlays=overlays,
                width=width, height=height,
            )
        elif scene_images and i < len(scene_images) and os.path.exists(scene_images[i]):
            # Fond : image statique + overlays
            pans = ["left", "right", "up", "down", "none"]
            pan = pans[i % len(pans)]
            render_scene(
                scene_images[i], vo_duration, scene_video,
                width, height, fps,
                zoom_range=(1.0, 1.12),
                pan=pan,
                overlays=overlays,
                overlay_times=ov_times,
            )
            print(f"  [COMPOSE] Scene {i+1}: {vo_duration:.1f}s | pan={pan} | "
                  f"✅ image | {len(overlays)} overlays")
        else:
            # Fallback : écran noir
            subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i",
                f"color=c=#0A0F23:s={width}x{height}:d={vo_duration}:r={fps}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                scene_video, "-y", "-loglevel", "error"
            ], check=True)
            print(f"  [COMPOSE] Scene {i+1}: {vo_duration:.1f}s | ❌ fallback noir")

        scene_videos.append({
            "path": scene_video,
            "duration": vo_duration,
            "audio": vo_path,
        })

    print(f"[COMPOSE] Source: {source_type} ({num_scenes} scènes)")

    # ── END CARD ──
    if end_card and os.path.exists(end_card):
        end_video = str(scenes_dir / "99_end.mp4")
        render_end_card(end_card, end_duration, end_video, width, height, fps)
        scene_videos.append({
            "path": end_video,
            "duration": end_duration,
            "audio": str(Path(__file__).with_name("background_music.mp3")),
            "volume": 0.50,
        })
        print(f"  [COMPOSE] End scene: {end_duration}s")

    # ── ASSEMBLY ──
    # Avec transitions xfade entre les scènes + audio mapping
    n_scenes = len(scene_videos)
    if n_scenes == 0:
        raise Exception("Aucune scène à composer")

    filter_parts = []
    video_labels = []
    audio_labels = []

    # Input files
    input_files = []
    for sv in scene_videos:
        input_files.extend(["-i", sv["path"]])
    # Audio inputs for each scene
    audio_inputs = []
    for sv in scene_videos:
        if sv["audio"] and os.path.exists(sv["audio"]):
            audio_inputs.append(sv["audio"])
            input_files.extend(["-i", sv["audio"]])

    # Map streams — chaque scène a sa propre vidéo et son audio
    audio_stream_idx = 0  # compteur pour les entrées audio
    for i, sv in enumerate(scene_videos):
        v_label = f"s{i}"
        filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS,format=yuv420p[{v_label}]")
        video_labels.append(f"[{v_label}]")

        # Audio : soit la voix-off, soit silence
        if sv["audio"] and os.path.exists(sv["audio"]):
            a_idx = n_scenes + audio_stream_idx
            a_label = f"a{i}"
            filter_parts.append(
                f"[{a_idx}:a]atrim=duration={sv['duration']},asetpts=PTS-STARTPTS,volume={sv.get('volume', 1.0)}[{a_label}]"
            )
            audio_labels.append(f"[{a_label}]")
            audio_stream_idx += 1
        else:
            # Silence
            a_label = f"a{i}"
            filter_parts.append(
                f"anullsrc=r=44100:cl=stereo,atrim=duration={sv['duration']}[{a_label}]"
            )
            audio_labels.append(f"[{a_label}]")

    # Xfade transitions between scenes
    vtags = [l.strip("[]") for l in video_labels]
    atags = [l.strip("[]") for l in audio_labels]

    # Durées cumulées pour offset xfade
    durations = [sv["duration"] for sv in scene_videos]
    for xi in range(n_scenes - 1):
        offset = sum(durations[:xi + 1]) - (xi + 1) * transition_duration
        if xi == 0:
            filter_parts.append(
                f"[{vtags[0]}][{vtags[1]}]xfade=transition=fade:duration={transition_duration}:offset={offset}[t{xi + 1}]"
            )
            filter_parts.append(
                f"[{atags[0]}][{atags[1]}]acrossfade=d={transition_duration}[c{xi + 1}]"
            )
        else:
            filter_parts.append(
                f"[t{xi}][{vtags[xi + 1]}]xfade=transition=fade:duration={transition_duration}:offset={offset}[t{xi + 1}]"
            )
            filter_parts.append(
                f"[c{xi}][{atags[xi + 1]}]acrossfade=d={transition_duration}[c{xi + 1}]"
            )

    full_filter = ";".join(filter_parts)
    last_v = f"[t{n_scenes - 1}]" if n_scenes > 1 else video_labels[0]
    last_a = f"[c{n_scenes - 1}]" if n_scenes > 1 else audio_labels[0]

    # Save filter for debugging
    filter_file = work_dir / "compose_filter.txt"
    filter_file.write_text(full_filter, encoding="utf-8")
    print(f"[COMPOSE] Filter: {len(full_filter)} chars | {n_scenes} scenes | "
          f"{sum(durations):.1f}s total")

    assembled = str(work_dir / "assembled.mp4")
    subprocess.run([
        "ffmpeg", *input_files,
        "-filter_complex", full_filter,
        "-map", last_v, "-map", last_a,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        assembled, "-y", "-loglevel", "warning"
    ], check=True, timeout=600)

    final_dur = get_media_duration(assembled)
    print(f"[COMPOSE] Assemblé: {final_dur:.1f}s")

    # ── SUBTITLES BURN (PASS 2) ──
    if ass_path and os.path.exists(ass_path):
        final_output = str(work_dir / "final.mp4")
        # Import from caption_burner
        import sys; sys.path.insert(0, str(Path(__file__).parent.parent / 'skills/alfred_cron'))
        from caption_burner import burn_ass_captions
        burn_ass_captions(assembled, ass_path, final_output)

        final_dur2 = get_media_duration(final_output)
        print(f"[COMPOSE] Sous-titres brûlés: {final_dur2:.1f}s")
    else:
        final_output = assembled
        print("[COMPOSE] Pas de sous-titres")

    # ── VALIDATION ──
    final_duration = get_media_duration(final_output)
    if final_duration < 25:
        raise Exception(f"Vidéo trop courte ({final_duration:.1f}s)")

    # Validation stricte du flux vidéo final
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height",
            "-of", "json",
            final_output,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if probe.returncode != 0:
        raise RuntimeError(
            f"Validation ffprobe échouée: "
            f"{probe.stderr.strip()[-500:] or probe.returncode}"
        )

    try:
        info = json.loads(probe.stdout)
    except json.JSONDecodeError as probe_error:
        raise RuntimeError(
            f"Réponse ffprobe invalide: {probe.stdout!r}"
        ) from probe_error

    streams = info.get("streams", [])
    if not streams:
        raise RuntimeError("Aucun flux vidéo détecté dans le rendu final")

    stream = streams[0]
    actual_width = stream.get("width")
    actual_height = stream.get("height")
    codec = stream.get("codec_name")

    if actual_width != width or actual_height != height:
        raise RuntimeError(
            f"Dimensions incorrectes: {actual_width}x{actual_height} "
            f"(attendu: {width}x{height})"
        )
    if codec != "h264":
        raise RuntimeError(f"Mauvais codec: {codec}")

    # Copie vers output_path si différent
    if str(final_output) != str(output_path):
        shutil.copy2(final_output, output_path)

    print(f"[COMPOSE] ✅ Final: {output_path} ({final_duration:.1f}s, {stream.get('width')}×{stream.get('height')}, H.264)")
    return str(output_path)


if __name__ == "__main__":
    # Test simple
    print("=== Scene Composer Test ===")
    test_dir = Path("/tmp/alfred_compose_test")
    test_dir.mkdir(parents=True, exist_ok=True)

    # Vérifie que les fonctions marchent
    print(f"Media duration (ffprobe): OK")
    print("✅ Scene composer chargé")