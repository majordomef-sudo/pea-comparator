#!/usr/bin/env python3
"""Auto-refill de la file idees Neuro-Finance.
Si < 5 idees pending -> genere 15 nouvelles via LLM. Anti-coupure silencieuse.
"""
import json, sys, time, re, os, requests
from pathlib import Path

WS = Path("/home/ubuntu/.openclaw/workspace")
QPATH = WS / "output" / "pipeline_ideas.json"
LOGDIR = Path("/home/ubuntu/output/logs")
LOGDIR.mkdir(parents=True, exist_ok=True)
LF = LOGDIR / ("pipeline_refill_" + time.strftime("%Y%m%d") + ".log")
MIN_PENDING = 5
TOPUP = 15
def log(m):
    l = "[" + time.strftime("%Y-%m-%d %H:%M:%S") + "] " + m
    with open(LF, "a") as f:
        f.write(l + chr(10))
    print(l)

def load_secrets():
    s = {}
    env = Path.home() / ".secrets" / "env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line:
                line = line.replace("export ", "").strip()
                k, v = line.split("=", 1)
                s[k] = v.strip(chr(34)).strip(chr(39))
    return s

def ask_llm(prompt, max_tokens=3000):
    secrets = load_secrets()
    api = secrets.get("OPENROUTER_API_KEY")
    if not api:
        raise RuntimeError("OPENROUTER_API_KEY manquante")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": "Bearer " + api, "Content-Type": "application/json"}
    for m in ["deepseek/deepseek-v4.1-flash", "google/gemma-4-31b-it"]:
        for attempt in range(2):
            try:
                resp = requests.post(url, headers=headers, data=json.dumps({
                    "model": m, "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.9, "max_tokens": max_tokens
                }), timeout=(10, 90))
                if resp.status_code == 429:
                    time.sleep(2 ** attempt + 1); continue
                resp.raise_for_status()
                c = resp.json()["choices"][0]["message"]["content"]
                if c and c.strip():
                    return c, m
            except Exception as e:
                log("LLM " + m + " fail: " + str(e)); time.sleep(2 ** attempt)
    raise RuntimeError("Tous modeles LLM echoues")

def main():
    if not QPATH.exists():
        return 0
    q = json.load(open(QPATH))
    pending = [i for i in q if i.get("status") == "pending"]
    existing = {i.get("title", "").lower() for i in q}
    log("Pending: " + str(len(pending)) + "/" + str(len(q)))
    if len(pending) >= MIN_PENDING:
        log("File suffisante, pas de refill"); return 0
    need = TOPUP
    prompt = (
        "Tu es un content strategist pour chaine YouTube Shorts Neuro-Finance (finance comportementale). Genere exactement " + str(need) +
        " idees de video. Chaque idee = titre accrocheur 4-10 mots, francais, contre-intuitif. "
        "Interdit: titres deja utilises, anglais, promesses gain rapide. "
        "JSON UNIQUEMENT {\"ideas\":[\"titre1\",...]}. Titres deja utilises:\n" +
        json.dumps(sorted(list(existing))[:60], ensure_ascii=False)
    )
    raw, model = ask_llm(prompt)
    mj = re.search(r"\{.*\}", raw, re.DOTALL)
    if not mj:
        raise RuntimeError("Pas de JSON LLM")
    ideas = json.loads(mj.group(0)).get("ideas", [])
    ideas = [i.strip() for i in ideas if i.strip()]
    fresh = [i for i in ideas if i.lower() not in existing][:need]
    new_ids = max((it.get("id", 0) for it in q), default=0) + 1
    for t in fresh:
        q.append({"id": new_ids, "title": t, "status": "pending", "priority": 50,
                  "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        new_ids += 1
    tmp = QPATH.with_suffix(QPATH.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(q, f, indent=2, ensure_ascii=False); f.flush()
    os.replace(tmp, QPATH)
    log("Refill: +" + str(len(fresh)) + " via " + model + " (file=" + str(len(q)) + ")")
    return 0

if __name__ == "__main__":
    sys.exit(main())
