import os
import sys
import subprocess
import json
import random
import time
import re
import textwrap
from datetime import datetime
from pathlib import Path
import requests

# --- CONFIGURATION ---
WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
PIPELINE_DIR = WORKSPACE / "skills/alfred_video_pipeline"
CHARTER_PATH = PIPELINE_DIR / "EDITORIAL_CHARTER_NEURO_FINANCE.md"
LEXICON_PATH = PIPELINE_DIR / "SEMANTIC_LEXICON_NEURO_FINANCE.md"
PLAYBOOK_PATH = PIPELINE_DIR / "PLAYBOOK_NEURO_FINANCE.md"
FONT_SELECTOR_PY = PIPELINE_DIR / "font_selector.py"
UPLOAD_PY = WORKSPACE / "skills/youtube_upload/upload.py"

MODEL_CREATIVE = os.environ.get("MODEL_CREATIVE", "google/gemma-4-26b-a4b-it")

def load_secrets():
    secrets = os.environ.copy()
    env_file = Path.home() / ".secrets/env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line:
                    line = line.replace('export ', '').strip()
                    k, v = line.split('=', 1)
                    secrets[k] = v.strip('"').strip("'")
    return secrets

def ask_llm(prompt, model=None):
    if model is None:
        model = MODEL_CREATIVE
    secrets = load_secrets()
    api_key = secrets.get("OPENROUTER_API_KEY")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    models_to_try = [model, "google/gemma-4-26b-a4b-it", "deepseek/deepseek-v4.1-flash"]
    last_error = None
    
    for m in models_to_try:
        try:
            payload = {"model": m, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 429:
                continue
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
            return match.group(1).strip() if match else content.strip()
        except Exception as e:
            last_error = e
            continue
    
    raise Exception(f"Tous les modèles ont échoué: {last_error}")

def fix_video(video_path):
    print(f"Correction de : {video_path.name}")
    title = video_path.stem.replace("_", " ")
    
    # 1. Get 40s script for this title
    charter = CHARTER_PATH.read_text(errors='ignore') if CHARTER_PATH.exists() else ""
    lexicon = LEXICON_PATH.read_text(errors='ignore') if LEXICON_PATH.exists() else ""
    playbook = PLAYBOOK_PATH.read_text(errors='ignore') if PLAYBOOK_PATH.exists() else ""
    
    script_prompt = (
        f"Tu es un expert en Neuro-Finance. \n{charter}\n{lexicon}\n{playbook}\n"
        f"Tâche : Recrée le script pour un Short de 40s basé sur le titre : {title}.\n"
        f"Réponds UNIQUEMENT en JSON : {{ \"title\": \"...\", \"description\": \"...\", \"segments\": [{{ \"text\": \"...\", \"duration\": 10 }} x 4] }}"
    )
    
    script_json = ask_llm(script_prompt, MODEL_CREATIVE)
    script_data = json.loads(script_json)
    segments = script_data['segments'][:4]
    while len(segments) < 4: segments.append(segments[-1])

    # 2. Prepare Text
    font_json_str = subprocess.check_output([str(FONT_SELECTOR_PY)], text=True)
    font_data = json.loads(font_json_str)
    font_bold = font_data['font_path'] # Simplified for fixer

    work_dir = Path(f"/tmp/fix_{int(time.time())}")
    work_dir.mkdir(parents=True, exist_ok=True)
    
    drawtext_filters = []
    for i in range(4):
        text = segments[i]['text']
        lines = textwrap.wrap(text, width=18)
        start_t, end_t = i*10, (i+1)*10
        for j, line in enumerate(lines[:3]):
            txt_path = work_dir / f"s{i}_l{j}.txt"
            with open(txt_path, "w", encoding="utf-8") as f: f.write(line)
            y_pos = "h*0.15" if i < 2 else "h*0.75"
            drawtext_filters.append(
                f"drawtext=textfile='{txt_path}':fontfile='{font_bold}':fontcolor=white@0.95:fontsize=42:x=(w-text_w)/2:y={y_pos}+{j*65}:shadowcolor=black@0.8:shadowx=2:shadowy=2:enable='between(t,{start_t},{end_t})'"
            )

    # 3. FFmpeg: Trim to 40s + Apply Text
    final_mp4 = work_dir / "fixed.mp4"
    filter_str = ", ".join(drawtext_filters)
    
    cmd = [
        "ffmpeg", "-t", "40", "-i", str(video_path),
        "-filter_complex", filter_str,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "copy", 
        str(final_mp4), "-y", "-loglevel", "error"
    ]
    subprocess.run(cmd, check=True)

    # 4. Upload
    playlist_id = "PLdwDhfX2NgAA7iRC7YyACU84j0etkTiWv"
    cmd_upload = [str(UPLOAD_PY), str(final_mp4), script_data['title'], script_data['description'], playlist_id]
    subprocess.run(cmd_upload)
    print(f"✅ {title} corrigé et uploadé.")

if __name__ == "__main__":
    output_dir = Path.home() / "output"
    for vid in output_dir.glob("*.mp4"):
        fix_video(vid)
