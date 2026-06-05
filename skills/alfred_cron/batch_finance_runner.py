#!/usr/bin/env python3
"""
Batch Finance Video Runner
Injecte les 5 scripts pre-ecrits dans le pipeline video.
Reutilise la structure du nightly_orchestrator (TTS, clips, montage, upload).
Usage: python3 skills/alfred_cron/batch_finance_runner.py [--preview]
"""

import os, sys, json, random, subprocess, asyncio, shutil, time
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
SCRIPTS_DIR = WORKSPACE / "video_scripts"
RAW_CLIPS_ROOT = Path.home() / "output" / "raw_clips"
LOGO_PATH = WORKSPACE / "skills/alfred_video_pipeline/alfredstudio_app_icon.png"
UPLOAD_PY = WORKSPACE / "skills/youtube_upload/upload.py"
SECRETS_ENV = Path.home() / ".secrets/env"
PLAYBOOK_PATH = WORKSPACE / "skills/alfred_video_pipeline/PLAYBOOK_NEURO_FINANCE.md"
CHARTER_PATH = WORKSPACE / "skills/alfred_video_pipeline/EDITORIAL_CHARTER_NEURO_FINANCE.md"

DEFAULT_HASHTAGS = "\n#Finance #Investissement #PEA #ETF #LiberteFinanciere"

# Charger les secrets
os.environ.setdefault("DEFAULT_HASHTAGS", DEFAULT_HASHTAGS)
if SECRETS_ENV.is_file():
    with open(SECRETS_ENV) as f:
        for line in f:
            if "=" in line:
                line = line.replace("export ", "").strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k] = v.strip('"').strip("'")

# ── SCRIPTS PRE-ECRITS ──────────────────────────────────────────────
SCRIPTS = [
    {
        "file": "video1_jeune_plan.txt",
        "title": "J'ai 26 ans et 200 euros par mois : mon plan pour etre libre",
        "niche": "Finance personnelle",
    },
    {
        "file": "video2_pea_av_cto.txt",
        "title": "PEA vs Assurance-Vie vs CTO : le match fiscal 2026",
        "niche": "Finance / Fiscalite",
    },
    {
        "file": "video3_impact_frais.txt",
        "title": "L'impact cache des frais : 144 000 euros perdus en 25 ans",
        "niche": "Finance personnelle",
    },
    {
        "file": "video4_4_phases.txt",
        "title": "Mes 4 phases pour l'independance financiere (roadmap complete)",
        "niche": "Investissement",
    },
    {
        "file": "video5_moitie_chemin.txt",
        "title": "La regle de la moitie du chemin vers 600 000 euros",
        "niche": "Finance / Interets composes",
    },
]


def load_segments(filepath):
    """Lit un fichier script et le separe en 4 segments ~30 mots"""
    with open(filepath) as f:
        content = f.read()

    # Enlever les commentaires et lignes vides
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("[") or stripped.startswith("```"):
            continue
        lines.append(stripped)

    full_text = " ".join(lines)

    # Nettoyer les caracteres speciaux
    full_text = full_text.replace("\u2019", "'").replace("\u2018", "'")
    full_text = full_text.replace("\u201c", """).replace("\u201d", """)
    full_text = full_text.replace("\u2014", "-").replace("\u2013", "-")

    # Diviser en phrases
    sentences = re.split(r'[.!?]+', full_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    # Grouper en ~4 segments de ~30 mots
    # Si on a 4+ phrases, on repartit
    # Decoupage par mots en 4 segments egaux
    words = full_text.split()
    total = len(words)
    n = total // 4
    rem = total % 4

    segs = []
    idx = 0
    for i in range(4):
        chunk = n + (1 if i < rem else 0)
        segment = " ".join(words[idx:idx+chunk])
        if segment and not segment.endswith("."):
            segment += "."
        segs.append(segment)
        idx += chunk

    return segs


def send_telegram(msg):
    """Envoie un message Telegram (copie du pipeline)"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            import requests
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            print(f"[TG] Erreur: {e}")


def pick_clips(n=4):
    """Selectionne des clips aleatoires (copie du pipeline)"""
    if not RAW_CLIPS_ROOT.exists():
        print("[CLIPS] Repertoire raw_clips introuvable")
        return []

    # Trouver tous les clips dispo
    clips = []
    for p in RAW_CLIPS_ROOT.iterdir():
        if p.suffix.lower() in (".mp4", ".mov", ".avi", ".webm"):
            clips.append(p)

    if len(clips) < n:
        print(f"[CLIPS] Pas assez de clips: {len(clips)} dispo, besoin de {n}")
        # Dupliquer si besoin
        while len(clips) < n:
            if clips:
                clips.append(clips[0])
            else:
                return []

    random.shuffle(clips)
    return clips[:n]


async def generate_voiceover(segments, work_dir):
    """Genere les voiceovers avec edge-tts"""
    import edge_tts
    voices = {
        "A": "fr-FR-VivienneMultilingualNeural",
        "B": "fr-FR-RemyMultilingualNeural",
    }

    audio_paths = []
    durations = []

    for i, seg in enumerate(segments):
        voice_key = "B" if i == 0 or i == 3 else "A"
        voice_id = voices[voice_key]
        out_path = work_dir / f"vo{i+1}.wav"

        # TTS
        tts = edge_tts.Communicate(seg[:300], voice_id, rate="-5%")
        await tts.save(str(out_path))

        # Duree
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(out_path)],
            capture_output=True, text=True, timeout=30
        ).stdout.strip() or 0)

        if dur < 1:
            print(f"[VO] Segment {i+1}: ECHEC, fallback silence")
            subprocess.run(
                ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                 "-t", "10", str(out_path), "-y", "-loglevel", "error"],
                capture_output=True, text=True)
            dur = 10.0

        audio_paths.append(out_path)
        durations.append(dur)
        print(f"[VO] Segment {i+1}: {dur:.1f}s (voix {voice_key})")

    return audio_paths, durations


def assemble_video(segments, audio_paths, durations, clips, work_dir, output_path):
    """Assemble la video finale (copie logique du pipeline)"""
    n = len(segments)

    # Preparer les filtres video
    filter_parts = []
    v_labels = []
    a_labels = []

    for i in range(n):
        clip_path = clips[i] if i < len(clips) else clips[-1]
        video_dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(clip_path)],
            capture_output=True, text=True, timeout=30
        ).stdout.strip() or 10)

        audio_dur = durations[i]
        speed = audio_dur / video_dur if video_dur > 0 else 1.0

        v_label = f"v{i}"
        v_proc = (
            f"[{i}:v]setpts=PTS-STARTPTS,setpts={speed}*PTS,"
            f"trim=duration={audio_dur},setpts=PTS-STARTPTS,"
            f"fps=30[{v_label}]"
        )
        filter_parts.append(v_proc)
        v_labels.append(f"[{v_label}]")

        a_label = f"a{i}"
        filter_parts.append(
            f"[{i}:a]atrim=0:{audio_dur},asetpts=PTS-STARTPTS,volume=0.15[amb{i}];"
            f"[{i+n}:a]atrim=0:{audio_dur},asetpts=PTS-STARTPTS,volume=1.0[vo{i}];"
            f"[amb{i}][vo{i}]amix=inputs=2:duration=first[{a_label}]"
        )
        a_labels.append(f"[{a_label}]")

    # Concatenation
    v_stack = "".join(v_labels)
    a_stack = "".join(a_labels)
    filter_parts.append(
        f"{v_stack}{a_stack}concat=n={n}:v=1:a=1[vid][aud]"
    )
    filter_complex = ";".join(filter_parts)

    # Inputs: clips + audios
    inputs = []
    for i in range(n):
        inputs.extend(["-i", str(clips[i])])
    for i in range(n):
        inputs.extend(["-i", str(audio_paths[i])])

    # PASS 1
    pass1 = work_dir / "pass1.mp4"
    cmd1 = [
        "ffmpeg",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vid]",
        "-map", "[aud]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-r", "30",
        "-shortest",
        "-y",
        str(pass1),
        "-loglevel", "error"
    ]

    print(f"[FFMPEG] PASS 1...")
    result = subprocess.run(cmd1, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"[ERREUR] PASS 1: {result.stderr[:300]}")
        return False

    if not pass1.exists():
        print(f"[ERREUR] PASS 1: fichier non genere")
        return False

    # PASS 2 (faststart pour streaming)
    cmd2 = [
        "ffmpeg", "-i", str(pass1),
        "-c", "copy",
        "-movflags", "+faststart",
        "-y",
        str(output_path),
        "-loglevel", "error"
    ]
    print(f"[FFMPEG] PASS 2...")
    result = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"[ERREUR] PASS 2: {result.stderr[:300]}")
        return False

    if not output_path.exists():
        print(f"[ERREUR] Output non genere")
        return False

    # Verification
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,codec_name",
         "-of", "default=noprint_wrappers=1", str(output_path)],
        capture_output=True, text=True, timeout=30
    )
    print(f"[VERIF] {probe.stdout.strip()}")

    print(f"[OK] Video generee: {output_path}")
    file_size = output_path.stat().st_size / (1024 * 1024)
    print(f"[SIZE] {file_size:.1f} Mo")

    return True


def upload_youtube(video_path, title, description):
    """Upload sur YouTube via upload.py"""
    if not UPLOAD_PY.exists():
        print(f"[UPLOAD] upload.py introuvable: {UPLOAD_PY}")
        return False

    print(f"[UPLOAD] Upload de {video_path.name}...")
    result = subprocess.run(
        ["python3", str(UPLOAD_PY),
         "--file", str(video_path),
         "--title", title,
         "--description", description,
         "--privacy", "public",
         "--category", "27"],  # Education
        capture_output=True, text=True, timeout=120
    )

    if result.returncode == 0:
        print(f"[UPLOAD] ✅ Reussi!")
        if result.stdout:
            print(f"   {result.stdout[-200:].strip()}")
        return True
    else:
        print(f"[UPLOAD] ❌ Echec: {result.stderr[:300]}")
        return False


async def process_video(script_info, idx, preview=False):
    """Traite une video complete"""
    script_file = SCRIPTS_DIR / script_info["file"]
    title = script_info["title"]
    niche = script_info["niche"]

    print(f"\n{'='*60}")
    print(f"📹 Video {idx}/5 : {title}")
    print(f"{'='*60}")

    # Charger et segmenter le script
    segments = load_segments(script_file)
    word_counts = [len(s.split()) for s in segments]
    print(f"   Segments: {len(segments)}, mots: {word_counts}")

    if any(wc < 20 for wc in word_counts):
        print(f"   ⚠️  Segments trop courts, ajustement...")
        # Re-equilibrer
        full = " ".join(segments)
        words = full.split()
        total = len(words)
        per = max(1, total // 4)
        segments = [
            " ".join(words[i*per:(i+1)*per])
            for i in range(4)
        ]

    # Creer work_dir
    ts = int(time.time())
    work_dir = Path(f"/tmp/alfred_finance_{ts}_{idx}")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Selectionner clips
        clips = pick_clips(4)
        if not clips:
            print(f"[CLIPS] Aucun clip disponible, abandon")
            return False

        print(f"[CLIPS] {len(clips)} clips selectionnes")

        # 2. Generer voix off
        audio_paths, durations = await generate_voiceover(segments, work_dir)

        # 3. Assembler video
        video_filename = f"finance_{idx:02d}_{int(time.time())}.mp4"
        video_path = Path.home() / "output" / video_filename

        ok = assemble_video(segments, audio_paths, durations, clips, work_dir, video_path)
        if not ok:
            print(f"[VIDEO] Echec assemblage")
            return False

        # 4. Description SEO
        seg_bullets = "\n".join("• " + s for s in segments)
        description = (
            f"💰 {title}\n\n"
            f"🎯 Dans cette video :\n{seg_bullets}\n\n"
            f"📊 Donnees issues du comparateur ETF PEA 2026 : "
            f"https://majordomef-sudo.github.io/pea-comparator/\n\n"
            f"🔔 Abonnez-vous pour ne rien rater : chaque jour, une video sur "
            f"la finance, l'investissement et la liberte financiere.\n"
            f"🤖 Bot Telegram @AlfredETFBot — Recherche d'ETF par ISIN\n"
            + DEFAULT_HASHTAGS
        )

        print(f"[DESC] {seg_bullets}")

        # 5. Upload ou preview
        if preview:
            send_telegram(
                f"🔍 PREVIEW Finance Video {idx}/5\n"
                f"Titre: {title}\n"
                f"Segments: {word_counts}\n"
                f"Fichier: {video_path}"
            )
            print(f"[PREVIEW] Video prete: {video_path}")
            return True

        ok = upload_youtube(video_path, title, description)
        if ok:
            send_telegram(
                f"🚀 Video Finance {idx}/5 uploadée !\n"
                f"Titre: {title}\n"
                f"Mots/segment: {word_counts}"
            )
        else:
            send_telegram(f"⚠️ Upload echoue pour: {title}")

        return ok

    finally:
        # Nettoyage
        shutil.rmtree(work_dir, ignore_errors=True)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch Finance Videos")
    parser.add_argument("--preview", action="store_true", help="Skip YouTube upload")
    args = parser.parse_args()

    preview = args.preview
    mode = "PREVIEW" if preview else "PROD"

    print(f"\n{'='*60}")
    print(f"  BATCH FINANCE VIDEOS — {mode}")
    print(f"  5 scripts prets dans {SCRIPTS_DIR}")
    print(f"{'='*60}\n")

    # Verifier espace
    tmp_free = shutil.disk_usage('/tmp').free
    if tmp_free < 1_073_741_824:
        print(f"❌ /tmp insuffisant: {tmp_free // 1_048_576} Mo")
        sys.exit(1)

    send_telegram(f"🎬 Lancement batch {mode} : 5 videos finance")

    success = 0
    for i, script in enumerate(SCRIPTS, 1):
        try:
            ok = await process_video(script, i, preview)
            if ok:
                success += 1
            else:
                print(f"❌ Video {i} echouee")
                send_telegram(f"❌ Video {i}/{5} echouee: {script['title']}")
        except Exception as e:
            print(f"❌ Video {i} erreur: {e}")
            send_telegram(f"❌ Video {i}/{5} erreur: {e}")

        # Pause entre les videos (eviter rate limit API)
        if i < len(SCRIPTS):
            print(f"\n--- Pause 30s avant video {i+1} ---")
            await asyncio.sleep(30)

    # Rapport final
    msg = f"📊 BATCH FINANCE TERMINE\n✅ {success}/{5} videos {'publiees' if not preview else 'pretees'}"
    print(f"\n{msg}")
    send_telegram(msg)


if __name__ == "__main__":
    asyncio.run(main())
