#!/usr/bin/env python3
"""Analyze a video for virality patterns."""
import json, os, sys, subprocess, argparse, re
from pathlib import Path

LLM_MODEL = os.environ.get("VIRAL_LLM_MODEL", "deepseek/deepseek-v4.1-flash")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
NL = chr(10)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout, r.stderr

def get_metadata(url):
    print("[1/5] Fetching metadata...")
    out, _ = run(["yt-dlp", "--dump-json", "--no-download", url])
    if not out.strip():
        return {"error": "No metadata"}
    d = json.loads(out.strip().split(NL)[0])
    return {
        "title": d.get("title"), "channel": d.get("channel"),
        "duration": d.get("duration"), "view_count": d.get("view_count"),
        "like_count": d.get("like_count"), "comment_count": d.get("comment_count"),
        "tags": (d.get("tags") or [])[:10], "description": (d.get("description") or "")[:500],
        "upload_date": d.get("upload_date")
    }

def download_audio(url, odir):
    print("[2/5] Downloading audio...")
    Path(odir).mkdir(parents=True, exist_ok=True)
    out_path = str(Path(odir) / "audio.%(ext)s")
    run(["yt-dlp", "-x", "--audio-format", "mp3", "-o", out_path, url])
    ap = str(Path(odir) / "audio.mp3")
    return ap if os.path.exists(ap) else None

def transcribe(apath):
    print("[3/5] Transcribing with Whisper...")
    try:
        import whisper
        result = whisper.load_model("small").transcribe(apath, language="fr")
        return result["text"]
    except ImportError:
        print("  whisper unavailable, skipping")
        return ""

def get_comments(url, mc=50):
    print("[4/5] Fetching comments...")
    out, _ = run(["yt-dlp", "--dump-json", "--extractor-args",
                   "youtube:comment_sort=top;max_comments=" + str(mc),
                   "--no-download", "--write-comments", url])
    if not out.strip():
        return []
    d = json.loads(out.strip().split(NL)[0])
    return [{"text": (c.get("text") or "")[:200], "likes": c.get("like_count", 0)}
            for c in (d.get("comments") or [])[:mc] if c.get("text")]

def llm_analysis(meta, transcript, comments):
    print("[5/5] LLM analysis...")
    if not OPENROUTER_KEY:
        return "Set OPENROUTER_API_KEY env var and rerun."
    parts = [
        "Analyse cette video YouTube pour la viralite.",
        "",
        "## Metadonnees",
        "Titre: " + str(meta.get("title","N/A")),
        "Chaine: " + str(meta.get("channel","N/A")),
        "Duree: " + str(meta.get("duration","N/A")) + "s",
        "Vues: " + str(meta.get("view_count","N/A")),
        "Likes: " + str(meta.get("like_count","N/A")),
        "Commentaires: " + str(meta.get("comment_count","N/A")),
        "",
        "## Transcription (debut)",
        (transcript or "N/A")[:1500],
        "",
        "## Commentaires top",
    ]
    if comments:
        parts.append(NL.join(["  - " + c["text"][:80] + " (+" + str(c["likes"]) + ")" for c in comments[:8]]))
    else:
        parts.append("N/A")
    parts += [
        "",
        "## Analyse demandee:",
        "1. Hook - comment les 15 premieres secondes accrochent ?",
        "2. Structure - storytelling, educatif, choc, humour ?",
        "3. Data - les chiffres sont-ils bien utilises ?",
        "4. CTA - quel call-to-action ?",
        "5. Titre - promet-il ce que la video livre ?",
        "6. Patterns viraux - quels mecanismes ? (FOMO, choc, utilite, controverse)",
        "7. Ameliorations pour la retention",
        "8. Score viral /10",
        "",
        "Reponds en francais, format concis."
    ]
    prompt = NL.join(parts)
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200
    })
    out, _ = run([
        "curl", "-s", "https://openrouter.ai/api/v1/chat/completions",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer " + OPENROUTER_KEY,
        "-d", payload
    ])
    try:
        return json.loads(out)["choices"][0]["message"]["content"]
    except:
        return "[LLM Error] " + out[:300]

def write_output(odir, meta, transcript, comments, analysis):
    Path(odir).mkdir(parents=True, exist_ok=True)
    files_data = [
        ("metadata.json", json.dumps(meta, indent=2, ensure_ascii=False)),
        ("transcript.txt", transcript or ""),
        ("comments.json", json.dumps(comments, indent=2, ensure_ascii=False)),
        ("report.md", analysis if isinstance(analysis, str) else str(analysis))
    ]
    for fname, data in files_data:
        with open(str(Path(odir) / fname), "w") as f:
            f.write(data)
    print("")
    print("Saved to " + odir + "/: metadata.json, transcript.txt, comments.json, report.md")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--output", "-o")
    args = p.parse_args()
    odir = args.output or "analysis_" + re.sub(r"[^a-zA-Z0-9]", "_", args.url)[:25]
    meta = get_metadata(args.url)
    if "error" in meta:
        print("FAIL: " + meta["error"])
        sys.exit(1)
    audio = download_audio(args.url, odir)
    transcript = transcribe(audio) if audio else ""
    comments = get_comments(args.url)
    analysis = llm_analysis(meta, transcript, comments)
    write_output(odir, meta, transcript, comments, analysis)
    v = meta
    print("")
    print("Stats: " + str(v.get("title","?")))
    print("  Views: " + format(v.get("view_count",0),",d") + " | Likes: " + format(v.get("like_count",0),",d") + " | Duration: " + str(v.get("duration",0)) + "s")

if __name__ == "__main__":
    main()
