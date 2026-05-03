#!/usr/bin/env python3
"""
nightly_orchestrator.py — Pipeline Neuro-Finance (PRODUCTION)
=============================================================
Pipeline calqué sur le test orchestrator (référence) :
  - LLM deepseek-v4-flash (default), fallback Gemma-4
  - 1 seul appel LLM (plus de boucle de review)
  - Validation bloquante : langue interdite, guru-speak, data chiffrée
  - TTS par segment (plus de fragmentation phrase par phrase)
  - Clip DB en cache, plus de ffprobe par clip
  - Font par défaut en fallback
"""

import os, sys, subprocess, json, random, time, re, shutil, asyncio, textwrap, difflib
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import requests, edge_tts

# ── YOUTUBE TAGS & DESCRIPTION (appliqué à chaque upload) ─────────
DEFAULT_TAGS = [
    "Neuro-Finance",
    "finance comportementale",
    "biais cognitifs",
    "investissement",
    "psychologie de l'argent",
    "éducation financière",
    "cerveau et argent",
    "antifragilité",
    "probabilités",
    "risque"
]

DEFAULT_DESC_TEMPLATE = """{}🎯 Dans cette vidéo :
{}{}{}{}
🔔 Abonnez-vous pour ne rien rater : tous les jours, une révélation sur la neurobiologie de l'argent."""

DEFAULT_HASHTAGS = "\n#NeuroFinance #FinanceComportementale #BiaisCognitifs #Investissement #PsychologieDeLArgent"


# ── CONFIG ──────────────────────────────────────────────────────────
SECRETS_ENV = Path.home() / ".secrets/env"
WORKSPACE    = Path("/home/ubuntu/.openclaw/workspace")
PIPELINE_DIR = WORKSPACE / "skills/alfred_video_pipeline"

# Assets Neuro-Finance
PLAYBOOK_PATH   = PIPELINE_DIR / "PLAYBOOK_NEURO_FINANCE.md"
CHARTER_PATH    = PIPELINE_DIR / "EDITORIAL_CHARTER_NEURO_FINANCE.md"
LEXICON_PATH    = PIPELINE_DIR / "SEMANTIC_LEXICON_NEURO_FINANCE.md"
PERFORMANCE_MD  = PIPELINE_DIR / "PERFORMANCE.md"
AFFILIATION_PATH = PIPELINE_DIR / "AFFILIATION_DB.json"

UPLOAD_PY = WORKSPACE / "skills/youtube_upload/upload.py"

# Modèles
MODEL_MAIN   = os.environ.get("MODEL_PIPELINE", "deepseek/deepseek-v4-flash")
MODEL_FALLBACK = "google/gemma-4-31b-it"  # fallback si deepseek down (coût ~équivalent)

# Clip sources
RAW_CLIPS_ROOT = Path.home() / "output" / "raw_clips"
CLIP_CACHE_FILE = WORKSPACE / "state" / "clip_db_cache.json"

# Font fallback si font_selector.py indisponible
FONT_FALLBACK = "/usr/share/fonts/truetype/montserrat/Montserrat-ExtraBold.ttf"

GURU_BLACKLIST = [
    "riche rapidement", "secret", "miracle", "liberté financière",
    "astuce", "gagner gros", "methode miracle", "devenir riche"
]

# ── HELPERS ─────────────────────────────────────────────────────────

def load_secrets():
    s = os.environ.copy()
    if SECRETS_ENV.is_file():
        with open(SECRETS_ENV) as f:
            for line in f:
                if '=' in line:
                    line = line.replace('export ', '').strip()
                    if '=' in line:
                        k, v = line.split('=', 1)
                        s[k] = v.strip('"').strip("'")
    return s

def send_telegram(msg):
    print(f"[TG] {msg}")
    secrets = load_secrets()
    bt, ci = secrets.get("TELEGRAM_BOT_TOKEN"), secrets.get("TELEGRAM_CHAT_ID")
    if bt and ci:
        try:
            requests.post(f"https://api.telegram.org/bot{bt}/sendMessage",
                          data={"chat_id": ci, "text": msg}, timeout=10)
        except Exception as e:
            print(f"[TG ERR] {e}")

def ask_llm(prompt, model=MODEL_MAIN, max_tokens=1500):
    """Appel LLM avec fallback automatique si le modèle gratuit est down."""
    secrets = load_secrets()
    api_key = secrets.get("OPENROUTER_API_KEY")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    models_to_try = [model] if model != MODEL_MAIN else [MODEL_MAIN, MODEL_FALLBACK]

    for m in models_to_try:
        for attempt in range(3):
            try:
                resp = requests.post(url, headers=headers, json={
                    "model": m, "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7, "max_tokens": max_tokens
                }, timeout=45)
                if resp.status_code == 429:
                    time.sleep(2 ** attempt + random.random())
                    continue
                resp.raise_for_status()
                data = resp.json()
                c = data['choices'][0]['message']['content']
                match = re.search(r'```(?:json)?\s*(.*?)\s*```', c, re.DOTALL)
                return (match.group(1) if match else c).strip(), m
            except Exception as e:
                if attempt == 2:
                    print(f"[LLM] {m} failed: {e}")
                    break
                time.sleep(2 ** attempt)

    raise Exception("Tous les modèles LLM ont échoué")

def get_audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())

def calculate_guru_score(text):
    return sum(text.lower().count(t) for t in GURU_BLACKLIST)

# Mots anglais/espagnols strictement interdits
FORBIDDEN_WORDS = [
    "hedge fund", "smart money", "leverage", "criterion", "storytelling",
    "dark pattern", "exit strategy", "deal", "trade", "trading", "trader",
    "broker", "asset", "liability", "equity", "bond", "bull market",
    "bear market", "spread", "swap", "default",
    "margin call", "portfolio", "capital gain", "cash flow", "pricing",
    "risk premium", "overhead", "fee", "rating", "investment bank",
    "private equity", "venture capital", "high frequency", "algorithmic",
    "behavioral finance", "mispricing", "volatility",
    "cognitive",  # edge-tts prononce a l'anglaise
    # Espagnol
    "dinero", "mercado", "inversion", "ganancia", "perdida", "riesgo",
    "banco", "finanzas", "accion", "bono", "tasa",
    "negocio", "interes", "inversor", "ahorro", "deuda",
]

# Mots ambigus que edge-tts prononce mal → correction phonétique française
PHONETIC_FIXES = {
    "cognitive": "cognitif",
    "cognition": "cognition",
    "behavioral": "comportemental",
    "algorithm": "algorithme",
    "algorithmic": "algorithmique",
    "default": "défaut",
    "leverage": "levier",
    "volatility": "volatilité",
    "portfolio": "portefeuille",
    "equity": "capitaux",
    "liability": "passif",
    "bond": "obligation",
    "premium": "prime",
    "rating": "notation",
    "criterion": "critère",
}

def contains_forbidden_words(text):
    lower_text = text.lower()
    for word in FORBIDDEN_WORDS:
        if word in lower_text:
            print(f"[LANG] mot interdit: '{word}'")
            return True
    return False

# ── CLIP DATABASE (AVEC CACHE) ──────────────────────────────────────

def build_clip_database(use_cache=True):
    """Scan raw_clips/ avec cache JSON pour éviter le re-scan à chaque run."""
    if use_cache and CLIP_CACHE_FILE.exists():
        try:
            mtime_db = CLIP_CACHE_FILE.stat().st_mtime
            # Vérifie si des clips ont été ajoutés depuis le cache
            # 1) Mtime du fichier le plus récent
            newest_clip = max(
                (p.stat().st_mtime for p in RAW_CLIPS_ROOT.rglob("*.mp4")),
                default=0
            )
            # 2) Mtime du dossier de date le plus récent (capture les dossiers nouveaux)
            newest_dir = max(
                (d.stat().st_mtime for d in RAW_CLIPS_ROOT.iterdir() if d.is_dir()),
                default=0
            )
            if max(newest_clip, newest_dir) <= mtime_db:
                with open(CLIP_CACHE_FILE) as f:
                    return json.load(f)
        except Exception:
            pass

    topics = defaultdict(list)
    pattern = re.compile(r'^(.+?)_v[1-4]\.mp4$')

    for clip_path in sorted(RAW_CLIPS_ROOT.rglob("*.mp4")):
        m = pattern.match(clip_path.name)
        topic = m.group(1) if m else re.sub(r'(_v[1-4])?\.mp4$', '', clip_path.name)
        topics[topic].append(str(clip_path))

    # Construire les sets cohérents par date
    date_topic_map = defaultdict(list)
    for topic, clip_strs in topics.items():
        for c_str in clip_strs:
            c = Path(c_str)
            date_dir = c.parent.name
            date_topic_map[(date_dir, topic)].append(c_str)

    sets = [{"topic": t, "date": d, "clips": clips, "size": len(clips)}
            for (d, t), clips in sorted(date_topic_map.items())]

    db = {"topics": dict(topics), "sets": sets, "total": sum(len(v) for v in topics.values())}

    # Sauvegarde cache
    CLIP_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CLIP_CACHE_FILE, "w") as f:
        json.dump(db, f)

    return db

def smart_select_clips(clip_db, n=4):
    """Selectionne n clips avec priorité set cohérent."""
    sets = clip_db.get("sets", [])
    topics = clip_db["topics"]

    if not topics:
        raise Exception("Aucun clip disponible")

    # Set cohérent >= n
    coherent = [s for s in sets if s["size"] >= n]
    if coherent:
        chosen = random.choice(coherent)
        selected = sorted(chosen["clips"], key=lambda p: int(re.search(r'_v(\d+)\.mp4$', Path(p).name).group(1)))
        return [Path(p) for p in selected], f"{chosen['topic']} ({chosen['date']})"

    # Topic unique multidate
    for t, clips in sorted(topics.items(), key=lambda x: -len(x[1])):
        if len(clips) >= n:
            selected = random.sample([Path(p) for p in clips], n)
            return selected, f"{t} (multidate)"

    # Mélange anti-duplicate
    all_clips = [(t, Path(c)) for t, clips in topics.items() for c in clips]
    random.shuffle(all_clips)
    seen, selected = set(), []
    for t, c in all_clips:
        if len(selected) >= n:
            break
        if c.name not in seen:
            selected.append(c)
            seen.add(c.name)

    if len(selected) < n:
        raise Exception(f"Pas assez de clips uniques ({len(selected)}/{n})")
    return selected[:n], "mixed"

# ── VOICEOVER (REMY MULTILINGUAL) ───────────────────────────────────

async def generate_voiceover_segment(text, out_path, seg_idx, voice="A"):
    """Génère la voix pour un segment.
    Voice A = Remy (male, expert), Voice B = Vivienne (female, provocateur)."""
    clean = re.sub(r'[*_]', '', text)
    # Correction phonétique : remplacer les mots que edge-tts prononce mal
    for bad, good in PHONETIC_FIXES.items():
        clean = re.sub(re.escape(bad), good, clean, flags=re.IGNORECASE)
    voice_name = "fr-FR-RemyMultilingualNeural" if voice == "A" else "fr-FR-VivienneMultilingualNeural"
    tmp_mp3 = out_path.parent / f"vo{seg_idx}.tmp.mp3"
    # rate=-10% : voix légèrement ralentie pour un ton posé et autoritaire, sans déformation
    comm = edge_tts.Communicate(clean, voice_name, rate="-5%")
    await comm.save(str(tmp_mp3))

    if not tmp_mp3.exists() or tmp_mp3.stat().st_size < 100:
        return False

    subprocess.run([
        "ffmpeg", "-i", str(tmp_mp3),
        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
        str(out_path), "-y", "-loglevel", "error"
    ], check=True)
    tmp_mp3.unlink()
    return True

# ── FONT ────────────────────────────────────────────────────────────

def get_font():
    """Récupère la police via font_selector, avec fallback."""
    font_selector = PIPELINE_DIR / "font_selector.py"
    if font_selector.exists():
        try:
            result = subprocess.run(["python3", str(font_selector)],
                                    capture_output=True, text=True, timeout=10)
            data = json.loads(result.stdout)
            font_path = data.get("font_path", "")
            if font_path and os.path.exists(font_path):
                # Si c'est déjà une variante Bold, on l'utilise directement
                if "Bold" in font_path or "bold" in font_path:
                    return font_path
                # Sinon, on cherche la variante Bold dans le même dossier
                font_dir = os.path.dirname(font_path)
                font_name = os.path.splitext(os.path.basename(font_path))[0].split("-")[0]
                bolds = sorted(f for f in os.listdir(font_dir)
                               if f.endswith(".ttf") and "Bold" in f and font_name in f)
                if bolds:
                    return os.path.join(font_dir, bolds[0])
                return font_path
        except Exception:
            pass

    if os.path.exists(FONT_FALLBACK):
        return FONT_FALLBACK
    raise Exception("Aucune police disponible")

# ── MAIN ────────────────────────────────────────────────────────────

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Neuro-Finance Production")
    parser.add_argument("--preview", action="store_true",
                        help="Skip YouTube upload, send only to Telegram")
    parser.add_argument("--no-cache", action="store_true",
                        help="Force rebuild clip database")
    args, _ = parser.parse_known_args()

    PREVIEW_MODE = args.preview
    tag = "PROD PREVIEW" if PREVIEW_MODE else "PROD"
    niche = "Neuro-Finance"
    success = False

    # Vérification jour : pas de publication le dimanche (sauf preview)
    today_weekday = datetime.now().weekday()  # 0=lun, 6=dim
    if not PREVIEW_MODE and today_weekday == 6:
        send_telegram("⛔ Dimanche : pas de publication YouTube. Le pipeline est désactivé ce jour.")
        print("[SKIP] Dimanche — pas de publication")
        return

    work_dir = Path(f"/tmp/alfred_test_{int(time.time())}")
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path.home() / "output"
    archive_dir = output_dir / "archive"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── STAGE 1 : SCRIPT (1 seul appel LLM) ──
        # Rotation de sous-thèmes pour éviter la répétition
        sub_topics = [
            "Architecture des fonds spéculatifs et capitaux invisibles",
            "Neurobiologie du cerveau d'un investisseur",
            "Théorie des jeux appliquée aux marchés",
            "Asymétrie d'information — pourquoi les riches s'enrichissent",
            "Mécanismes de la dette et du levier financier",
            "Mathématiques du risque — probabilités et espérance de gain",
            "Pièges psychologiques de la finance comportementale",
            "Récits des grandes fortunes historiques",
            "Psychologie du luxe et coût du statut social",
            "Stratégies de sortie — l'art de vendre au bon moment",
        ]
        used_file = WORKSPACE / "state" / "used_subtopics.json"
        used = json.load(open(used_file)) if used_file.exists() else []
        available = [t for t in sub_topics if t not in used[-5:]]
        if not available:
            available = sub_topics
            used = []
        chosen_topic = random.choice(available)
        used.append(chosen_topic)
        used_file.parent.mkdir(parents=True, exist_ok=True)
        with open(used_file, "w") as f:
            json.dump(used[-10:], f)

        charter  = CHARTER_PATH.read_text(errors='ignore')[:1500] if CHARTER_PATH.exists() else ""
        lexicon  = LEXICON_PATH.read_text(errors='ignore')[:1000] if LEXICON_PATH.exists() else ""
        playbook = PLAYBOOK_PATH.read_text(errors='ignore')[:2000] if PLAYBOOK_PATH.exists() else ""

        prompt = (
            "Tu es un expert en Neuro-Finance.\n"
            "RÈGLE ABSOLUE : Tous les textes des segments DOIVENT être 100%% en français. "
            "ZÉRO mot d'anglais. ZÉRO mot d'espagnol.\n"
            "Interdit : hedge fund, smart money, leverage, criterion, storytelling, "
            "dark pattern, exit strategy, trade, trader, deal, portfolio, equity, bond, cognitive.\n"
            "Crée un script Short 40s (4 segments de 10s).\n"
            f"SUJET DU JOUR : {chosen_topic}\n"
            f"CHARTE :\n{charter}\n\nLEXIQUE :\n{lexicon}\n\n"
            f"PLAYBOOK :\n{playbook}\n\n"
            "\n--- STRATÉGIE DU HOOK (inspiré Finary) ---\n"
            "Le segment 1 (ACCROCHE, 0-10s) DOIT commencer par une des techniques suivantes :\n"
            "1. Question personnelle : 'Vous savez combien...' / 'Pourquoi votre cerveau...'\n"
            "2. Chiffre choc : '83 pourcent des investisseurs...'\n"
            "3. Paradoxe : 'Ce qui vous rend riche peut aussi vous ruiner.'\n"
            "4. Attaque de croyance : 'Tout le monde vous ment sur l'épargne.'\n"
            "Le HOOK doit interpeller PERSONNELLEMENT le spectateur (utilisez 'vous').\n"
            "\n--- FORMAT 2 VOIX (dialogue dynamique) ---\n"
            "Alternance de deux voix pour chaque segment :\n"
            "- Voix A (expert, didactique) : les explications, les données, la science\n"
            "- Voix B (contrepoint, provocateur) : les questions, les défis, les punchlines\n"
            "Structure par segment :\n"
            "- Segment 1 [voix B] : question provoquante ou paradoxe qui accroche\n"
            "- Segment 2 [voix A] : déconstruction scientifique, données, biais\n"
            "- Segment 3 [voix A] : le système, la solution, la stratégie\n"
            "- Segment 4 [voix B] : punchline qui boucle avec le hook\n"
            "\n"
            "EXACTEMENT 33 mots par segment pour une narration de 10s. "
            "Ni trop court, ni trop long. 35 mots = 11s, 28 mots = 9s. Vise 33.\n"
            "IMPORTANT : data chiffrée obligatoire, zéro guru-speak, zéro anglais.\n\n"
            "JSON UNIQUEMENT : {\"title\":\"...\",\"description\":\"...\","
            "\"segments\":[{\"text\":\"...\",\"voice\":\"A\",\"duration\":10},...]} "
            "Le champ 'voice' indique 'A' (voix expertise) ou 'B' (voix contrepoint)."
        )

        raw_script, model_used = ask_llm(prompt)

        # ════════════════════════════════════════
        # VALIDATION CONTENU (bloquante)
        # ════════════════════════════════════════
        def validate_script(raw, mdl):
            data = json.loads(raw)
            txt = " ".join(s['text'] for s in data['segments'])
            gs = calculate_guru_score(txt)
            lo = not contains_forbidden_words(txt)
            # Data chiffree obligatoire
            has_data = bool(re.search(r'\d+', txt))
            return data, txt, gs, lo, has_data

        # Une seule tentative de parsing, pas de boucle de review
        try:
            script_data, full_text, guru_score, lang_ok, has_data = validate_script(raw_script, model_used)
        except (json.JSONDecodeError, KeyError):
            # Dernier essai avec fallback
            raw_script, model_used = ask_llm(prompt, MODEL_FALLBACK)
            script_data, full_text, guru_score, lang_ok, has_data = validate_script(raw_script, model_used)

        # Blocage : langue interdite, guru-speak, absence de data
        violations = []
        if not lang_ok:
            violations.append("mots anglais/espagnol interdits")
        if guru_score > 0:
            violations.append(f"guru-speak (score={guru_score})")
        if not has_data:
            violations.append("data chiffrée obligatoire manquante")
        if violations:
            raise Exception(f"Script rejeté : {'; '.join(violations)}. Régénération nécessaire.")

        print(f"[VALIDATION] OK — lang={lang_ok}, guru={guru_score}, data={has_data}")

        title = script_data['title']
        # Description enrichie automatique pour SEO YouTube
        desc_segments = script_data.get('description', '')
        if desc_segments and desc_segments != title:
            hook_line = desc_segments.split('.')[0] + '.'
        else:
            hook_line = f'Pourquoi votre cerveau sous-estime les probabilités — explication neuro-scientifique.'
        # Liste des points clés depuis les segments
        seg_bullets = '\n'.join(f'• {s["text"][:80]}...' for s in script_data['segments'])
        description = (
            f'{hook_line}\n\n'
            f'🎯 Dans cette vidéo :\n{seg_bullets}\n\n'
            f'🔔 Abonnez-vous pour ne rien rater : tous les jours, une révélation sur la neurobiologie de l\'argent.\n'
            f'{DEFAULT_HASHTAGS}'
        )
        segments = script_data['segments']

        # Anti-titre-dupliqué : vérifier les 10 derniers titres dans l'historique
        history_path = PIPELINE_DIR / "PROMPT_HISTORY.json"
        if history_path.exists():
            try:
                history = json.load(open(history_path))
                recent_titles = [h.get('title', '') for h in history[-10:]]
                for old_title in recent_titles:
                    ratio = difflib.SequenceMatcher(None, title.lower(), old_title.lower()).ratio()
                    if ratio > 0.80:
                        raise Exception(f"Titre trop similaire à '{old_title}' (similarité {ratio:.0%}). Régénération nécessaire.")
            except Exception as e:
                if "Régénération" in str(e):
                    raise

        while len(segments) < 4:
            segments.append({"text": "...", "duration": 10})
        segments = segments[:4]

        for s in segments:
            s['duration'] = 10  # forcé à 10s, les clips vidéo durent 10s

        mode_label = "PREVIEW" if PREVIEW_MODE else "Upload"
        send_telegram(
            f"🚀 Pipeline Neuro-Finance lancé\n"
            f"Sujet : {title}\n"
            f"Guru : {guru_score} | LLM : {model_used}\n"
            f"Mode : {mode_label} | Voix : Dual (Remy + Vivienne)")

        # ── STAGE 2 : CLIPS ──
        clip_db = build_clip_database(use_cache=not args.no_cache)
        print(f"[CLIPS] {clip_db['total']} clips, {len(clip_db['sets'])} sets")

        selected_clips, topic_name = smart_select_clips(clip_db)

        for i, clip in enumerate(selected_clips):
            shutil.copy2(clip, work_dir / f"v{i+1}.mp4")
            print(f"  Clip {i+1}: {clip.name}")

        send_telegram(f"[PROD] Clips : {topic_name} ({', '.join(c.name for c in selected_clips)})")

        # ── STAGE 3 : VOICEOVER (par segment, pas fragmenté) ──
        seg_audio_paths = []
        seg_durations = []

        for i, seg in enumerate(segments):
            wav_path = work_dir / f"vo{i+1}.wav"
            voice_label = seg.get('voice', 'A')
            if await generate_voiceover_segment(seg['text'], wav_path, i+1, voice_label):
                dur = get_audio_duration(wav_path)
                seg_audio_paths.append(wav_path)
                seg_durations.append(dur)
                print(f"  VO {i+1}: {dur:.1f}s")
            else:
                # Silence de secours
                subprocess.run([
                    "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", str(seg.get('duration', 10)),
                    str(wav_path), "-y", "-loglevel", "error"
                ], check=True)
                seg_audio_paths.append(wav_path)
                seg_durations.append(float(seg.get('duration', 10)))
                print(f"  VO {i+1}: SILENCE (fallback)")

        # Normalisation audio : PAS d'atempo (ni ralenti, ni accéléré)
        # Les segments trop courts sont paddés avec du silence à la fin
        # Les segments longs restent à leur durée naturelle (voix préservée)
        for i in range(len(seg_audio_paths)):
            dur = seg_durations[i]
            target_dur = max(dur, 10.0)
            if dur < 9.5:
                padded = work_dir / f"vo{i+1}_padded.wav"
                subprocess.run([
                    "ffmpeg", "-i", str(seg_audio_paths[i]),
                    "-af", f"apad=pad_dur={target_dur - dur}",
                    "-t", str(target_dur),
                    str(padded), "-y", "-loglevel", "error"
                ], check=True)
                shutil.move(str(padded), str(seg_audio_paths[i]))
                seg_durations[i] = target_dur
                print(f"  VO {i+1}: {dur:.1f}s → {target_dur:.0f}s silence({target_dur - dur:.1f}s)")
            else:
                print(f"  VO {i+1}: {dur:.1f}s (naturel)")

        # ── STAGE 4 : FONT ──
        font_bold = get_font()
        print(f"[FONT] {font_bold}")

        # ── STAGE 5a : ASSEMBLAGE VIDÉO (PASS 1 — sans texte) ──
        # On assemble les clips avec xfade et l'audio (ambiance + voix)
        # Le texte sera appliqué en PASS 2 pour éviter les chevauchements
        fadelen = 0.5
        filter_parts = []
        v_labels, a_labels = [], []

        for i in range(4):
            video_dur = get_audio_duration(work_dir / f"v{i+1}.mp4")
            audio_dur = seg_durations[i]
            speed = audio_dur / video_dur if video_dur > 0 else 1.0

            # Vidéo : speed, trim, framerate constant — SANS drawtext
            v_proc = (
                f"[{i}:v]setpts=PTS-STARTPTS,setpts={speed}*PTS,"
                f"trim=duration={audio_dur},setpts=PTS-STARTPTS,"
                f"fps=30"
            )
            v_label = f"v{i}"
            v_proc += f"[{v_label}]"
            filter_parts.append(v_proc)
            v_labels.append(f"[{v_label}]")

            a_label = f"a{i}"
            filter_parts.append(
                f"[{i}:a]atrim=0:{audio_dur},asetpts=PTS-STARTPTS,volume=0.3[amb{i}];"
                f"[{i+4}:a]atrim=0:{audio_dur},asetpts=PTS-STARTPTS,volume=1.0[vo{i}];"
                f"[amb{i}][vo{i}]amix=inputs=2:duration=first[{a_label}]"
            )
            a_labels.append(f"[{a_label}]")

        # Crossfade entre clips
        v_tags = [l.strip('[]') for l in v_labels]
        a_tags = [l.strip('[]') for l in a_labels]
        for xi in range(3):
            offset = sum(seg_durations[:xi+1]) - (xi+1) * fadelen
            if xi == 0:
                filter_parts.append(f"[{v_tags[xi]}][{v_tags[xi+1]}]xfade=transition=fade:duration={fadelen}:offset={offset}[t{xi+1}]")
                filter_parts.append(f"[{a_tags[xi]}][{a_tags[xi+1]}]acrossfade=d={fadelen}[c{xi+1}]")
            else:
                filter_parts.append(f"[t{xi}][{v_tags[xi+1]}]xfade=transition=fade:duration={fadelen}:offset={offset}[t{xi+1}]")
                filter_parts.append(f"[c{xi}][{a_tags[xi+1]}]acrossfade=d={fadelen}[c{xi+1}]")
        full_filter = ";".join(filter_parts)

        # Sauvegarde du filtre pour debug
        filter_file = work_dir / "filter_p1.txt"
        filter_file.write_text(full_filter, encoding="utf-8")
        print(f"[FILTER P1] {len(full_filter)} chars")

        inputs = []
        for i in range(1, 5):
            inputs.extend(["-i", str(work_dir / f"v{i}.mp4")])
        for i in range(1, 5):
            inputs.extend(["-i", str(work_dir / f"vo{i}.wav")])

        assembled_mp4 = work_dir / "assembled.mp4"
        subprocess.run([
            "ffmpeg", *inputs,
            "-filter_complex", full_filter,
            "-map", "[t3]", "-map", "[c3]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(assembled_mp4), "-y", "-loglevel", "error"
        ], check=True, timeout=300)

        # ── STAGE 5b : TEXTE (PASS 2 — overlay sur vidéo assemblée) ──
        # On applique le texte avec enable='between(t,start,end)' pour que
        # chaque segment n'apparaisse qu'aux bons moments, sans chevauchement
        # pendant les crossfades.
        assembled_dur = get_audio_duration(assembled_mp4)
        seg_times = []
        for i in range(4):
            seg_start = sum(seg_durations[:i]) - i * fadelen  # position vidéo dans l'assemblage
            txt_start = seg_start + (fadelen if i > 0 else 0)  # texte après le xfade entrant
            txt_end = seg_start + seg_durations[i] - (fadelen if i < 3 else 0)  # texte avant le xfade sortant
            seg_times.append((txt_start, txt_end))

        text_filters = []
        for i, seg in enumerate(segments):
            txt_clean = re.sub(r'[*_]', '', seg['text'])
            txt_clean = txt_clean.replace('%', ' pourcent ')
            lines = textwrap.wrap(txt_clean, width=26)
            line_height = 65
            block_h = len(lines) * line_height
            start_y = min(int(1080 * 0.73), 1080 - block_h - 30)
            t_start, t_end = seg_times[i]

            for j, line in enumerate(lines):
                txt_file = work_dir / f"txt{i}_{j}.txt"
                txt_file.write_text(line, encoding="utf-8")
                esc_txt = str(txt_file).replace(':', '\\:')
                esc_font = font_bold.replace(':', '\\:').replace("'", "\\'")
                text_filters.append(
                    f"drawtext=textfile={esc_txt}:fontfile={esc_font}:"
                    f"fontcolor=white:fontsize=54:"
                    f"x=(w-text_w)/2:y={start_y + j * line_height}:"
                    f"shadowcolor=black@0.8:shadowx=2:shadowy=2:"
                    f"enable='between(t,{t_start},{t_end})'"
                )

        # Chaîne : [0:v]drawtext1,drawtext2,...,drawtextN[outv]
        txt_filter = "[0:v]" + ",".join(text_filters) + "[outv]"
        print(f"[TEXT PASS 2] {len(txt_filter)} chars, {len(text_filters)} drawtext calls")

        final_mp4 = work_dir / "final.mp4"
        subprocess.run([
            "ffmpeg", "-i", str(assembled_mp4),
            "-filter_complex", txt_filter,
            "-map", "[outv]", "-map", "0:a",
            "-af", "loudnorm=I=-14:LRA=8:TP=-1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(final_mp4), "-y", "-loglevel", "error"
        ], check=True, timeout=300)

        final_duration = get_audio_duration(final_mp4)
        if final_duration < 25:
            raise Exception(f"Vidéo trop courte ({final_duration:.1f}s)")
        print(f"[OK] {final_mp4} ({final_duration:.1f}s)")

        # ── STAGE 6 : SAUVEGARDE ──
        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:50]
        persistent_mp4 = output_dir / f"PROD_{datetime.now().strftime('%Y%m%d_%H%M')}_{safe_title}.mp4"
        shutil.copy2(final_mp4, persistent_mp4)

        # ── STAGE 7 : UPLOAD OU PREVIEW ──
        yt_url = None
        if PREVIEW_MODE:
            size_mb = persistent_mp4.stat().st_size / (1024 * 1024)
            send_telegram(f"[PREVIEW] Prêt - {final_duration:.0f}s, {size_mb:.0f}MB")
            if size_mb < 48:
                sec = load_secrets()
                bt, ci = sec.get("TELEGRAM_BOT_TOKEN"), sec.get("TELEGRAM_CHAT_ID")
                if bt and ci:
                    with open(persistent_mp4, "rb") as f:
                        requests.post(
                            f"https://api.telegram.org/bot{bt}/sendVideo",
                            data={"chat_id": ci, "caption": f"🎬 {title}"},
                            files={"video": f}, timeout=180)
            else:
                send_telegram(f"Trop lourd pour Telegram ({size_mb:.0f}MB)")
        else:
            playlist_id = "PLdwDhfX2NgAAuB6rWjAJpr4yETIM4_nmO"
            # Vérification token YouTube avant upload
            token_path = Path.home() / ".secrets" / "youtube_token.json"
            if not token_path.exists():
                raise Exception("Token YouTube introuvable. Lance 'auth_youtube.py' en SSH.")
            try:
                import json as _json
                tk = _json.load(open(token_path))
                if tk.get('expired', False):
                    raise Exception("Token YouTube expiré. Re-authentifie via SSH (python3 skills/youtube_upload/auth_youtube.py)")
            except _json.JSONDecodeError:
                pass

            tags_json = json.dumps(DEFAULT_TAGS)
            cmd = ["python3", str(UPLOAD_PY), str(persistent_mp4), title, description, playlist_id, tags_json]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            output = result.stdout.strip()

            if "youtube.com" in output or "youtu.be" in output:
                yt_url = output
                # Archive
                video_id = yt_url.split("/")[-1]
                history_path = PIPELINE_DIR / "PROMPT_HISTORY.json"
                history = json.load(open(history_path)) if history_path.exists() else []
                history.append({"video_id": video_id, "niche": "NEURO_FINANCE",
                                "title": title, "timestamp": datetime.now().isoformat(),
                                "score": None, "mode": "PROD"})
                with open(history_path, "w") as f:
                    json.dump(history, f, indent=2)
                shutil.move(str(persistent_mp4), str(archive_dir / persistent_mp4.name))
            else:
                err = result.stderr.strip()
                if "uploadLimitExceeded" in err or "exceeded the number of videos" in err:
                    send_telegram(f"⚠️ [PROD] Vidéo prête mais upload YouTube impossible (limite quotidienne). Sauvegardée dans output/.")
                else:
                    raise Exception(f"Upload échoué: {err}")

        # ── RAPPORT ──
        if yt_url:
            send_telegram(f"[{tag}] OK ! {title} → {yt_url}")
        else:
            send_telegram(f"[{tag}] OK - {title} ({final_duration:.0f}s) | LLM: {model_used}")

        print("[OK] Pipeline prod terminé")
        success = True

    except Exception as e:
        print(f"[FAIL] {e}")
        send_telegram(f"[{tag}] Échec : {e}")
    finally:
        if not success:
            fail_dir = WORKSPACE / "failures"
            fail_dir.mkdir(parents=True, exist_ok=True)
            recovery = fail_dir / f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{work_dir.name}"
            shutil.move(str(work_dir), str(recovery))
        else:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())