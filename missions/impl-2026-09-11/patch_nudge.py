#!/usr/bin/env python3
# Patch cible : garde anti-doublons (concept Mem0) dans nocturne_nudge.py
from pathlib import Path
P = Path("/home/ubuntu/.openclaw/workspace/scripts/nocturne_nudge.py")
src = P.read_text()

def apply(old, new, label):
    global src
    assert old in src, "ANCRE MANQUANTE: " + label
    src = src.replace(old, new, 1)

# 1) imports
apply("import sys, json, re, os, requests, time, http.client",
      "import sys, json, re, os, requests, time, http.client, sqlite3, hashlib",
      "imports")

# 2) constantes (DRY_RUN via env, pas d'argparse -> moins de regression)
apply('SYNTHESIS_MODEL = "deepseek/deepseek-v4-flash-0731"',
'''SYNTHESIS_MODEL = "deepseek/deepseek-v4-flash-0731"
NOCTURNE_DB = "/home/ubuntu/nocturne_memory/nocturne_data.db"
DEDUP_LOG = WORKSPACE / "state" / "nudge_dedup_history.jsonl"
DRY_RUN = os.environ.get("NUDGE_DRY_RUN") == "1"
DEDUP_THRESHOLD = 0.85''',
      "constantes")

# 3) fonctions garde avant load_secrets
GUARD = '''# ── Garde anti-doublons (concept Mem0) ──────────────────────────────

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

'''
apply("def load_secrets():", GUARD + "def load_secrets():", "guard")

# 4) compteurs dans main()
apply("    facts_created = 0",
      "    facts_created = 0" + chr(10) + "    facts_blocked = 0" + chr(10) + "    seen_batch = []",
      "compteurs")

# 5) boucle avec garde (triple quotes + vrais retours a la ligne)
apply("for fact in facts:",
'''for fact in facts:
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
                continue''',
      "boucle")

# 6) rapport
apply('    print(f"  Faits crees:      {facts_created}")',
'''    print(f"  Faits crees:      {facts_created}")
    print(f"  Faits bloques:    {facts_blocked} (dedup)")''',
      "rapport")

P.write_text(src)
print("PATCH OK — nocturne_nudge.py:", len(src), "octets")
