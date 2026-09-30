#!/usr/bin/env python3
"""
Agent 3-couches pour pipeline Neuro-Finance
Décision → Exécution → Supervision
Inspiré de Toonflow.app (Apache 2.0)
"""
import sys, json, subprocess, time, os
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
sys.path.insert(0, str(WORKSPACE / "scripts"))
from skill_loader import load_skill

ORCHESTRATOR = WORKSPACE / "skills" / "alfred_cron" / "nightly_orchestrator.py"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ── Secrets ─────────────────────────────────────────────────────

def load_secrets():
    env = os.environ.copy()
    secrets_file = Path.home() / ".secrets/env"
    if secrets_file.is_file():
        with open(secrets_file) as f:
            for line in f:
                if '=' in line:
                    line = line.replace('export ', '').strip()
                    if '=' in line:
                        k, v = line.split('=', 1)
                        env[k] = v.strip('"').strip("'")
    return env

secrets = load_secrets()
API_KEY = secrets.get("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))

MODEL = "deepseek/deepseek-v4.1-flash"


def call_llm(prompt: str, system: str = None) -> str:
    """Call LLM via OpenRouter"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    try:
        r = requests.post(OPENROUTER_URL, json={
            "model": MODEL,
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.3
        }, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, timeout=30)
        msg = r.json()['choices'][0]['message']
        return msg.get('content') or msg.get('reasoning', '')
    except Exception as e:
        print(f"  LLM error: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════
# LAYER 1 — DÉCISION
# ═══════════════════════════════════════════════════════════════════

def decide_topic() -> dict:
    """Décide du sujet de la prochaine vidéo"""
    print("\n  [DÉCISION] Choix du sujet...")
    
    # Charger les prompts
    decision_prompt = load_skill("decision").get("content", "")
    
    prompt = f"""Tu es un expert en stratégie de contenu Neuro-Finance.
{decision_prompt}

Choisis un sujet de short finance percutant avec angle psychologie/cerveau.
Réponds UNIQUEMENT par un JSON valide, sans texte avant ni après.
Aucun raisonnement, aucune explication, seulement le JSON."""
    
    result = call_llm(prompt)
    print(f"  Réponse brute: {result[:200]}")
    
    # Extraction JSON robuste
    import re
    json_match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if "topic" in data:
                print(f"  Sujet: {data['topic']}")
                return data
        except:
            pass
    
    # Fallback: extraire du reasoning
    for line in result.split('\n'):
        line = line.strip()
        if 'topic' in line.lower() and '"' in line:
            try:
                data = json.loads('{' + line + '}')
                if "topic" in data:
                    return data
            except:
                pass
    
    # Fallback final
    print("  Fallback: sujet par défaut")
    return {"topic": "Pourquoi ton cerveau te pousse à acheter", "hook": "Tu crois tout maîtriser ?", "angle": "psychologie", "duration_seconds": 30, "confidence": 7}

def execute_pipeline(topic: str) -> dict:
    """Exécute le pipeline existant avec le sujet choisi (--preview = pas d'upload)"""
    print(f"\n  [EXÉCUTION] Lancement du pipeline pour: {topic}")
    
    # Lancer l'orchestrateur en mode preview (sans upload) — l'agent gère l'upload
    cmd = ["python3.14", str(ORCHESTRATOR), "--topic", topic, "--preview"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    
    # Trouver la dernière vidéo générée
    video_path = None
    output_dir = Path.home() / "output"
    if output_dir.exists():
        mp4_files = sorted(output_dir.glob("PROD_*.mp4"), key=os.path.getmtime)
        if mp4_files:
            video_path = str(mp4_files[-1])
    
    print(f"  Vidéo trouvée: {video_path}")
    return {
        "success": result.returncode == 0,
        "output_path": video_path,
        "stdout": result.stdout[-500:],
        "stderr": result.stderr[-500:] if result.stderr else ""
    }


# ═══════════════════════════════════════════════════════════════════
# LAYER 3 — SUPERVISION
# ═══════════════════════════════════════════════════════════════════

def validate_video(video_path: str = None, topic: str = "") -> dict:
    """Valide la qualité de la vidéo avant upload"""
    print(f"\n  [SUPERVISION] Validation qualité...")
    
    # Analyse ffprobe si vidéo dispo
    duration = 0
    has_video = False
    if video_path and os.path.exists(video_path):
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path],
                capture_output=True, text=True, timeout=30
            )
            probe = json.loads(result.stdout)
            has_video = True
            if "format" in probe:
                duration = float(probe["format"].get("duration", 0))
        except:
            pass
    
    # Validation basée sur métriques réelles
    score = 100
    issues = []
    
    # Durée (25-50s)
    if duration < 25:
        issues.append(f"Durée trop courte: {duration:.0f}s (min 25s)")
        score -= 20
    elif duration > 50:
        issues.append(f"Durée trop longue: {duration:.0f}s (max 50s)")
        score -= 10
    else:
        score += 0  # OK
    
    # Fichier existe
    if not has_video:
        issues.append("Fichier vidéo introuvable")
        score -= 30
    
    # Score final
    if score < 60:
        verdict = "FAILED"
        can_upload = False
    elif score < 80:
        verdict = "WARNING"
        can_upload = True
    else:
        verdict = "PASSED"
        can_upload = True
    
    result = {
        "score": max(0, min(100, score)),
        "verdict": verdict,
        "issues": issues,
        "can_upload": can_upload
    }
    
    print(f"  Supervision: {json.dumps(result)}")
    return result


# ═══════════════════════════════════════════════════════════════════
# MAIN — Orchestrateur 3-couches
# ═══════════════════════════════════════════════════════════════════

def main():
    import requests
    global requests
    
    print("=" * 60)
    print("Pipeline Neuro-Finance — Agent 3-couches")
    print(f"{datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    # Layer 1: Décision
    decision = decide_topic()
    topic = decision.get("topic", "finance par défaut")
    print(f"\n✅ Sujet choisi: {topic}")
    
    # Layer 2: Exécution (avec retry)
    max_retries = 3
    video_path = None
    for attempt in range(max_retries):
        execution = execute_pipeline(topic)
        video_path = execution.get("output_path")
        
        if execution["success"] and video_path:
            print(f"✅ Vidéo générée (attempt {attempt+1}): {video_path}")
            break
        
        if video_path and not execution["success"]:
            print(f"  ⚠️  Pipeline non-zero mais vidéo trouvée: {video_path}")
            break
        
        print(f"  🔄 Retry {attempt+1}/{max_retries} — échec, nouveau sujet...")
        # Regenerate topic
        decision = decide_topic()
        topic = decision.get("topic", "finance par défaut")
        print(f"  Nouveau sujet: {topic}")
    else:
        print(f"❌ Pipeline échoué après {max_retries} tentatives")
        sys.exit(1)
    
    print(f"✅ Vidéo générée: {video_path}")
    
    # Layer 3: Supervision
    validation = validate_video(video_path, topic=topic)
    verdict = validation.get("verdict", "WARNING")
    score = validation.get("score", 0)
    issues = validation.get("issues", [])
    can_upload = validation.get("can_upload", True)
    
    print(f"\n📊 SCORE: {score}/100 — {verdict}")
    if issues:
        for issue in issues:
            print(f"  ⚠️  {issue}")
    
    if verdict == "FAILED":
        print("❌ Vidéo rejetée — pas d'upload")
        sys.exit(1)
    
    if verdict == "WARNING":
        print("⚠️  Vidéo acceptée (qualité borderline)")
    
    if can_upload:
        print(f"✅ Upload autorisé — lancement...")
        # Lancer l'upload
        upload_cmd = [
            "python3.14",
            str(WORKSPACE / "skills" / "youtube_upload" / "upload.py"),
            video_path or "",
            "Neuro-Finance #shorts #cerveau"
        ] if video_path else ["echo", "No video to upload"]
        subprocess.run(upload_cmd, timeout=120)
    
    print("\n" + "=" * 60)
    print("Pipeline terminé avec succès")
    print("=" * 60)


if __name__ == "__main__":
    main()