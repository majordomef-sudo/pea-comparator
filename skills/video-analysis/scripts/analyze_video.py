#!/usr/bin/env python3
"""
analyze_video.py — Analyse multi-dimensionnelle d'une vidéo pipeline

Modules : technique, scènes, motion, audio, contenu (LLM), viralité
Intégration claude-watch (taoufik123-collab/claude-watch) :
  - Hook microscope 0-10s (extraction dense + word-level Whisper)
  - Scene-change frame extraction (1 frame/plan au lieu de N/secondes)
  - Hero frames selection (3-5 frames clés)
  - Auto-fps adaptatif

Usage CLI :
  python3 analyze_video.py --video chemin.mp4 [--script script.json] [--output dossier/]

Usage programmatique :
  from analyze_video import analyze
  report = analyze("/path/to/video.mp4", "/path/to/script.json")
"""

import json, os, sys, subprocess, argparse, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WORKSPACE = Path.home() / ".openclaw" / "workspace"
SKILL_DIR = WORKSPACE / "skills" / "video-analysis"
MODULES_DIR = SKILL_DIR / "scripts" / "modules"

# S'assurer que les modules sont importables
if str(MODULES_DIR) not in sys.path:
    sys.path.insert(0, str(MODULES_DIR))

from technical import analyze_technical
from scenes import analyze_scenes, extract_scene_change_frames, auto_fps
from motion import analyze_motion
from audio_analysis import analyze_audio
from content import analyze_content_llm
from virality import compute_virality_score
from report import generate_report
from hook_analysis import analyze_hook
from hero_frames import select_hero_frames, describe_hero_frames
from hook_reflection import log_hook_score, get_hook_score_trend, summarize_hook_trend

# Fusion video-analyzer (byjlw) : vision LLM
try:
    from vision_analysis import VisionAnalyzer, VisionResult
    HAVE_VISION = True
except ImportError:
    HAVE_VISION = False
    logger.warning("vision_analysis module not available")


def _get_duration(video_path: Path) -> float:
    """Récupère la durée de la vidéo."""
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(video_path)],
        capture_output=True, text=True,
    )
    data = json.loads(probe.stdout or "{}").get("format", {})
    return float(data.get("duration", 0))


def analyze(
    video_path_str: str,
    script_path_str: str = None,
    output_dir_str: str = None,
    enable_vision: bool = False,
    vision_model: str = "google/gemini-2.0-flash-exp:free",
) -> dict:
    """Point d'entrée programmatique : analyse complète d'une vidéo.

    Args:
        video_path_str: Chemin vers la vidéo
        script_path_str: Optionnel, chemin vers le script JSON
        output_dir_str: Optionnel, dossier de sortie pour frames/rapports

    Returns:
        dict: Rapport d'analyse complet (inclut hook + hero frames)
    """
    video_path = Path(video_path_str)

    if not video_path.exists():
        raise FileNotFoundError(f"Vidéo introuvable : {video_path}")

    output_dir = Path(output_dir_str or "rapports") / video_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    # Vérifier résolution
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", str(video_path)],
        capture_output=True, text=True,
    )
    info = json.loads(probe.stdout)
    streams = {s["codec_type"]: s for s in info.get("streams", [])}
    vstream = streams.get("video", {})
    duration = _get_duration(video_path)

    print(f"  🎬 Analyse : {video_path.name} | {vstream.get('width')}x{vstream.get('height')} | {duration:.0f}s")

    # === MODULES EXISTANTS ===
    tech = analyze_technical(video_path)
    scenes = analyze_scenes(video_path)
    motion = analyze_motion(video_path)
    audio = analyze_audio(video_path)

    script_data = None
    if script_path_str:
        spath = Path(script_path_str)
        if spath.exists():
            script_data = json.loads(spath.read_text())
    content = analyze_content_llm(video_path, script_data)
    virality = compute_virality_score(scenes, motion, audio, content)

    # === NOUVEAU : Hook Microscope 0-10s (claude-watch) ===
    print("  🔬 Hook microscope 0-10s...")
    hook_data = analyze_hook(str(video_path), output_dir, full_duration=duration)
    if hook_data.get("ran"):
        print(f"     Pattern: {hook_data.get('hook_pattern', '?')} | Score: {hook_data.get('hook_score', '?')}/10")
        if hook_data.get("frame_count"):
            print(f"     Frames: {hook_data['frame_count']} en 10s")
    else:
        print(f"     Skipped: {hook_data.get('reason', 'N/A')}")

    # === NOUVEAU : Scene-change frames (claude-watch) ===
    print("  🎞️  Scene-change frame extraction...")
    scene_frames_dir = output_dir / "scene_frames"
    scene_change_frames = extract_scene_change_frames(
        video_path, scene_frames_dir,
        max_frames=100,
    )
    scenes["scene_change_frames"] = [
        {"index": f["index"], "timestamp": f["timestamp"],
         "path": f["path"], "type": f.get("type", "scene-change")}
        for f in scene_change_frames
    ]
    scenes["scene_frame_count"] = len(scene_change_frames)
    print(f"     {len(scene_change_frames)} frames extraites ({scene_change_frames[0].get('type', 'scene') if scene_change_frames else 'aucune'})")

    # === NOUVEAU : Hero frames (claude-watch) ===
    print("  ⭐ Hero frames selection...")
    hero_frames = select_hero_frames(
        scene_change_frames,
        shot_data=scenes.get("transitions", []),
        hook_end=10.0,
    )
    print(f"     {len(hero_frames)} frames clés sélectionnées")

    # === NOUVEAU : Vision LLM (byjlw/video-analyzer fusion) ===
    vision_data = {}
    if enable_vision and HAVE_VISION:
        print("  👁️  Vision LLM analysis...")
        try:
            va = VisionAnalyzer(model=vision_model)
            vr = va.analyze(str(video_path), output_dir)
            vision_data = {
                "frames": vr.frames_count,
                "analyses_count": len(vr.frame_analyses),
                "description": vr.description,
                "text_on_screen": vr.text_on_screen[:12],
                "coherence_score": vr.coherence_score,
            }
            print(f"     {vr.frames_count} frames analysees")
            if vr.text_on_screen:
                print(f"     Texte detecte: {vr.text_on_screen[:4]}")
            if vr.description:
                print(f"     Description: {vr.description[:100]}...")
        except Exception as e:
            print(f"     Failed: {e}")
            vision_data = {"error": str(e)}
    else:
        vision_data = {"skipped": True}

    # === RAPPORT ===
    report = generate_report(
        tech, scenes, motion, audio, content, virality,
        hook=hook_data,
        hero_frames=hero_frames,
        vision_analysis=vision_data if vision_data.get("frames", 0) > 0 else None,
    )
    report["video_path"] = video_path_str
    report["duration"] = round(duration, 2)

    # Sauvegarde du rapport
    report_path = output_dir / "rapport.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )

    # Auto-réflexion hook : log dans l'historique
    hook_info = report.get("hook_microscope", {})
    # Vision LLM
    vision_info = report.get("vision_analysis", {})
    if vision_info.get("frames", 0) > 0:
        print(f"  👁️  Vision: {vision_info["frames"]} frames | scores: {vision_info.get("coherence_score", "?")}")
    elif vision_info.get("skipped"):
        print("  👁️  Vision: desactivee (--vision pour activer)")

    if hook_info.get("ran"):
        log_entry = log_hook_score(
            video_name=video_path.name,
            hook_score=hook_info.get("hook_score"),
            hook_pattern=hook_info.get("hook_pattern"),
            frame_count=hook_info.get("frame_count", 0),
            duration=duration,
        )
        if log_entry.get("adjustment"):
            adj = log_entry["adjustment"]
            if adj.get("alert"):
                print(f"  ⚠️  {adj['message']}")

    return report


def parse_args():
    parser = argparse.ArgumentParser(description="Analyse vidéo pipeline Neuro-Finance")
    parser.add_argument("--video", required=True, help="Chemin vers la vidéo à analyser")
    parser.add_argument("--script", help="Chemin vers le script LLM (JSON)")
    parser.add_argument("--output", default="rapports/", help="Dossier de sortie du rapport")
    parser.add_argument("--vision", action="store_true", help="Activer analyse visuelle LLM")
    parser.add_argument("--vision-model", default="google/gemini-2.0-flash-exp:free", help="Modele vision")
    return parser.parse_args()


def main():
    args = parse_args()

    report = analyze(args.video, args.script, args.output, enable_vision=args.vision, vision_model=args.vision_model)

    scores = report["scores"]
    hook_info = report.get("hook_microscope", {})

    print(f"\n{'='*60}")
    print(f"  📊 RAPPORT FINAL — {scores['global']}/100 ({report['category']})")
    print(f"  Technique: {scores['technical']}/30 | Contenu: {scores['content']}/30")
    print(f"  Audio: {scores['audio']}/20 | Viralité: {scores['virality']}/20")
    # Vision LLM
    vision_info = report.get("vision_analysis", {})
    if vision_info.get("frames", 0) > 0:
        print(f"  👁️  Vision: {vision_info["frames"]} frames | scores: {vision_info.get("coherence_score", "?")}")
    elif vision_info.get("skipped"):
        print("  👁️  Vision: desactivee (--vision pour activer)")

    if hook_info.get("ran"):
        hscore = hook_info.get("hook_score", "?")
        hpattern = hook_info.get("hook_pattern", "?")
        hframes = hook_info.get("frame_count", 0)
        print(f"  🔬 Hook: {hscore}/10 | Pattern: {hpattern} | {hframes} frames/10s")
    print(f"  → Rapport sauvegardé")
    print(f"{'='*60}")

    # Tendances auto-réflexion
    print(f"\n📈 Tendance hook :")
    print(summarize_hook_trend())

    print(f"\n🔧 Top 3 améliorations :")
    for i, imp in enumerate(report.get("improvements", [])[:3], 1):
        print(f"  {i}. {imp['action']} (gain +{imp['impact']} pts)")
    print()


if __name__ == "__main__":
    main()