#!/usr/bin/env python3
"""
🧠 Alfred Nudge Nocturne — Nudge adapté pour Nocturne Memory
Remplace l'ancien nudge Mem0.
Analyse les daily notes, extrait les faits, les stocke dans Nocturne.
"""

import sys, json, re, os, requests, time, http.client, sqlite3, hashlib
from model_router import log_llm_call
from pathlib import Path
from datetime import datetime, timezone

NOCTURNE_BASE = "http://127.0.0.1:8898"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
MEMORY_DIR = WORKSPACE / "memory"
SYNTHESIS_MODEL = "deepseek/deepseek-v4.1-flash"
NOCTURNE_DB = "/home/ubuntu/nocturne_memory/nocturne_data.db"
DEDUP_LOG = WORKSPACE / "state" / "nudge_dedup_history.jsonl"
DRY_RUN = os.environ.get("NUDGE_DRY_RUN") == "1"
DEDUP_THRESHOLD = 0.85

# ── Session Nocturne ───────────────────────────────────────────

def nocturne_session():
    r = requests.post(f"{NOCTURNE_BASE}/mcp",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"},
        json={"jsonrpc":"2.0","id":"nudge-init","method":"initialize",
              "params":{"protocolVersion":"2024-11-05","capabilities":{},
                        "clientInfo":{"name":"alfred-nudge","version":"2.0"}}},
        timeout=15)
    return r.headers.get("Mcp-Session-Id", "")

def nocturne_create(sesh, content, title=None):
    args = {
        "parent_uri": "core://",
        "content": content,
        "priority": 3,
        "disclosure": "When reviewing recent context or daily notes"
    }
    if title:
        args["title"] = title
    r = requests.post(f"{NOCTURNE_BASE}/mcp",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream",
                 "Mcp-Session-Id": sesh},
        json={"jsonrpc":"2.0","id":f"n-{int(time.time()*1000)}",
              "method":"tools/call",
              "params":{"name":"create_memory","arguments":args}},
        timeout=15)
    for line in r.text.split("\n"):
        if line.startswith("data:"):
            data = json.loads(line[5:])
            if "result" in data:
                return True
    return False

def nocturne_search(sesh, query):
    r = requests.post(f"{NOCTURNE_BASE}/mcp",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream",
                 "Mcp-Session-Id": sesh},
        json={"jsonrpc":"2.0","id":f"s-{int(time.time()*1000)}",
              "method":"tools/call",
              "params":{"name":"search_memory","arguments":{"query":query, "limit":5}}},
        timeout=15)
    for line in r.text.split("\n"):
        if line.startswith("data:"):
            data = json.loads(line[5:])
            if "result" in data:
                txt = data["result"]["content"][0]["text"]
                if "No matching" in txt:
                    return []
                matches = re.findall(r'core://[^\s]+', txt)
                return matches
    return []

# ── LLM Synthèse ────────────────────────────────────────────────

# ── Garde anti-doublons (concept Mem0) ──────────────────────────────

def _nudge_sha(t):
    try:
        from memory_dedup import sha
        return sha(t)
    except Exception:
        return hashlib.sha256((t or "").encode()).hexdigest()

def dedup_guard_db():
    """Contenus actifs restants (lecture seule)."""
    try:
        con = sqlite3.connect(f"file:{NOCTURNE_DB}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("SELECT content FROM memories WHERE deprecated = 0 AND content IS NOT NULL AND TRIM(content) != ''")
        rows = [r[0] for r in cur.fetchall()]
        con.close()
        return rows
    except Exception as e:
        print(f"    [dedup] DB inaccessible: {e}")
        return []

def dedup_check_fact(fact, threshold=DEDUP_THRESHOLD, seen_batch=None):
    """Retourne (is_dup, match, score, methode).
    Ordre : intra-batch (meme run) -> hash exact DB -> Qdrant (fallback cosine local)."""
    try:
        from memory_dedup import sha, embed, cos_sim
    except Exception as e:
        print(f"    [dedup] memory_dedup indisponible: {e}")
        return False, "", 0.0, "unavailable"
    h = _nudge_sha(fact)
    if seen_batch:
        for (prev, ph) in seen_batch:
            if ph == h:
                return True, prev, 1.0, "intra-batch"
    for c in dedup_guard_db():
        if _nudge_sha(c) == h:
            return True, c, 1.0, "hash"
    try:
        from memory_qdrant import dedup_check
        dups = dedup_check(fact, threshold=threshold)
        if dups:
            return True, dups[0]["content"], dups[0]["score"], "qdrant-cosine"
    except Exception as e:
        print(f"    [dedup] Qdrant indisponible ({str(e)[:60]}), fallback cosine local...")
        try:
            import numpy as np
            contents = dedup_guard_db()
            if contents:
                vecs = embed(contents).astype(np.float32)
                n = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
                fv = embed([fact]).astype(np.float32)
                fv = fv / (np.linalg.norm(fv) + 1e-9)
                sims = n @ fv.T
                best = int(np.argmax(sims[:, 0]))
                if float(sims[best, 0]) >= threshold:
                    return True, contents[best], float(sims[best, 0]), "local-cosine"
        except Exception as e2:
            print(f"    [dedup] fallback indisponible: {e2}")
    return False, "", 0.0, ""

def log_dedup(fact, match, score, methode):
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "fact": fact,
             "match": match[:120], "score": round(score, 3), "methode": methode}
    try:
        DEDUP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DEDUP_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + chr(10))
    except Exception as e:
        print(f"    [dedup] journal impossible: {e}")

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
API_KEY = secrets.get("OPENROUTER_API_KEY", "")

def extract_facts(text: str) -> list:
    """Extract key facts from a text using LLM"""
    prompt = f"""Analyse le texte suivant et extrait les faits clés (maximum 5).
Un fait = une information utile et durable (pas des banalités).
Format: un fait par ligne, sans numérotation, en français.

Texte:
{text[:2000]}

Faits:"""
    
    try:
        r = requests.post(OPENROUTER_URL, json={
            "model": SYNTHESIS_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.1
        }, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, timeout=30)
        j = r.json()
        u = j.get("usage", {})
        log_llm_call(SYNTHESIS_MODEL, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        facts = j["choices"][0]["message"]["content"].strip().split("\n")
        return [f.strip().lstrip("0123456789.- ").strip("'\"") for f in facts if f.strip() and len(f.strip()) > 20]
    except:
        return []

# ── Main ────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Nocturne Nudge")
    print(f"{datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # 1. Session Nocturne
    sesh = nocturne_session()
    if not sesh:
        print("ERREUR: Impossible de se connecter à Nocturne")
        sys.exit(1)
    print(f"Connecte: {sesh}")

    # 2. Lire les daily notes récentes
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    files = sorted(MEMORY_DIR.glob("*.md"))
    recent = [f for f in files if f.name.endswith(".md") and f.name != "README.md"][-3:]

    facts_found = 0
    facts_created = 0
    facts_blocked = 0
    seen_batch = []

    for file in recent:
        if not file.exists():
            continue
        text = file.read_text(encoding="utf-8")
        if not text.strip():
            continue

        # Vérifier si déjà traité
        existing = nocturne_search(sesh, file.stem)
        if existing:
            print(f"  {file.name}: deja connu ({len(existing)} entree(s))")
            continue

        # Extraire les faits
        facts = extract_facts(text)
        if not facts:
            print(f"  {file.name}: aucun fait nouveau")
            continue

        facts_found += len(facts)
        print(f"  {file.name}: {len(facts)} fait(s) candidat(s)")

        # Stocker dans Nocturne
        for fact in facts:
            # Garde anti-doublons (Mem0) : bloquer si deja connu
            is_dup, match, score, methode = dedup_check_fact(fact, seen_batch=seen_batch)
            if is_dup:
                facts_blocked += 1
                log_dedup(fact, match, score, methode)
                print(f"    BLOQUE (dedup {methode} {round(score,3)}): {fact[:70]}")
                continue
            if DRY_RUN:
                print(f"    [DRY-RUN] cree: {fact[:70]}")
                seen_batch.append((fact, _nudge_sha(fact)))
                continue
            title = re.sub(r'[^a-zA-Z0-9_-]', '_', fact[:40].lower().strip())
            ok = nocturne_create(sesh, fact, title=title)
            if ok:
                facts_created += 1
            time.sleep(0.15)

    # 3. Rapport
    print("\n" + "=" * 60)
    print("RAPPORT NUDGE")
    print(f"  Fichiers analyses: {len(recent)}")
    print(f"  Faits candidats:  {facts_found}")
    print(f"  Faits crees:      {facts_created}")
    print(f"  Faits bloques:    {facts_blocked} (dedup)")
    print("=" * 60)


if __name__ == "__main__":
    main()