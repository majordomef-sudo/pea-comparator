#!/usr/bin/env python3
"""
pipeline_orchestrator.py — Pipeline vidéo amélioré (inspiré OpenMontage)
======================================================================
Pipeline stage-based avec :
  - STAGE 1 : SCRIPTS → LLM avec rotation de sujets
  - STAGE 2 : PREFLIGHT → vérification capacités
  - STAGE 3 : ASSETS → génération images (PiAPI) + overlays graphiques (Pillow)
  - STAGE 4 : VOICEOVER → génération audio par segment
  - STAGE 5 : COMPOSE → composition ffmpeg avec Ken Burns + overlays + sous-titres
  - STAGE 6 : VALIDATION → verification dimensions, durée, codec
  - STAGE 7 : UPLOAD → YouTube + Zernio (TikTok/LinkedIn)

Utilise les modules du package pipeline/ :
  - pipeline/preflight.py
  - pipeline/asset_generator.py
  - pipeline/scene_composer.py
"""

import os, sys, json, random, re, time, asyncio, shutil, difflib, subprocess, traceback
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import requests, edge_tts

# Ajouter les chemins pour les imports
SCRIPT_DIR = Path(__file__).parent.resolve()
WORKSPACE_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(WORKSPACE_DIR))
sys.path.insert(0, str(WORKSPACE_DIR / "skills" / "alfred_cron"))

from pipeline.preflight import run_preflight, print_report, check_can_produce
from pipeline.asset_generator import (
    generate_scene_images,
    create_title_card,
    create_end_card,
    create_overlay_sequence,
    create_youtube_thumbnail,
    load_secrets,
)
from pipeline.director import StageDirector
from pipeline.pipeline_config import load_config, model_main, model_fallback
# ── CONFIG CENTRALISÉE (pipeline_config.yaml → config_loader) ─────
from pipeline.config_loader import (
    GURU_BLACKLIST, FORBIDDEN_WORDS, PHONETIC_FIXES,
    DEFAULT_TAGS, DEFAULT_HASHTAGS, RICH_DESC_TEMPLATE, PLAYLIST_ID,
    get_guru_blacklist, get_forbidden_words, get_phonetic_fixes,
    get_default_tags, get_default_hashtags, get_rich_description_template,
    get_playlist_id,
)

# ── SIGNAL HANDLING ─────────────────────────────────────
import signal as _signal
def _cleanup_handler(signum, frame):
    print(f"[SIGNAL] Received {_signal.Signals(signum).name}, cleaning...")
    try:
        lp = "/tmp/alfred_pipeline.lock"
        if __import__("os").path.exists(lp):
            __import__("os").unlink(lp)
    except OSError as cleanup_error:
        print(f"[SIGNAL] Échec suppression du verrou: {cleanup_error}")
    __import__("os")._exit(1)
_signal.signal(_signal.SIGTERM, _cleanup_handler)
_signal.signal(_signal.SIGINT, _cleanup_handler)
# ──────────────────────────────────────────────────────────

# ── COST TRACKING ───────────────────────────────────────
LLM_COST_LOG = __import__("pathlib").Path.home() / "output" / "logs" / "llm_costs.jsonl"
LLM_PRICES = {
    "deepseek/deepseek-v4.1-flash": {"input": 0.15, "output": 0.60},
    "deepseek/deepseek-v4-pro": {"input": 0.50, "output": 1.50},
    "google/gemma-4-31b-it": {"input": 0.10, "output": 0.34},
    "google/gemma-4-26b-a4b-it": {"input": 0.07, "output": 0.34},
}
def track_llm_cost(model, prompt_tokens, completion_tokens):
    try:
        prices = LLM_PRICES.get(model, {"input": 0.25, "output": 0.75})
        cost = (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1_000_000
        LLM_COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LLM_COST_LOG, "a") as f:
            __import__("json").dump({
                "ts": __import__("datetime").datetime.now().isoformat(),
                "model": model, "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": round(cost, 6)
            }, f)
            f.write("\n")
        return cost
    except (OSError, TypeError, ValueError) as cost_error:
        print(f"[COST] Suivi des coûts impossible: {cost_error}")
        return 0
# ──────────────────────────────────────────────────────────

try:
    from tools.virality_scanner import scanner as virality_scanner
except ImportError:
    print("[WARN] tools.virality_scanner non trouvé — scanner viral désactivé")
    class _DummyScanner:
        @staticmethod
        def scan_text_for_hooks(text):
            return []
        @staticmethod
        def scan_video(video_path):
            return {}
        @staticmethod
        def scan_text(text):
            return []
    virality_scanner = _DummyScanner()

from pipeline.scene_composer import compose_final_video
# Late-bound imports avec fallback silencieux
# Use local word_timings module (cached whisper, zero network dependency)
try:
    from pipeline.word_timings import burn_ass_captions, get_word_timings
    from skills.alfred_cron.caption_burner import make_ass_captions
except ImportError:
    from word_timings import make_ass_captions, burn_ass_captions, get_word_timings

try:
    from skills.alfred_cron.zernio_uploader import upload_video as zernio_upload_video
except ImportError:
    def zernio_upload_video(*a, **kw): return {"success": False, "error": "zernio_uploader non disponible"}
    print("[WARN] zernio_uploader non trouvé — cross-post Zernio désactivé")

# Analyse vidéo auto + apprentissage
_ANALYSIS_PATH = str(WORKSPACE_DIR / "skills" / "video-analysis" / "scripts")
_MODULES_PATH = str(WORKSPACE_DIR / "skills" / "video-analysis" / "scripts" / "modules")
if _ANALYSIS_PATH not in sys.path:
    sys.path.insert(0, _ANALYSIS_PATH)
if _MODULES_PATH not in sys.path:
    sys.path.insert(0, _MODULES_PATH)
try:
    from analyze_video import analyze
except ImportError:
    analyze = None
    print("[WARN] analyze_video non trouvé — analyse vidéo auto désactivée (source manquante)")
from learning import store_analysis, detect_patterns, generate_lessons, get_prompt_lessons


# ── CONFIG ──────────────────────────────────────────────────────────

SECRETS_ENV = Path.home() / ".secrets/env"
WORKSPACE = Path(os.environ.get("ALFRED_WORKSPACE", str(Path.home() / ".openclaw" / "workspace")))
PIPELINE_DIR = WORKSPACE / "skills/alfred_video_pipeline"

PLAYBOOK_PATH = PIPELINE_DIR / "PLAYBOOK_NEURO_FINANCE.md"
CHARTER_PATH = PIPELINE_DIR / "EDITORIAL_CHARTER_NEURO_FINANCE.md"
LEXICON_PATH = PIPELINE_DIR / "SEMANTIC_LEXICON_NEURO_FINANCE.md"
PERFORMANCE_MD = PIPELINE_DIR / "PERFORMANCE.md"

UPLOAD_PY = WORKSPACE / "skills/youtube_upload/upload.py"

RAW_CLIPS_ROOT = Path.home() / "output" / "raw_clips"
CLIP_CACHE_FILE = WORKSPACE / "state" / "clip_db_cache.json"

# Modèles LLM
MODEL_MAIN = model_main()
MODEL_FALLBACK = model_fallback()  # fallback centralise dans pipeline_config.yaml

# Tags YouTube


# ── HELPERS ─────────────────────────────────────────────────────────

def send_telegram(msg):
    print(f"[TG] {msg}")
    secrets = load_secrets()
    bt = secrets.get("TELEGRAM_BOT_TOKEN")
    ci = secrets.get("TELEGRAM_CHAT_ID")
    if bt and ci:
        try:
            requests.post(
                f"https://api.telegram.org/bot{bt}/sendMessage",
                data={"chat_id": ci, "text": msg}, timeout=10
            )
        except Exception as e:
            print(f"[TG ERR] {e}")


def send_telegram_video(video_path, caption="", max_mb=45):
    import os as _os
    if not _os.path.isfile(video_path):
        print("[TG VIDEO] introuvable")
        return False
    size_mb = _os.path.getsize(video_path) / 1048576.0
    if size_mb > max_mb:
        print("[TG VIDEO] trop lourd")
        return False
    secrets = load_secrets()
    bt = secrets.get("TELEGRAM_BOT_TOKEN")
    ci = secrets.get("TELEGRAM_CHAT_ID")
    if not (bt and ci):
        print("[TG VIDEO] token manquant")
        return False
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{bt}/sendVideo",
                data={"chat_id": ci},
                files={"video": f},
                timeout=300
            )
        ok = r.status_code == 200
        print("[TG VIDEO] sent", ok, size_mb)
        return ok
    except Exception as e:
        print("[TG VIDEO ERR]", e)
        return False


def ask_llm(prompt, model=MODEL_MAIN, max_tokens=1500, temperature=0.7):
    """Appel LLM avec fallback automatique."""
    secrets = load_secrets()
    api_key = secrets.get("OPENROUTER_API_KEY")
    url = "ht" + "tps://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    models_to_try = [model] if model != MODEL_MAIN else [MODEL_MAIN, MODEL_FALLBACK]

    for m in models_to_try:
        for attempt in range(1 if m == "deepseek/deepseek-v4-pro" else 3):
            try:
                resp = requests.post(url, headers=headers, json={
                    "model": m, "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature, "max_tokens": max_tokens, **({"reasoning": {"max_tokens": 800, "exclude": True}, "response_format": {"type": "json_object"}} if "deepseek" in m else {})
                }, timeout=(10, 45))
                if resp.status_code == 429:
                    time.sleep(2 ** attempt + random.random())
                    continue
                resp.raise_for_status()
                data = resp.json()
                c = data["choices"][0]["message"]["content"]
                if not c or not c.strip(): raise ValueError(f"Réponse vide: finish_reason={data["choices"][0].get("finish_reason")}, message={data["choices"][0].get("message")}")
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", c, re.DOTALL)
                return (match.group(1) if match else c).strip(), m
            except Exception as e:
                if attempt == (0 if m == "deepseek/deepseek-v4-pro" else 2):
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


# ── VALIDATION ──────────────────────────────────────────────────────






def _term_found(text, term):
    return bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.IGNORECASE))


def calculate_guru_score(text):
    hits = [t for t in GURU_BLACKLIST if _term_found(text, t)]
    if hits: print(f"[GURU] termes détectés: {hits}")
    return len(hits)


def contains_forbidden_words(text):
    hits = [w for w in FORBIDDEN_WORDS if _term_found(text, w)]
    if hits: print(f"[LANG] termes interdits: {hits}")
    return bool(hits)

# ── CLIP DATABASE (fallback si pas d'images générées) ──────────────



# -- REGLES LONGUEUR + STRUCTURE HOOK (mesurees le 27/09/2026 sur 44 videos) --
SEG1_MIN, SEG1_MAX = 16, 24
SEG_OTHER_MIN, SEG_OTHER_MAX = 46, 55
# Plancher de padding d'un segment audio (secondes). C'est un filet de securite
# pour un TTS en echec, PAS une cible. Ne jamais remonter a 9s : une accroche
# courte (16-24 mots, environ 8s) etait remplie de 2.1s de silence, ce qui a cree
# un trou de 3.0s juste apres le hook -> rejet QA le 27/09/2026.
PAD_MIN_SEGMENT_S = 4.0
TOTAL_MIN = SEG1_MIN + 3 * SEG_OTHER_MIN
TOTAL_MAX = SEG1_MAX + 3 * SEG_OTHER_MAX
HOOK_FIRST_SENTENCE_MAX_WORDS = 14  # seuil aligne sur les 2 meilleures videos (10 et 14 mots) ; objectif demande au LLM : 10 a 12
HOOK_JARGON = ["drawdown", "trade", "trader", "equity", "bond", "portfolio", "leverage", "hedge fund", "smart money", "exit strategy"]

def count_words(text):
    return len(re.findall(r"\b[\w\u00c0-\u00ff\d\'-]+\b", text))

def word_counts_ok(word_counts):
    """Accroche courte (16-24 mots), segments 2 a 4 entre 46 et 55, total 154-189."""
    if len(word_counts) != 4:
        return False
    return (
        SEG1_MIN <= word_counts[0] <= SEG1_MAX
        and all(SEG_OTHER_MIN <= c <= SEG_OTHER_MAX for c in word_counts[1:])
        and TOTAL_MIN <= sum(word_counts) <= TOTAL_MAX
    )

def title_quality_issues(title):
    """Regles de titre issues des donnees reelles de la chaine (27/09/2026).
    Mesure : titres adresses au spectateur + enjeu concret = 128 a 147 vues ;
    titres nominaux abstraits (L erreur de..., La science de...) = 0 a 5 vues."""
    t = (title or "").strip()
    if not t:
        return ["titre vide"]
    norm = t.replace("\u2019", "'").replace("\u2018", "'")
    low = norm.lower()
    issues = []
    if len(t) > 75:
        issues.append("titre trop long (> 75 caracteres)")
    if len(t) < 20:
        issues.append("titre trop court (< 20 caracteres)")
    has_you = bool(re.search(r"\b(vous|votre|vos)\b", low))
    has_q = bool(re.search(r"^(pourquoi|comment|combien|faut-il|est-ce)", low)) or "?" in t
    has_num = bool(re.search(r"[0-9]", t))
    abstract_openers = (
        r"^l'\s*(erreur|illusion|science|art|secret|piege|paradoxe|danger|mythe|verite|puissance|force|loi|methode|psychologie|anatomie)",
        r"^la\s+(science|puissance|force|loi|verite|psychologie|methode|face cached)",
        r"^le\s+(test|piege|mythe|secret|danger|vrai|faux|cout)",
        r"^les\s+(secrets|pieges|mythes|erreurs)",
    )
    is_abstract = any(re.search(pat, low) for pat in abstract_openers)
    if is_abstract and not has_you and not has_num and not has_q:
        issues.append("titre nominal abstrait (L erreur de / La science de / Le piege de...) sans adresse au spectateur ni chiffre : format mesure a 0-5 vues")
    if not (has_you or has_q or has_num):
        issues.append("titre sans accroche : aucun (vous/votre/vos), aucune question, aucun chiffre")
    return issues


def pick_hook_variant(when=None):
    """Variante d accroche du jour. A = question directe, B = constat sec + bascule vous.
    Alternance deterministe par jour (reproductible, equilibre sur 2 jours)."""
    import datetime as _dt
    d = when or _dt.date.today()
    return "A" if (d.toordinal() % 2 == 0) else "B"


def record_ab_assignment(variant, title, word_counts=None, test_id="ab_001"):
    """Journalise l affectation A/B reelle de la video.
    Trou corrige le 27/09 : ab_001 etait 'running' depuis le 30/07 avec 0 video assignee."""
    import json as _json
    import datetime as _dt
    path = WORKSPACE_DIR / "state" / "auto-reflection" / "ab-testing.json"
    try:
        data = _json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"tests": []}
    except Exception:
        data = {"tests": []}
    if not isinstance(data, dict):
        data = {"tests": []}
    tests = data.setdefault("tests", [])
    t = next((x for x in tests if isinstance(x, dict) and x.get("id") == test_id), None)
    if t is None:
        t = {"id": test_id, "started": _dt.datetime.now().isoformat(), "status": "running"}
        tests.append(t)
    t["name"] = "Hook: variante A (question directe) vs variante B (constat + bascule vous)"
    t["metric"] = "averageViewPercentage (retention YouTube Analytics, 90 j)"
    t["status"] = "running"
    t.setdefault("assignments", [])
    t["assignments"].append({
        "date": _dt.date.today().isoformat(),
        "variant": variant,
        "title": title,
        "word_counts": word_counts,
    })
    t["videos_a"] = sum(1 for a in t["assignments"] if a.get("variant") == "A")
    t["videos_b"] = sum(1 for a in t["assignments"] if a.get("variant") == "B")
    data["last_test"] = test_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def hook_structure_issues(segments, variant=None):
    """Structure de l accroche. Mesure du 27/09/2026 (retention reelle, 7 videos >= 10 vues) :
    l interdiction de la question n est PAS soutenue par les donnees (question 37,7 % de %vu
    contre 12,0 % pour une affirmation). Les deux formes sont donc autorisees ; c est le test
    A/B ab_001, mesure sur la retention, qui tranche.
      - variante A : la premiere phrase DOIT etre une question directe
      - variante B : premiere phrase = constat sec, puis bascule explicite sur le spectateur
    Regles communes : premiere phrase <= 14 mots, 3 phrases maximum."""
    if not segments:
        return ["accroche absente"]
    hook = str(segments[0].get("text", "")).strip()
    if not hook:
        return ["accroche vide"]
    phrases = [p.strip() for p in re.split(r"(?<=[.!?])\s+", hook) if p.strip()]
    first = phrases[0] if phrases else ""
    issues = []
    is_question = first.endswith("?")
    low = " " + hook.lower() + " "
    has_vous = any(t in low for t in (" vous ", " votre ", " vos "))
    if count_words(first) > HOOK_FIRST_SENTENCE_MAX_WORDS:
        issues.append("accroche : premiere phrase trop longue (%d mots, max %d)" % (
            count_words(first), HOOK_FIRST_SENTENCE_MAX_WORDS))
    if len(phrases) > 3:
        issues.append("accroche : %d phrases (3 maximum)" % len(phrases))
    if variant == "A":
        if not is_question:
            issues.append("accroche variante A : la premiere phrase doit etre une question directe")
    elif variant == "B":
        if is_question:
            issues.append("accroche variante B : la premiere phrase doit etre un constat, pas une question")
        if not has_vous:
            issues.append("accroche variante B : aucune bascule sur le spectateur (vous)")
    else:
        if (not is_question) and (not has_vous):
            issues.append("accroche : ni question, ni bascule sur le spectateur (vous)")
    if (variant in (None, "", "B")) and not is_question:
        generiques = ("de nombreux", "une grande partie", "la plupart", "beaucoup de", "il est")
        suite = " ".join(phrases[1:3]).lower()
        if first.lower().startswith(generiques) and ("vous" not in suite):
            issues.append("accroche : constat a la 3e personne sans retournement immediat sur vous")
    return issues


def validate_script_data(segments, model="deepseek/deepseek-v4-pro", reference_block=""):
    """
    Valide que les donnees chiffrees du script sont plausibles.
    Utilise un LLM pour fact-checker chaque segment.
    Retourne (is_valid, issues) ou issues est une liste de problemes detectes.
    """
    full_text = "\n\n".join(f"SEGMENT {i+1}: {s['text']}\nSTAT_VALUE: {s.get('stat_value', '')}" for i, s in enumerate(segments))

    prompt = (
        "Tu es un fact-checker specialise en finance. Analyse ce script de video YouTube Shorts.\n"
        "MISSION : reperer UNIQUEMENT les affirmations factuelles PRECISES qui necessitent une source et qui sont fausses, exagerees ou inverifiables.\n\n"
        "A SIGNALER (vrai probleme) :\n"
        "- statistique chiffree precise non sourcee et inverifiable (ex: '90% des investisseurs vendent au plus bas') ;\n"
        "- etude, rapport ou autorite non identifiee ('la science montre', 'une etude prouve') ;\n"
        "- causalite deterministe presentee comme une loi absolue (ex: 'ce mecanisme force la vente au plus bas') ;\n"
        "- chiffre faux ou mathematiquement incoherent.\n\n"
        "A NE JAMAIS SIGNALER (style editorial tolere) :\n"
        "- opinion, jugement ou these assumee ('le pire moment pour vendre, c'est quand vous avez peur') ;\n"
        "- question rhetorique, metaphore, punchline, formule d'accroche ;\n"
        "- conseil general non chiffre ('gardez votre cap', 'resister a la panique') ;\n"
        "- tendance generale NON chiffree, meme au present ('beaucoup d'investisseurs ont tendance a vendre sous stress') ;\n"
        "- reformulation qualitative d'un biais connu (aversion aux pertes, exces de confiance) sans chiffre precis.\n\n"
        "REGLE D'ARBITRAGE : si la phrase reste une opinion ou une tendance generale une fois le chiffre exact ou l'attribution a une source retire, alors elle est ACCEPTEE. Ne signale que ce qui affirme un fait precis.\n"
        + ("VALEURS DE RÉFÉRENCE AUTORISÉES (déjà vérifiées et sourcées) :\n" + reference_block +
           "\nCes valeurs sont DÉJÀ SOURCÉES : tout chiffre qui correspond exactement à l'une d'elles NE DOIT PAS être signalé comme invérifiable. "
           "Ne signale un chiffre que s'il ne figure PAS dans ce référentiel.\n\n" if reference_block else "")
        + "Ne considère jamais un chiffre comme vrai sans contexte fiable. Ne crée aucune nouvelle statistique.\n"
        "Chaque STAT_VALUE doit contenir uniquement une valeur numérique exactement présente dans le texte du segment, sans préfixe comme exemple, sans formule et sans commentaire.\n"
        "Si une affirmation est invérifiable, propose une reformulation avec un chiffre simple et vérifiable : année officielle, durée, montant illustratif clairement présenté comme exemple, ou calcul mathématique exact. N’invente aucun pourcentage comportemental.\n\n"
        "Format de reponse (JSON UNIQUEMENT) :\n"
        '{"valid": true/false, "issues": [{"segment": 1, "claim": "...", "reason": "...", "suggestion": "..."}]}\n'
        "Renvoie valid=true et issues=[] si tout est correct.\n\n"
        f"SCRIPT A ANALYSER :\n{full_text}"
    )

    try:
        raw, _ = ask_llm(prompt, model=model, max_tokens=9000, temperature=0.1)
        from json_repair import repair_json; result = json.loads(repair_json(raw))
        if not isinstance(result, dict):
            print(f"[DATA-VALIDATION] Réponse JSON inattendue: type={type(result).__name__}, brut={raw[:1000]!r}")
            return False, [{"segment": 0, "claim": "Reponse invalide", "reason": "Format JSON incorrect", "suggestion": "Relancer le fact-check DeepSeek V4 Pro"}]
        issues = result.get("issues", [])
        is_valid = result.get("valid", len(issues) == 0)
        return is_valid, issues
    except Exception as e:
        print(f"[DATA-VALIDATION] Fact-check Pro échoué: {e}")
        try:
            raw, _ = ask_llm(
                prompt,
                model="deepseek/deepseek-v4.1-flash",
                max_tokens=9000,
                temperature=0.1
            )
            from json_repair import repair_json
            result = json.loads(repair_json(raw))
            if not isinstance(result, dict):
                raise ValueError(
                    f"Réponse Flash invalide: {type(result).__name__}"
                )
            issues = result.get("issues", [])
            is_valid = result.get("valid", len(issues) == 0)
            print("[DATA-VALIDATION] Fact-check récupéré via Flash")
            return is_valid, issues
        except Exception as fallback_error:
            print(f"[DATA-VALIDATION] Fallback fact-check Flash échoué: {fallback_error}")
            return False, [{
                "segment": 0,
                "claim": "Validation impossible",
                "reason": str(fallback_error),
                "suggestion": "Relancer le fact-check"
            }]
def build_clip_database(use_cache=True):
    """Scan raw_clips/ avec cache JSON — fallback si PiAPI indisponible."""
    if use_cache and CLIP_CACHE_FILE.exists():
        try:
            mtime_db = CLIP_CACHE_FILE.stat().st_mtime
            newest_clip = max(
                (p.stat().st_mtime for p in RAW_CLIPS_ROOT.rglob("*.mp4")), default=0
            )
            newest_dir = max(
                (d.stat().st_mtime for d in RAW_CLIPS_ROOT.iterdir() if d.is_dir()), default=0
            )
            if max(newest_clip, newest_dir) <= mtime_db:
                with open(CLIP_CACHE_FILE) as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as cache_error:
            print(f"[CLIPS] Cache inutilisable, reconstruction: {cache_error}")

    topics = defaultdict(list)
    pattern = re.compile(r"^(.+?)_v[1-4]\.mp4$")
    for clip_path in sorted(RAW_CLIPS_ROOT.rglob("*.mp4")):
        m = pattern.match(clip_path.name)
        topic = m.group(1) if m else re.sub(r"(_v[1-4])?\.mp4$", "", clip_path.name)
        topics[topic].append(str(clip_path))

    date_topic_map = defaultdict(list)
    for topic, clip_strs in topics.items():
        for c_str in clip_strs:
            c = Path(c_str)
            date_dir = c.parent.name
            date_topic_map[(date_dir, topic)].append(c_str)

    sets = [{"topic": t, "date": d, "clips": clips, "size": len(clips)}
            for (d, t), clips in sorted(date_topic_map.items())]

    db = {"topics": dict(topics), "sets": sets, "total": sum(len(v) for v in topics.values())}

    CLIP_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CLIP_CACHE_FILE, "w") as f:
        json.dump(db, f)
    return db


def smart_select_clips(clip_db, n=4):
    """Sélectionne n clips avec priorité set cohérent — fallback."""
    sets = clip_db.get("sets", [])
    topics = clip_db["topics"]
    if not topics:
        raise Exception("Aucun clip disponible")

    coherent = [s for s in sets if s["size"] >= n]
    if coherent:
        chosen = random.choice(coherent)
        selected = sorted(chosen["clips"],
                          key=lambda p: int(re.search(r"_v(\d+)\.mp4$", Path(p).name).group(1)))
        return [Path(p) for p in selected], f"{chosen['topic']} ({chosen['date']})"

    for t, clips in sorted(topics.items(), key=lambda x: -len(x[1])):
        if len(clips) >= n:
            selected = random.sample([Path(p) for p in clips], n)
            return selected, f"{t} (multidate)"

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


# ── VOICEOVER ───────────────────────────────────────────────────────

async def generate_voiceover_segment(text, out_path, seg_idx, voice="A"):
    """Génère la voix pour un segment avec Remy (A) ou Vivienne (B)."""
    clean = re.sub(r"[*_]", "", text)
    for bad, good in PHONETIC_FIXES.items():
        clean = re.sub(re.escape(bad), good, clean, flags=re.IGNORECASE)

    voice_name = "fr-FR-HenriNeural" if voice == "A" else "fr-FR-DeniseNeural"
    print(f"[VOICE] Segment {seg_idx}: voix {"Henri" if voice == "A" else "Denise"}")
    tmp_mp3 = out_path.parent / f"vo{seg_idx}.tmp.mp3"
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


# ── SUB-TOPICS ROTATION ────────────────────────────────────────────

SUB_TOPICS = [
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


def pick_topic():
    """Rotation de sujet avec historique. Sujet force si queue active."""
    # Verifier si une idee est dans la queue
    queue_override = Path("/tmp/alfred_next_topic.txt")
    if queue_override.exists():
        try:
            topic = queue_override.read_text().strip()
            queue_override.unlink()
            print(f"[TOPIC] Queue override: {topic}")
            return topic
        except Exception as e:
            print(f"[TOPIC] Queue override error: {e}")

    used_file = WORKSPACE / "state" / "used_subtopics.json"
    used = json.load(open(used_file)) if used_file.exists() else []
    available = [t for t in SUB_TOPICS if t not in used[-5:]]
    if not available:
        available = SUB_TOPICS
        used = []
    chosen = random.choice(available)
    used.append(chosen)
    used_file.parent.mkdir(parents=True, exist_ok=True)
    with open(used_file, "w") as f:
        json.dump(used[-10:], f)
    return chosen


# ── MAIN ────────────────────────────────────────────────────────────

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline vidéo amélioré")
    parser.add_argument("--topic", type=str, default=None, help="Sujet imposé par la file d idées")
    parser.add_argument("--auto", action="store_true", help="Exécution automatique depuis la file d idées")
    parser.add_argument("--preview", action="store_true", help="Skip YouTube upload")
    parser.add_argument("--no-cache", action="store_true", help="Force rebuild clip DB")
    parser.add_argument("--skip-image-gen", action="store_true",
                        help="Skip PiAPI image generation, use clips")
    args, _ = parser.parse_known_args()

    # ── Lock file anti-pipelines concurrents ──
    LOCK_FILE = Path(f"/tmp/alfred_pipeline.lock")
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            os.kill(old_pid, 0)  # Vérifie si le process existe
            send_telegram(f"⛔ Pipeline déjà en cours (PID {old_pid}). Skipping.")
            print(f"[LOCK] Pipeline déjà en cours (PID {old_pid})")
            return
        except (OSError, ValueError, ProcessLookupError):
            pass  # Lock stale
    LOCK_FILE.write_text(str(os.getpid()))

    PREVIEW_MODE = args.preview
    tag = "PREVIEW" if PREVIEW_MODE else "PROD"
    success = False


    # ── PREFLIGHT ──
    print("\n" + "=" * 50)
    print("  STAGE 0 : PREFLIGHT")
    print("=" * 50)
    preflight = run_preflight()
    print_report(preflight)

    if not check_can_produce(preflight):
        send_telegram(f"[{tag}] ❌ Preflight échoué : {'; '.join(preflight['blockers'])}")
        return

    print("[PREFLIGHT] Mode clips vidéo (réserve raw_clips)")

    work_dir = Path(f"/tmp/alfred_pipeline_{int(time.time())}")
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path.home() / "output"
    archive_dir = output_dir / "archive"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    # ── CONFIG LOAD (once) ──
    try:
        _pipeline_config = load_config()
    except Exception as config_error:
        raise RuntimeError(
            f"Configuration pipeline invalide: {config_error}"
        ) from config_error

    video_config = _pipeline_config.get("video", {})
    # 27/09 : carte titre reduite 3.0s -> 1.2s. 18% des videos perdaient le spectateur avant 5s
    # (donnees retention 90j) : 3s de carte muette en ouverture = zone morte sur Shorts.
    title_duration = 1.2
    transition_duration = float(video_config.get("transition_duration", 0.5))
    target_fps = int(video_config.get("fps", 30))
    _shorts_mode = video_config.get("mode", "normal") == "shorts"

    try:
        t_width, t_height = map(
            int,
            video_config.get("resolution", "1080x1920").split("x")
        )
    except (TypeError, ValueError) as resolution_error:
        raise RuntimeError(
            f"Résolution vidéo invalide: {video_config.get('resolution')}"
        ) from resolution_error

    if _shorts_mode and t_width >= t_height:
        raise RuntimeError(
            f"Mode Shorts incohérent avec la résolution {t_width}x{t_height}"
        )

    try:
        # ════════════════════════════════════════════
        # STAGE 1 : SCRIPT (LLM)
        # ════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("  STAGE 1 : SCRIPT")
        print("=" * 50)

        chosen_topic = args.topic.strip() if args.topic else pick_topic()
        
        # --- VIRALITY SCANNING (CLIPIFY LOGIC) ---
        # On analyse le sujet pour suggérer des hooks "Reversal" au LLM
        virality_hooks = virality_scanner.scan_text_for_hooks(chosen_topic)
        hook_suggestion = ""
        if virality_hooks:
            best_hook = virality_hooks[0]['text']
            hook_suggestion = f"Angle viral suggéré : '{best_hook}' (Score: {virality_hooks[0]['score']})"
        # ----------------------------------------

        charter = CHARTER_PATH.read_text(errors="ignore")[:1500] if CHARTER_PATH.exists() else ""
        lexicon = LEXICON_PATH.read_text(errors="ignore")[:1000] if LEXICON_PATH.exists() else ""
        playbook = PLAYBOOK_PATH.read_text(errors="ignore")[:2000] if PLAYBOOK_PATH.exists() else ""

        LEARNING_INJECTION = get_prompt_lessons()

        # --- DONNEES REELLES (snapshot source : Yahoo + Eurostat + BCE + base ETF) ---
        try:
            from pipeline.market_data_snapshot import build_prompt_block
            MARKET_DATA_BLOCK = build_prompt_block()
        except Exception as snapshot_error:  # noqa: BLE001
            print(f"[SNAPSHOT] indisponible ({snapshot_error}) - fallback sans donnees reelles")
            MARKET_DATA_BLOCK = ""
        if MARKET_DATA_BLOCK:
            print(f"[SNAPSHOT] Donnees reelles injectees ({len(MARKET_DATA_BLOCK)} car.)")
        else:
            print("[SNAPSHOT] Aucune donnee reelle - regles chiffres seules")
        # -------------------------------------------------------------------------------
        overrides_path = WORKSPACE_DIR / "state" / "video_analysis" / "config_overrides.json"
        overrides_text = ""
        if overrides_path.exists():
            import json
            overrides = json.loads(overrides_path.read_text())
            for o in overrides:
                if o.get("applied") is not True:
                    continue
                overrides_text += f"- {o.get('action', '' )}\\n"
        active_fixes = {
            override.get("fix", "")
            for override in overrides
            if override.get("applied") is True
        } if overrides_path.exists() else set()
        trim_silence_aggressive = "auto_trim_silence" in active_fixes




        
        # --- AGENTIC DIRECTIVE (OpenMontage) ---
        director_info = StageDirector.get_directive("script")
        directive_text = f"OBJECTIF : {director_info['goal']}\\nCRITÈRES : {', '.join(director_info['criteria'])}"
        # ----------------------------------------

        hook_variant = pick_hook_variant()
        if hook_variant == "A":
            hook_variant_label = "A (question directe)"
            hook_variant_rule = ("La premiere phrase du segment 1 DOIT etre une question directe, 14 mots maximum. "
                                 "Pas de constat avant la question. Forme attendue : une question qui vise la situation du spectateur. "
                                 "Exemples de forme (a ne pas recopier) : Pourquoi agir sans cesse ? Combien de fois avez-vous verifie vos comptes aujourd hui ?")
        else:
            hook_variant_label = "B (constat sec puis bascule vous)"
            hook_variant_rule = ("La premiere phrase DOIT etre un constat sec de 14 mots maximum, et la phrase suivante DOIT basculer "
                                 "explicitement sur le spectateur (vous, votre, vos). Exemple de forme (a ne pas recopier) : "
                                 "De nombreux investisseurs surevaluent leur capacite a predire les marches. Vous pensez que votre intelligence vous protege ? C est une erreur fatale.")
        print(f"[AB] variante d accroche du jour : {hook_variant_label}")
        prompt = (
            "Tu es un expert en Neuro-Finance.\n"
            "RÈGLE ABSOLUE : Tous les textes des segments DOIVENT être 100% en français. "
            "ZÉRO mot d'anglais. ZÉRO mot d'espagnol.\n"
            "Interdit : hedge fund, smart money, leverage, criterion, storytelling, "
            "dark pattern, exit strategy, trade, trader, deal, portfolio, equity, bond.\n"
            "ORTHOGRAPHE : zéro faute. Accents obligatoires (é, è, ê, à, ù, ç, ô, î, û).\n\n"
            "Cr\u00e9e exactement 4 segments. SEGMENT 1 (ACCROCHE) : 16 \u00e0 24 mots, 2 phrases maximum. SEGMENTS 2 \u00e0 4 : 46 \u00e0 55 mots chacun. TOTAL : 154 \u00e0 189 mots. La vid\u00e9o finale dure environ 60 \u00e0 80 secondes avec le titre, les transitions et la carte de fin.\n"
            f"SUJET DU JOUR : {chosen_topic}\n"
            f"CHARTE :\n{charter}\n\nLEXIQUE :\n{lexicon}\n\n"
            f"PLAYBOOK :\n{playbook}\n\n"
            f"AUTO-FIXES :\\n{overrides_text}\\n\\n"

            f"DIRECTIVE DU RÉALISATEUR :\n{directive_text}\n\n"
            f"SUGGESTION VIRALE : {hook_suggestion if hook_suggestion else 'Utilise un angle contre-intuitif.'}\n"
            "--- FRAMEWORK DE VIRALITÉ (AI Youtube Shorts Generator) ---\n"
            "Chaque segment DOIT activer AU MOINS UN de ces signaux viraux :\n"
            "1. HOOK MOMENT — phrase qui crée une curiosité immédiate "
            "('Le mécanisme que presque personne ne remarque...', 'Votre cerveau vous ment sur...')\n"
            "2. OPINION BOMB — déclaration forte, contre-intuitive qui pousse à réagir\n"
            "3. REVELATION — fait ou statistique surprenant qui change la perspective\n"
            "4. CONFLIT/TENSION — problème affronté directement, dilemme\n"
            "5. QUOTABLE ONE-LINER — phrase courte qui marche comme citation standalone\n"
            "6. STORY PEAK — climax ou twist d'une anecdote\n"
            "7. PRACTICAL VALUE — conseil concret applicable immédiatement\n"
            "\n"
            "--- STRATÉGIE DU HOOK ---\n"
                        f"--- STRATEGIE DU HOOK (variante A/B, mesuree sur la retention le 27/09/2026) ---\\n"
            f"VARIANTE IMPOSEE AUJOURD HUI : {hook_variant_label}. {hook_variant_rule}\\n"
            "Segment 1 (ACCROCHE) : 2 phrases conseillees (3 maximum), 16 a 24 mots au total, soit 6 a 9 secondes.\\n"
            "Phrase 1 : 10 a 12 mots (14 maximum), posee des les 3 premieres secondes. Phrase 2 : la bascule ou la consequence directe pour le spectateur.\\n"
            "Ne recopie jamais un exemple mot pour mot : adapte-le au sujet du jour. Evite le jargon anglophone (prefere baisse a drawdown).\\n"
            "Le HOOK doit interpeller PERSONNELLEMENT le spectateur (vous, votre, vos), sauf en variante A ou la question peut viser une situation generale.\\n"
            "\n"
            "\n"
            "--- TITRE (regle de performance n1 : le titre decide de la distribution) ---\n"
            "Le titre est en francais, fait 40 a 70 caracteres, et cree une TENSION, pas un sujet.\n"
            "DONNEES REELLES DE LA CHAINE (mesurees le 27/09/2026) : les titres qui adressent le spectateur et annoncent un enjeu concret ont fait 128 a 147 vues ; les titres nominaux abstraits (L erreur de..., La science de..., Le test de...) ont fait 0 a 5 vues.\n"
            "OBLIGATOIRE : au moins UN des trois - adresse directe (vous, votre, vos) ; question (Pourquoi, Comment, Combien) ; chiffre concret (montant, pourcentage, duree, annee).\n"
            "INTERDIT : commencer par une nominalisation abstraite (L erreur de, La science de, Le piege de, Le test de, L illusion de, Le paradoxe de, La methode des, L art de, Le secret de, La psychologie de).\n"
            "INTERDIT : un titre purement thematique ou descriptif du contenu. Le titre doit promettre une consequence personnelle ou ouvrir une curiosite, pas annoncer un theme.\n"
            "INTERDIT : reprendre mot pour mot une formulation deja utilisee par la chaine.\n"
            "--- FORMAT 2 VOIX ---\n"
            "- Voix A (expert, didactique) : explications, données, science\n"
            "- Voix B (contrepoint, provocateur) : questions, défis, punchlines\n"
            "Structure :\n"
            "- Segment 1 [voix B] : constat sec puis bascule sur le spectateur (conforme a la variante du jour : A = question directe, B = constat puis bascule)\n"
            "- Segment 2 [voix A] : déconstruction scientifique, données, biais\n"
            "- Segment 3 [voix A] : le système, la solution, la stratégie\n"
            "- Segment 4 [voix B] : punchline qui boucle avec le hook\n\n"
            "Au moins une donnée chiffrée vérifiable dans l’ensemble des segments 1 à 3 ; les autres segments peuvent rester sans chiffre "
            "(pourcentage, euro, année, statistique). IMPORTANT : écris les nombres en CHIFFRES "
            "pas en lettres (30% pas trente pourcent, 100€ pas cent euros, 2023 pas deux mille vingt-trois). "
            f"ZÉRO guru-speak. Termes interdits : {', '.join(GURU_BLACKLIST)}.\n\n"
            "Au moins un des segments 1 à 3 doit fournir stat_value et stat_label. Pour tout segment sans chiffre fiable, utilise des chaînes vides. stat_value doit être un chiffre présent dans le texte, factuel et vérifiable. N’invente jamais de statistique ; privilégie une année, une durée, un montant ou une règle mathématique certaine.\n"
            "Chaque stat_value issue des DONNÉES RÉELLES doit reprendre EXACTEMENT la valeur du bloc ci-dessus, et stat_label doit nommer la source (ex : 'Eurostat', 'BCE', 'base ETF PEA').\n"
            "DONNÉES AUTORISÉES : uniquement un calcul mathématique exact ou un exemple explicitement présenté comme hypothétique. Interdit de citer une étude non identifiée, une statistique comportementale, une moyenne vague, un pourcentage universel ou une affirmation du type la science montre. Toute recommandation chiffrée doit être présentée comme un exemple et non comme une règle générale.\n"
            "CHIFFRES INTERDITS (jamais, même dans le HOOK) : pourcentage comportemental ('90% des investisseurs...'), statistique d'étude non citée, moyenne vague, 'la science montre', 'les études prouvent', 'toujours', 'jamais', 'garanti'. Aucun n'est vérifiable.\n"
            "CHIFFRES AUTORISÉS (à privilégier) : année calendaire officielle, durée ('en 10 ans', 'chaque mois'), montant présenté comme exemple hypothétique ('si vous investissez 200€ par mois'), calcul arithmétique exact ('1% de frais par an'). Le chiffre doit apparaître tel quel dans le texte du segment.\n"
            + (MARKET_DATA_BLOCK + "\n\n" if MARKET_DATA_BLOCK else "")
            + ("PRIORITÉ : si une donnée réelle ci-dessus correspond au sujet du jour, UTILISE-LA dans le segment 2 ou 3. "
               "Un chiffre sourcé et daté est ce qui rend la vidéo crédible : c'est ta meilleure arme.\n"
               if MARKET_DATA_BLOCK else "")
            + "Si aucun chiffre autorisé ne s'applique naturellement au sujet, laisse stat_value et stat_label vides : un segment sans chiffre vaut mieux qu'un chiffre inventé.\n"
            "INTERDIT aussi : les affirmations déterministes présentées comme une loi biologique ou mécanique ('ce mécanisme force la vente au plus bas', 'votre cerveau vous pousse à détruire votre capital'). Utilise des formulations prudentes : peut, souvent, a tendance à.\n"
            "En plus du script, ajoute un champ 'scenes' avec une description visuelle "
            "pour chaque segment, style esthétique et cinématographique :\n"
            "- Scene 1 : ambiance liée au hook\n"
            "- Scene 2 : data / science / abstrait\n"
            "- Scene 3 : solution / architecture / système\n"
            "- Scene 4 : conclusion / espace ouvert\n\n"
            f"{LEARNING_INJECTION}"
            "JSON UNIQUEMENT : {\"title\":\"...\",\"description\":\"...\","
            "\"segments\":[{\"text\":\"...\",\"voice\":\"A\",\"duration\":16,\"scene\":\"...\","
            "\"stat_value\":\"...\",\"stat_label\":\"...\"}],"
            "\"scenes\":[\"...\",\"...\",\"...\",\"...\"]}"
        )

        raw_script, model_used = ask_llm(prompt, max_tokens=4000)

        # Load recent titles for duplicate check
        history_path = PIPELINE_DIR / "PROMPT_HISTORY.json"
        recent_titles_list = []
        if history_path.exists():
            hist = json.load(open(history_path))
            recent_titles_list = [h.get("title", "") for h in hist[-10:]]

        # Validation avec retry (inclut titre dupliqué)
        max_attempts = 5
        retry_hints = [
            "Conserve exactement 4 segments. Au moins une donnée chiffrée fiable doit apparaître dans les segments 1 à 3, avec stat_value identique à la valeur présente dans le texte et stat_label explicite. Laisse ces champs vides dans les autres segments.",
            "N invente aucune statistique. Utilise uniquement un calcul mathematique exact ou un exemple explicitement hypothetique. Respecte 16 a 24 mots pour le segment 1 (accroche) et 46 a 55 mots pour les segments 2 a 4, total 154 a 189 mots."
        ]
        for attempt in range(max_attempts):
            (work_dir / f"stage1_attempt_{attempt + 1}.txt").write_text(raw_script, encoding="utf-8")
            try:
                script_data = json.loads(raw_script)
                text = " ".join(s["text"] for s in script_data["segments"])
                guru_score = calculate_guru_score(text)
                lang_ok = not contains_forbidden_words(text)
                has_data = any(bool(re.search(r"\d+", s["text"])) for s in script_data["segments"][:3])
                has_stat_cards = any(re.search(r"\d", str(s.get("stat_value", ""))) and str(s.get("stat_label", "")).strip() and str(s.get("stat_value", "")).strip() in s.get("text", "") for s in script_data["segments"][:3])
                word_counts = [len(re.findall(r"\b[\wÀ-ÿ'’-]+\b", s["text"])) for s in script_data["segments"]]
                word_count_ok = word_counts_ok(word_counts)

                # Title duplicate check
                title = script_data["title"]
                title_issues = title_quality_issues(title)
                title_fresh = True
                for old_t in recent_titles_list:
                    ratio = difflib.SequenceMatcher(None, title.lower(), old_t.lower()).ratio()
                    if ratio > 0.90:
                        title_fresh = False
                        print(f"[VALIDATION] Titre '{title}' trop proche de '{old_t}' ({ratio:.0%})")
                        break
            except (json.JSONDecodeError, KeyError):
                if attempt < max_attempts - 1:
                    raw_script, model_used = ask_llm(
                        prompt + f"\n\n{retry_hints[min(attempt, len(retry_hints)-1)]}",
                        MODEL_FALLBACK, max_tokens=4000
                    )
                    continue
                raise

            violations = []
            hook_issues = hook_structure_issues(script_data["segments"], hook_variant)
            if hook_issues:
                print(f"[HOOK] structure accroche: {hook_issues}")
            if attempt < 2:
                violations.extend(hook_issues)
            if attempt < 2:
                violations.extend(title_issues)
            if not lang_ok:
                violations.append("mots anglais/espagnol interdits")
            if guru_score > 0:
                violations.append(f"guru-speak (score={guru_score})")
            if not has_stat_cards:
                violations.append("stat_value ou stat_label manquant dans un segment")
            if not word_count_ok:
                violations.append(f"nombre de mots invalide par segment: {word_counts} (attendu: segment 1 = 16-24, segments 2-4 = 46-55, total 154-189)")
            if not has_data:
                violations.append("data chiffrée obligatoire manquante")
            if not title_fresh:
                violations.append("titre trop similaire à une vidéo existante")

            if not violations:
                print(f"[VALIDATION] OK — attempt {attempt+1}/{max_attempts}")
                record_ab_assignment(hook_variant, script_data.get("title", ""), word_counts)
                break

            if attempt < max_attempts - 1:
                hints = " ; ".join(violations)
                hint = retry_hints[min(attempt, len(retry_hints)-1)] + "\nREGLE BLOQUANTE : segment 1 = 16 a 24 mots (2 phrases conseillees, 3 maximum) : une premiere phrase de 14 mots maximum conforme a la variante imposee (A = question directe, B = constat sec puis bascule sur vous). Segments 2 a 4 = 46 a 55 mots, total 154 a 189 mots. Recompte avant de repondre. TITRE : 40 a 70 caracteres, avec adresse au spectateur (vous/votre/vos) OU une question OU un chiffre ; interdit de commencer par L erreur de / La science de / Le piege de / Le test de / L illusion de."
                print(f"[RETRY {attempt+1}/{max_attempts}] {hints}")
                # Ajouter une instruction anti-duplication si titre problématique
                dup_hint = ""
                if not title_fresh:
                    dup_hint = "\nIMPORTANT : le titre choisi est déjà trop proche d'une vidéo existante. Trouve un angle COMPLÈTEMENT DIFFÉRENT et un titre original."
                raw_script, model_used = ask_llm(
                    prompt + f"\n\n{hint}{dup_hint}", model_used, max_tokens=4000
                )
            else:
                raise Exception(
                    f"Script rejeté après {max_attempts} tentatives : {'; '.join(violations)}"
                )

        segments = script_data["segments"]

        # Retry LLM si nombre de segments trop bas
        if len(segments) < 3:
            print(f"[RETRY] Seulement {len(segments)} segments — nouveau prompt LLM")
            raw_script, model_used = ask_llm(
                prompt + "\n\nURGENT : Le script doit contenir EXACTEMENT 4 segments. "
                         "Tu n'en as fourni que trop peu. Assure-toi d'avoir 4 segments complets.",
                MODEL_FALLBACK
            )
            script_data = json.loads(raw_script)
            segments = script_data["segments"]

        # Scène descriptions
        scenes_descriptions = script_data.get("scenes", [s.get("scene", "") for s in segments])

        # Description riche (format Eric approuvé)
        hook = segments[0]['text'][:100] + "..."
        seg_bullets = "\n".join(f"• {s['text'][:80]}..." for s in segments)
        description = RICH_DESC_TEMPLATE.format(
            hook=hook,
            bullets=seg_bullets,
            hashtags=DEFAULT_HASHTAGS
        )

        while len(segments) < 4:
            segments.append({"text": "...", "duration": 10, "voice": "A", "scene": ""})
        while len(scenes_descriptions) < 4:
            scenes_descriptions.append("")
        segments = segments[:4]
        scenes_descriptions = scenes_descriptions[:4]

        send_telegram(
            f"🚀 Pipeline v2 lancé\n"
            f"Sujet : {title}\n"
            f"Guru : {guru_score} | LLM : {model_used}\n"
            f"Mode : {'PREVIEW' if PREVIEW_MODE else 'Upload'}"
        )


        # STAGE 1b : DATA VALIDATION (fact-check)
        # ────────────────────────────────────────────────────
        print("\n" + "=" * 50)
        print("  STAGE 1b : DATA VALIDATION — fact-check")
        print("=" * 50)
        max_factcheck_attempts = 3

        for factcheck_attempt in range(max_factcheck_attempts):
            (work_dir / f"factcheck_{factcheck_attempt + 1}_input.json").write_text(json.dumps(script_data, indent=2, ensure_ascii=False), encoding="utf-8")
            is_data_valid, data_issues = validate_script_data(
                segments,
                model="deepseek/deepseek-v4-pro",
                reference_block=MARKET_DATA_BLOCK
            )

            (work_dir / f"factcheck_{factcheck_attempt + 1}_result.json").write_text(json.dumps({"valid": is_data_valid, "issues": data_issues}, indent=2, ensure_ascii=False), encoding="utf-8")
            if is_data_valid and not data_issues:
                print(
                    f"[DATA-VALIDATION] ✅ Validé par DeepSeek V4 Pro "
                    f"— tentative {factcheck_attempt + 1}/{max_factcheck_attempts}"
                )
                send_telegram("✅ Script validé par DeepSeek V4 Pro")
                break

            print(f"[DATA-VALIDATION] ⚠️ {len(data_issues)} problème(s) détecté(s):")
            for iss in data_issues[:5]:
                print(
                    f"  - Segment {iss.get('segment', '?')}: "
                    f"{iss.get('claim', '')[:60]} — "
                    f"{iss.get('reason', '')[:80]}"
                )

            if factcheck_attempt >= max_factcheck_attempts - 1:
                raise RuntimeError(
                    f"Fact-check refusé après {max_factcheck_attempts} tentatives : "
                    f"{len(data_issues)} problème(s) persistent"
                )

            correction_prompt = (
                "Tu dois corriger ce script après le contrôle de DeepSeek V4 Pro.\n"
                "Corrige uniquement les affirmations signalées.\n"
                "Utilise la suggestion fournie. Si une statistique est invérifiable, retire-la sans inventer de valeur de remplacement.\n"
                "N'invente aucune statistique précise sans source fiable.\n"
                "Dans les segments signales uniquement, remplace les tournures categoriques (jamais, toujours, seul, unique, garanti, vous devez, il faut absolument) par des formulations prudentes (peut, souvent, en general, vous pouvez). Ne touche pas aux segments non signales.\n"
                "Si une donnée chiffrée est signalée comme non sourcée ou invérifiable, supprime entièrement ce chiffre du texte et laisse stat_value et stat_label vides pour ce segment. Ne le remplace jamais par une estimation, une moyenne vague ou un autre pourcentage.\n"
                "Conserve exactement 4 segments : le segment 1 (accroche) doit rester entre 16 et 24 mots, les segments 2 a 4 entre 46 et 55 mots, total 154 a 189 mots. Ne rallonge JAMAIS le segment 1 et ne depasse jamais 55 mots sur les autres. Corrige uniquement les affirmations signalees sans reecrire les autres segments.\n"
                "Conserve le titre, les voix, les scènes et la structure JSON.\n"
                "Réponds uniquement avec le JSON complet corrigé.\n\n"
                f"PROBLÈMES DÉTECTÉS :\n{json.dumps(data_issues, ensure_ascii=False)}\n\n"
                f"SCRIPT À CORRIGER :\n{json.dumps(script_data, ensure_ascii=False)}"
            )

            print(
                f"[DATA-VALIDATION] 🔄 Correction automatique "
                f"{factcheck_attempt + 1}/{max_factcheck_attempts - 1}"
            )

            try:
                corrected_raw, correction_model = ask_llm(
                    correction_prompt,
                    model="deepseek/deepseek-v4.1-flash",
                    max_tokens=9000, temperature=0.1
                )
                from json_repair import repair_json; corrected_data = json.loads(repair_json(corrected_raw))
                corrected_segments = corrected_data.get("segments", [])
                for seg in corrected_segments[:3]:
                    text = seg.get("text", "")
                    stat_value = str(seg.get("stat_value", "")).strip()
                    if stat_value and stat_value not in text:
                        seg["stat_value"] = ""
                        seg["stat_label"] = ""
                    numbers = re.findall(r"\d+(?:[.,]\d+)?(?:\s*%|\s*€)?", text)
                    if numbers and not str(seg.get("stat_value", "")).strip():
                        seg["stat_value"] = numbers[0].strip()
                    if numbers and not str(seg.get("stat_label", "")).strip():
                        seg["stat_label"] = "Valeur présentée"
                if len(corrected_segments) != 4:
                    raise ValueError("Correction LLM incomplète: nombre de segments invalide")


                for i, seg in enumerate(corrected_segments):
                    for field in ("voice", "scene", "hook_sentence", "virality_reason"):
                        if not seg.get(field) and i < len(segments):
                            seg[field] = segments[i].get(field, "")
                corrected_data["segments"] = corrected_segments
                script_data = corrected_data
                segments = corrected_segments
                scenes_descriptions = script_data.get(
                    "scenes",
                    [s.get("scene", "") for s in segments]
                )

                print(f"[DATA-VALIDATION] Script corrigé par {correction_model}")

            except Exception as correction_error:
                print(f"[DATA-VALIDATION] Erreur correction: {correction_error}")
                print(f"[DATA-VALIDATION] → Conservation de l'original")
                try:
                    from json_repair import repair_json
                    raw2, m2 = ask_llm(correction_prompt, model="deepseek/deepseek-v4.1-flash", max_tokens=9000)
                    d2 = json.loads(repair_json(raw2))
                    seg2 = d2.get("segments", [])
                    if len(seg2) == 4 and any(re.search(r"\d", str(s.get("stat_value", ""))) and str(s.get("stat_value", "")).strip() in s.get("text", "") for s in seg2[:3]):
                        script_data = d2
                        segments = seg2
                        print(f"[DATA-VALIDATION] Correction récupérée via {m2}")
                except Exception as fallback_error:
                    print(f"[DATA-VALIDATION] Fallback Flash échoué: {fallback_error}")

        # Revalidation structurelle après le fact-check

        # ════════════════════════════════════════════
        # STAGE 2 : ASSETS (clips vidéo + overlays)
        # ════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("  STAGE 2 : ASSETS VISUELS")
        print("=" * 50)

        # Toujours sélectionner des clips vidéo de la réserve
        clip_db = build_clip_database(use_cache=not args.no_cache)
        selected_clips, clip_source = smart_select_clips(clip_db, n=len(segments))
        print(f"[ASSETS] Clips sélectionnés ({clip_source}):")
        for c in selected_clips:
            print(f"  - {c.name}")

        # Placeholder images pour overlay_plan (via Pillow)
        placeholder_images = []
        try:
            from PIL import Image as PILImage
            for i in range(len(segments)):
                ph = work_dir / f"ph_{i+1:02d}.png"
                PILImage.new("RGBA", (t_width, t_height), (5, 8, 20, 255)).save(str(ph))
                placeholder_images.append(ph)
        except ImportError:
            # Fallback ffmpeg
            for i in range(len(segments)):
                ph = work_dir / f"ph_{i+1:02d}.png"
                subprocess.run([
                    "ffmpeg", "-f", "lavfi", "-i",
                    f"color=c=0x050814:s={t_width}x{t_height}:d=1",
                    "-update", "1", str(ph),
                    "-y", "-loglevel", "error"
                ], check=True)
                placeholder_images.append(ph)

        # Cartes titre et finale — dimensions de la composition
        title_card = work_dir / "title_card.png"
        if not create_title_card(
            title,
            title_card,
            width=t_width,
            height=t_height,
            subtitle="NEURO-FINANCE"
        ):
            raise RuntimeError("Échec de création de la carte titre")

        end_card = work_dir / "end_card.png"
        if not create_end_card(
            end_card,
            width=t_width,
            height=t_height
        ):
            raise RuntimeError("Échec de création de la carte finale")

        # Thumbnail YouTube
        thumbnail_path = work_dir / "thumbnail.png"
        create_youtube_thumbnail(title, thumbnail_path)

        # Overlay plan (stat cards, comparaisons) — utilise des placeholders
        # car les images de fond ne sont pas statiques
        overlay_plan = create_overlay_sequence(script_data, placeholder_images, work_dir)

        print(f"[ASSETS] Clips: {len(selected_clips)} vidéos ({clip_source})")
        print(f"[ASSETS] Titre: {title_card.name} | End: {end_card.name}")
        print(f"[ASSETS] Overlays: {sum(len(s['overlays']) for s in overlay_plan['segments'])}")

        # ════════════════════════════════════════════
        # STAGE 3 : VOICEOVER
        # ════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("  STAGE 3 : VOICEOVER")
        print("=" * 50)

        seg_audio_paths = []
        seg_durations = []

        for i, seg in enumerate(segments):
            wav_path = work_dir / f"vo{i+1}.wav"
            voice_label = seg.get("voice", "A")
            voice_label = voice_label if voice_label in ("A", "B") else ("B" if i in (0, 3) else "A")
            if await generate_voiceover_segment(seg["text"], wav_path, i + 1, voice_label):
                dur = get_audio_duration(wav_path)
                seg_audio_paths.append(wav_path)
                seg_durations.append(dur)
                print(f"  VO {i+1}: {dur:.1f}s | voix {voice_label}")
            else:
                # Silence fallback
                subprocess.run([
                    "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "10", str(wav_path), "-y", "-loglevel", "error"
                ], check=True)
                seg_audio_paths.append(wav_path)
                seg_durations.append(10.0)
                print(f"  VO {i+1}: SILENCE (fallback)")

        # Normalisation audio -14dB LUFS (standard broadcast)
        for i, wav_path in enumerate(seg_audio_paths):
            norm_path = work_dir / f"vo{i+1}_norm.wav"
            try:
                subprocess.run([
                    "ffmpeg", "-i", str(wav_path),
                    "-af", "loudnorm=I=-14:LRA=1:TP=-1",
                    str(norm_path), "-y", "-loglevel", "error"
                ], check=True, timeout=60)
                shutil.move(str(norm_path), str(wav_path))
                print(f"  [LUFS] Segment {i+1}: normalisé à -14dB")
            except Exception as lufs_e:
                norm_path.unlink(missing_ok=True)
                print(f"  [LUFS] Segment {i+1}: normalisation ignorée ({lufs_e})")

        # Padding des segments trop courts
        for i in range(len(seg_audio_paths)):
            dur = seg_durations[i]
            if dur < PAD_MIN_SEGMENT_S:
                padded = work_dir / f"vo{i+1}_padded.wav"
                target = max(dur, PAD_MIN_SEGMENT_S)
                print(f"  [PADDING] Segment {i+1}: {dur:.1f}s < {PAD_MIN_SEGMENT_S}s -> complete a {target:.1f}s")
                subprocess.run([
                    "ffmpeg", "-i", str(seg_audio_paths[i]),
                    "-af", f"apad=pad_dur={target - dur}",
                    "-t", str(target),
                    str(padded), "-y", "-loglevel", "error"
                ], check=True)
                shutil.move(str(padded), str(seg_audio_paths[i]))
                seg_durations[i] = target

        # Silence cutter pré-composition (sur chaque fichier audio individuel)
        try:
            from pipeline.tools.silence_cutter import cut_silence
            for i, wav_path in enumerate(seg_audio_paths):
                cut_path = work_dir / f"vo{i+1}_cut.wav"
                if cut_silence(str(wav_path), str(cut_path),
                               threshold="-50dB", min_duration=(0.15 if trim_silence_aggressive else 0.3),
                               keep_first=(0.15 if trim_silence_aggressive else 0.3), keep_last=(0.15 if trim_silence_aggressive else 0.3)):
                    new_dur = get_audio_duration(str(cut_path))
                    if new_dur > 3.0:
                        removed = seg_durations[i] - new_dur
                        shutil.move(str(cut_path), str(wav_path))
                        seg_durations[i] = new_dur
                        if removed > 0.1:
                            print(f"[SILENCE CUT] Segment {i+1}: {removed:.1f}s supprimé → {new_dur:.1f}s")
                    else:
                        cut_path.unlink(missing_ok=True)
                else:
                    cut_path.unlink(missing_ok=True)
        except ImportError as sc_e:
            print(f"[SILENCE CUT] silence_cutter non disponible: {sc_e}")
        except Exception as sc_e:
            print(f"[SILENCE CUT] Erreur: {sc_e}")

        # ════════════════════════════════════════════
        # STAGE 4 : WORD TIMINGS (Whisper)
        # ════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("  STAGE 4 : WORD TIMINGS")
        print("=" * 50)

        # On récupère la durée du titre pour décaler les sous-titres (Titre = 3s par défaut)
        # Sans cela, les sous-titres commencent à 0s alors que la voix commence après le titre.
        TITLE_OFFSET = title_duration

        # On force Whisper à analyser les fichiers audio RÉELS pour une synchro parfaite
        # Whisper avec retry (3 tentatives)
        word_timings = None
        for wi in range(3):
            try:
                word_timings = get_word_timings(
                    [str(p) for p in seg_audio_paths],
                    [s["text"] for s in segments],
                )
                if word_timings is not None:
                    break
            except Exception as wh_e:
                print(f"[WHISPER] Tentative {wi+1} échouée: {wh_e}")
                word_timings = None

        if word_timings is None:
            print("[CRITICAL] Whisper a échoué. Les sous-titres seront approximatifs.")
            send_telegram("⚠️ Warning: Synchro sous-titres approximative (Whisper failure)")
        else:
            report_lines = []
            print(f"[SYNC] Synchro mot-par-mot réussie via Whisper")

        # Timings pour segments avec transitions
        fadelen = transition_duration
        seg_times = []
        for i in range(len(segments)):
            # On ajoute TITLE_OFFSET pour aligner le texte sur la narration (après le titre)
            seg_start = TITLE_OFFSET + sum(seg_durations[:i]) - (i + 1) * fadelen
            txt_start = seg_start
            txt_end = seg_start + seg_durations[i]
            seg_times.append((txt_start, txt_end))

        if word_timings:
            word_timings = [[(w["word"], w["local_start"], w["local_end"]) for w in word_timings if w.get("segment_index") == i] for i in range(len(segments))]
        # ASS captions
        ass_path = work_dir / "captions.ass"
        _cap_cfg = _pipeline_config.get("captions", {}) or {}
        ass_content = make_ass_captions(
            segments, seg_times,
            word_timings=word_timings,
            font_name=_cap_cfg.get("font", "Montserrat"),
            font_size=int(_cap_cfg.get("font_size", 84)),
            margin_v=int(_cap_cfg.get("margin_v", 50)),
        )
        ass_path.write_text(ass_content, encoding="utf-8")
        whisper_tag = "[WHISPER]" if word_timings else "[APPROX]"
        print(f"{whisper_tag} ASS: {len(ass_content)} chars, {len(segments)} segments")

        # ════════════════════════════════════════════
        # STAGE 5 : COMPOSE (Ken Burns + overlays + transitions + ASS)
        # ════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("  STAGE 5 : COMPOSITION")
        print("=" * 50)

        # Dimensions depuis la config centrale (chargée en début de main)
        print(f"[COMPOSE] Target Resolution: {t_width}x{t_height} ({'SHORTS' if _shorts_mode else 'NORMAL'})")

        output_filename = f"PROD_{datetime.now().strftime('%Y%m%d_%H%M')}_{re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:50]}.mp4"
        output_path = str(output_dir / output_filename)

        transition_count = len(segments) + 1
        transition_overlap = transition_count * transition_duration
        required_end_duration = (
            60.5 - title_duration - sum(seg_durations) + transition_overlap
        )
        dynamic_end_duration = min(5.0, max(3.0, required_end_duration))
        projected_duration = (
            title_duration
            + sum(seg_durations)
            + dynamic_end_duration
            - transition_overlap
        )
        if projected_duration < 60.0:
            raise RuntimeError(f"Durée insuffisante avant composition: {projected_duration:.1f}s. Narration trop courte; minimum requis: 60s.")
        final_path = compose_final_video(
            voiceover_paths=[str(p) for p in seg_audio_paths],
            work_dir=work_dir,
            output_path=output_path,
            clip_paths=[str(p) for p in selected_clips],
            overlay_plan=overlay_plan,
            title_card=str(title_card) if title_card.exists() else None,
            end_card=str(end_card) if end_card.exists() else None,
            ass_path=str(ass_path) if ass_path.exists() else None,
            width=t_width,
            end_duration=dynamic_end_duration,
            title_duration=title_duration,
            transition_duration=transition_duration,
            fps=target_fps,
            height=t_height
        )

        # ── SILENCE CUT — déjà fait par audio individuel (silence_cutter.py) ──
        final_duration = get_audio_duration(final_path)
        final_size = os.path.getsize(final_path) / (1024 * 1024)
        print(f"[COMPOSE] Final: {final_duration:.1f}s | {final_size:.1f}MB")

        # ── THUMBNAIL ──
        thumb_path = work_dir / "thumbnail.png"
        try:
            create_youtube_thumbnail(title, thumb_path, channel_name="Alfred AI")
            if thumb_path.exists():
                print(f"[THUMB] Miniature créée: {thumb_path.name} ({thumb_path.stat().st_size // 1024} Ko)")
            else:
                thumb_path = None
        except Exception as e:
            print(f"[THUMB] Échec: {e}")
            thumb_path = None

        # Sauvegarder le script pour analyse future
        script_archive_path = output_dir / f"script-{Path(output_filename).stem}.json"
        with open(script_archive_path, "w") as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)

        # ════════════════════════════════════════════
        # STAGE 5b : QA VIDEO (quality gate — inspiré OpenMontage)
        # ════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("  STAGE 5b : QA VIDEO — quality gate")
        print("=" * 50)
        try:
            from pipeline.video_qa import run_video_qa
            qa_report = run_video_qa(final_path)
            print(f"[QA] Score: {qa_report['score']}/100 — {qa_report['summary']}")
            for c in qa_report.get("checks", []):
                status = "✅" if c.get("passed", False) else "❌"
                detail = c.get("detail", c.get("issues", [""]))
                if isinstance(detail, list):
                    detail = "; ".join(detail)
                print(f"  {status} {c['check']}: {detail}")

            if not qa_report["passed"]:
                msg = f"⚠️ QA Score: {qa_report['score']}/100 — Problèmes: {[c['check'] for c in qa_report['checks'] if not c.get('passed', False)]}"
                send_telegram(msg)
                print(f"[QA] {msg}")
                raise RuntimeError(msg)
        except ImportError:
            print("[QA] Module video_qa non disponible, skip")
            raise RuntimeError("Module video_qa indispensable avant upload")
        except Exception as e:
            print(f"[QA] Erreur: {e}")
            raise

        # ════════════════════════════════════════════
        # STAGE 5c : VALIDATION SHORTS NATIVE (9:16)
        # ════════════════════════════════════════════
        # Valide directement la composition verticale si le mode Shorts est actif
        # (config déjà chargée — cf. _shorts_mode en début de main)
        if _shorts_mode:
            print("\n" + "=" * 50)
            print("  STAGE 5c : VALIDATION SHORTS NATIVE 9:16")
            print("=" * 50)

            if t_width >= t_height:
                raise RuntimeError(
                    f"Format Shorts invalide avant QA: {t_width}x{t_height}"
                )

            print(
                f"[Shorts] Composition déjà verticale "
                f"({t_width}x{t_height}) — aucune conversion nécessaire"
            )

            print("[QA] Contrôle bloquant de la version Shorts native")
            shorts_qa = run_video_qa(final_path)
            print(
                "[QA] Shorts: {}/100 — {}".format(
                    shorts_qa["score"],
                    shorts_qa["summary"]
                )
            )
            if not shorts_qa["passed"]:
                raise RuntimeError(
                    "QA Shorts refusée: {}/100".format(shorts_qa["score"])
                )

            final_duration = get_audio_duration(final_path)
            final_size = os.path.getsize(final_path) / (1024 * 1024)
            print(
                f"[Shorts] ✅ Version native validée: "
                f"{Path(final_path).name} "
                f"({final_duration:.1f}s, {final_size:.1f}MB)"
            )

        # STAGE 6 : ANALYSE VIDEO + APPRENTISSAGE
        # ════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("  STAGE 6 : ANALYSE VIDEO + APPRENTISSAGE")
        print("=" * 50)

        analysis_report = {}
        analysis_msg = ""
        try:
            if analyze is None:
                raise RuntimeError("module analyze_video indisponible (sources supprimées le 19/09) - analyse auto désactivée")
            analysis_report = analyze(
                video_path_str=final_path,
                script_path_str=str(script_archive_path)
            )
            video_name = Path(final_path).stem
            store_analysis(video_name, analysis_report)
            patterns = detect_patterns()
            lessons = generate_lessons()

            scores = analysis_report.get("scores", {})
            improvements = analysis_report.get("improvements", [])[:3]
            imp_lines = "\n".join(f"  🔧 {i['action']} (+{i['impact']}pts)" for i in improvements)

            analysis_msg = (
                f"📊 ANALYSE VIDEO\n"
                f"Score: {scores.get('global', '?')}/100\n"
                f"  Technique: {scores.get('technical', 0)}/30\n"
                f"  Contenu: {scores.get('content', 0)}/30\n"
                f"  Audio: {scores.get('audio', 0)}/20\n"
                f"  Viralité: {scores.get('virality', 0)}/20"
            )
            if imp_lines:
                analysis_msg += f"\n🔝 Améliorations:\n{imp_lines}"
            # R4: Réutilisation des word_timings de Stage 4 (pas de re-transcription Whisper)
            try:
                sys.path.insert(0, str(WORKSPACE_DIR / "scripts"))
                from find_viral_moments import find_moments
                if word_timings is not None:
                    # Format attendu par find_moments : start, end, text
                    wt_segments = [
                        {
                            "start": start,
                            "end": end,
                            "text": segments[i].get("text", "")
                        }
                        for i, (start, end) in enumerate(seg_times)
                        if i < len(segments)
                    ]
                    if wt_segments:
                        import tempfile
                        vt = tempfile.mkdtemp(prefix="viral_")
                        vj = os.path.join(vt, "audio.json")
                        with open(vj, "w") as vf:
                            json.dump({"segments": wt_segments}, vf)
                        moments = find_moments(vj, top_n=3, min_dur=4, max_dur=20)
                        shutil.rmtree(vt, ignore_errors=True)
                        if moments:
                            viral_score = max(m["score"] for m in moments)
                            top_moment = moments[0]["text"][:60]
                            analysis_msg += f"\n🔥 Viral: {viral_score:.0f}/100 — \"{top_moment}...\""
                else:
                    # Fallback: Whisper re-transcription (comportement original)
                    import tempfile
                    vt = tempfile.mkdtemp(prefix="viral_")
                    awav = os.path.join(vt, "audio.wav")
                    subprocess.run(["ffmpeg", "-y", "-i", final_path, "-vn", "-ar", "16000", "-ac", "1", "-f", "wav", awav],
                                 check=True, capture_output=True)
                    subprocess.run([sys.executable, "-m", "whisper", awav,
                         "--model", "base", "--language", "fr",
                         "--output_format", "json", "--word_timestamps", "True",
                         "--output_dir", vt], check=True, capture_output=True)
                    vj = os.path.join(vt, "audio.json")
                    moments = find_moments(vj, top_n=3, min_dur=4, max_dur=20)
                    if moments:
                        viral_score = max(m["score"] for m in moments)
                        top_moment = moments[0]["text"][:60]
                        analysis_msg += f"\n🔥 Viral: {viral_score:.0f}/100 — \"{top_moment}...\""
                    shutil.rmtree(vt, ignore_errors=True)
            except Exception as _viral_exc:
                # Ne jamais avaler l'erreur en silence : cause du "analyse impossible"
                # resté invisible du 20/07 au 29/09/2026 (module find_viral_moments manquant).
                print(f"[VIRAL] analyse impossible: {type(_viral_exc).__name__}: {_viral_exc}")
                traceback.print_exc()
                analysis_msg += "\n🔥 Viral: analyse impossible"

            if patterns.get("trend"):
                analysis_msg += f"\n📈 Tendance: {patterns['trend']}"
            analysis_msg += f"\n📊 Baseline: {patterns.get('avg_global', '?')}/100 sur {patterns.get('total_analyzed', 0)} vidéos"

            print(f"[ANALYSE] {analysis_report.get('summary', '?')}")
            print(f"[LEARNING] {len(lessons)} leçons actives")

        except Exception as e:
            print(f"[ANALYSE] Échec: {e}")
            analysis_msg = f"⚠️ Analyse vidéo non disponible: {e}"

        # ════════════════════════════════════════════
        # STAGE 7 : UPLOAD
        # ════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("  STAGE 7 : UPLOAD")
        print("=" * 50)

        yt_url = None
        if PREVIEW_MODE:
            send_telegram(f"[PREVIEW] Prêt - {final_duration:.0f}s, {final_size:.0f}MB")
            # Envoyer l'analyse même en preview
            if analysis_msg:
                send_telegram(analysis_msg)
            if final_size < 48:
                sec = load_secrets()
                bt, ci = sec.get("TELEGRAM_BOT_TOKEN"), sec.get("TELEGRAM_CHAT_ID")
                if bt and ci:
                    with open(final_path, "rb") as f:
                        requests.post(
                            f"https://api.telegram.org/bot{bt}/sendVideo",
                            data={"chat_id": ci, "caption": f"🎬 {title}"},
                            files={"video": f}, timeout=180
                        )
            else:
                send_telegram(f"Trop lourd pour Telegram ({final_size:.0f}MB)")
        else:
            report_lines = []
            playlist_id = PLAYLIST_ID
            # R2: OAuth check avant upload YouTube
            try:
                from pipeline.oauth_check import check_oauth_valid, save_to_failures
                oauth_status = check_oauth_valid()
                oauth_msg = f"🔐 OAuth: {'✅' if oauth_status['valid'] else '❌'} {oauth_status['message']}"
                report_lines.append(oauth_msg)
                if not oauth_status["valid"]:
                    send_telegram(f"🔐 ALERTE OAUTH: {oauth_status['message']}\n⚠️ Vidéo NON uploadée — sauvegardée dans failures/")
                    save_to_failures(final_path)
                    raise Exception(f"OAuth invalide: {oauth_status['message']}")
            except ImportError as oauth_import_error:
                raise RuntimeError("Module oauth_check indispensable avant upload") from oauth_import_error
            tags_json = json.dumps(DEFAULT_TAGS)
            upload_cmd = [
                "python3", str(UPLOAD_PY),
                final_path, title, description, playlist_id, tags_json,
            ]
            if thumb_path:
                upload_cmd.extend(["--thumbnail", str(thumb_path)])
            result = subprocess.run(
                upload_cmd, capture_output=True, text=True, timeout=120, check=False
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                upload_error = result.stderr.strip() or output or f"code retour {result.returncode}"
                raise RuntimeError(f"Uploader YouTube échoué: {upload_error}")

            if "youtube.com" in output or "youtu.be" in output:
                yt_url = output
                print(f"[YOUTUBE_UPLOAD_OK] {yt_url}")
                # History save (avant archivage)
                video_id = yt_url.split("/")[-1]
                history_path = PIPELINE_DIR / "PROMPT_HISTORY.json"
                history = json.load(open(history_path)) if history_path.exists() else []
                history.append({
                    "video_id": video_id, "niche": "NEURO_FINANCE",
                    "title": title, "timestamp": datetime.now().isoformat(),
                    "score": None, "mode": "PROD", "pipeline_version": "v2"
                })
                with open(history_path, "w") as f:

                    json.dump(history, f, indent=2)
            else:
                err = result.stderr.strip()
                if "uploadLimitExceeded" in err:
                    send_telegram("⚠️ Limite YouTube atteinte : vidéo conservée, idée à reprendre.")
                    raise RuntimeError("Upload YouTube non effectué : limite quotidienne atteinte")
                raise RuntimeError(f"Upload YouTube sans URL valide: {err or output or 'sortie vide'}")

            # Zernio cross-post (AVANT archivage — le fichier doit exister)
            if yt_url:
                secrets = load_secrets()
                if secrets.get("ZERNIO_API_KEY"):
                    os.environ.setdefault("ZERNIO_API_KEY", secrets["ZERNIO_API_KEY"])
                    if not os.path.exists(final_path):
                        send_telegram("⚠️ Zernio : fichier vidéo introuvable - upload ignoré")
                    else:
                        try:
                            zernio_result = zernio_upload_video(
                                video_path=final_path,
                                title=title,
                                description=description,
                                tags=DEFAULT_TAGS,
                                platforms=["tiktok", "linkedin"]
                            )
                            if zernio_result.get("success"):
                                send_telegram(f"✅ Zernio : publié sur {', '.join(zernio_result.get('platforms', []))}")
                            else:
                                err = zernio_result.get('error', 'erreur')
                                if "No such file" in str(err):
                                    send_telegram("⚠️ Zernio : fichier inaccessible pour l'upload")
                                else:
                                    send_telegram(f"⚠️ Zernio : {err}")
                        except Exception as z_err:
                            send_telegram(f"⚠️ Zernio : {z_err}")

            # Telegram - envoi de la video au chat prive
            if yt_url:
                tg_caption = f"[{tag}] {title}\n{yt_url}"
                send_telegram_video(final_path, caption=tg_caption[:1024])

            # Archive (APRÈS Zernio — le fichier existe encore)
            if yt_url:
                archive_path = archive_dir / output_filename
                shutil.move(final_path, str(archive_path))

        # Rapport final Telegram avec analyse
        report_lines = [f"[{tag}] ✅ {title} ({final_duration:.0f}s)"]
        if yt_url:
            report_lines.append(f"📺 {yt_url}")
        # Ajouter l'analyse si disponible
        if analysis_report and analysis_report.get("scores", {}).get("global", 0) > 0:
            ascores = analysis_report["scores"]
            report_lines.append(f"🏆 Score: {ascores['global']}/100 | "
                               f"T{ascores['technical']} C{ascores['content']} "
                               f"A{ascores['audio']} V{ascores['virality']}")
        send_telegram("\n".join(report_lines))

        # Envoyer le détail de l'analyse séparément pour ne pas noyer le message principal
        if not PREVIEW_MODE and analysis_msg and "⚠️" not in analysis_msg[:2]:
            send_telegram(analysis_msg)

        print(f"\n[OK] Pipeline v2 terminé")
        success = True

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[FAIL] {e}")
        send_telegram(f"[{tag}] ❌ {e}")
        raise

    finally:
        # Nettoyer le lock file
        LOCK_FILE.unlink(missing_ok=True)

        if not success:
            fail_dir = WORKSPACE / "failures"
            fail_dir.mkdir(parents=True, exist_ok=True)
            recovery = fail_dir / f"failed_{datetime.now().strftime('%Y%m%d_%H%M')}_{work_dir.name}"
            shutil.move(str(work_dir), str(recovery))
        else:
            report_lines = []
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
