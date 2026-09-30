#!/usr/bin/env python3
"""
memory_dedup.py — Déduplication intelligente de la mémoire Nocturne (style Mem0).
Hash exact + similarité sémantique (embeddings locaux fastembed) avec seuil cosinus.

Usage:
  python3 scripts/memory_dedup.py --dry-run            # rapport sans modification (DEFAUT)
  python3 scripts/memory_dedup.py --apply              # fusionne réellement (avec backup auto)
  python3 scripts/memory_dedup.py --dry-run --min 0.9  # seuil personnalisé
"""
import argparse, hashlib, json, re, sqlite3, unicodedata, shutil
from datetime import datetime, timezone
from pathlib import Path

DB = Path("/home/ubuntu/nocturne_memory/nocturne_data.db")
HISTORY_LOG = Path("/home/ubuntu/.openclaw/workspace/state/memory_dedup_history.jsonl")
BACKUP_DIR = Path("/home/ubuntu/.openclaw/workspace/missions/impl-2026-09-11/backups")

EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_embedder = None


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sha(s: str) -> str:
    return hashlib.sha256(norm(s).encode()).hexdigest()


def get_embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(model_name=EMB_MODEL, cache_dir="/home/ubuntu/.cache/fastembed")
    return _embedder


def embed(texts, batch=64):
    import numpy as np
    model = get_embedder()
    vecs = []
    for i in range(0, len(texts), batch):
        for v in model.embed(texts[i:i + batch]):
            vecs.append(np.asarray(v, dtype=np.float32))
    return np.vstack(vecs) if vecs else np.zeros((0, 384), dtype=np.float32)


def cos_sim(a, b):
    import numpy as np
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return float(np.dot(a, b))


def load_memories(con):
    cur = con.cursor()
    cur.execute("""
        SELECT m.id, m.content, m.deprecated, m.migrated_to, m.created_at,
               s.uri, s.priority, s.namespace
        FROM memories m
        LEFT JOIN search_documents s ON s.memory_id = m.id
        WHERE m.content IS NOT NULL AND TRIM(m.content) != ''
    """)
    mems = []
    for r in cur.fetchall():
        mems.append({
            "id": r[0], "content": r[1], "deprecated": bool(r[2]), "migrated_to": r[3],
            "created_at": str(r[4]) if r[4] else "", "uri": r[5] or "",
            "priority": r[6], "namespace": r[7] or "",
        })
    return mems


def find_duplicates(mems, threshold=0.85):
    texts = [m["content"] for m in mems]
    hashes = [sha(t) for t in texts]
    active = [i for i in range(len(mems)) if not mems[i]["deprecated"]]
    active_set = set(active)
    groups = []

    # 1) Doublons exacts (meme hash normalise)
    by_hash = {}
    for i in active:
        by_hash.setdefault(hashes[i], []).append(i)
    for h, idxs in by_hash.items():
        if len(idxs) > 1:
            idxs_sorted = sorted(idxs, key=lambda i: (-len(texts[i]), i))
            groups.append({"type": "exact", "canonical": idxs_sorted[0], "dups": idxs_sorted[1:], "score": 1.0})

    # 2) Doublons semantiques : matrice de cosine vectorisee (numpy)
    import numpy as np
    vecs = embed([texts[i] for i in active])
    vecs = vecs.astype(np.float32)
    norms = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    sims = norms @ norms.T  # (N,N)

    # Paires au-dessus du seuil (strictement au-dessus de la diagonale)
    iu = np.triu_indices(len(active), k=1)
    cond = sims[iu] >= threshold
    pairs = [(int(iu[0][k]), int(iu[1][k]), float(sims[iu[0][k], iu[1][k]])) for k in range(len(iu[0])) if cond[k]]

    # Union-find pour regrouper en clusters
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    # Exclure les paires exactes deja traitees
    links = []
    for i, j, sim in pairs:
        if hashes[active[i]] == hashes[active[j]]:
            continue
        links.append((active[i], active[j], sim))
        union(active[i], active[j])

    clusters = {}
    for i, j, _ in links:
        clusters.setdefault(find(i), set()).update([i, j])

    for root, members in clusters.items():
        members = [m for m in members if m in active_set]
        if len(members) < 2:
            continue
        ordered = sorted(members, key=lambda i: (-len(texts[i]), i))
        best = max((s for i, j, s in links if ordered[0] in (i, j)), default=threshold)
        groups.append({"type": "semantic", "canonical": ordered[0], "dups": ordered[1:], "score": round(best, 3)})

    # Chaque memoire ne doit apparaitre qu'une fois (canonical ou dup)
    consumed, unique = set(), []
    for g in sorted(groups, key=lambda g: -g["score"]):
        if g["canonical"] in consumed or any(d in consumed for d in g["dups"]):
            continue
        consumed.add(g["canonical"])
        consumed.update(g["dups"])
        unique.append(g)
    return unique



def backup_db():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"nocturne_data_pre_dedup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(DB, dest)
    print(f"[BACKUP] {dest}")


def log_history(entry):
    HISTORY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + chr(10))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true", help="Appliquer les fusions (avec backup auto)")
    ap.add_argument("--min", type=float, default=0.85, help="Seuil cosinus (defaut 0.85)")
    args = ap.parse_args()

    apply = args.apply
    con = sqlite3.connect(str(DB))
    mems = load_memories(con)
    print(f"[DEDUP] {len(mems)} memoires chargees | seuil={args.min} | apply={apply}")

    groups = find_duplicates(mems, threshold=args.min)
    print(f"[DEDUP] {len(groups)} groupe(s) de doublons detecte(s)")

    if apply:
        backup_db()

    total = 0
    for g in groups:
        c = mems[g["canonical"]]
        dups = [mems[d] for d in g["dups"]]
        action = "MERGE" if apply else "A FUSIONNER"
        print()
        print(f"  [{g['type']}] score={g['score']:.3f} {action}")
        print(f"    CANON  #{c['id']} ({len(c['content'])}c): {c['content'][:100]}")
        for d in dups:
            total += 1
            print(f"    DUP    #{d['id']} ({len(d['content'])}c): {d['content'][:100]}")
            if apply:
                cur = con.cursor()
                cur.execute("UPDATE memories SET deprecated=1, migrated_to=? WHERE id=?", (c["id"], d["id"]))
                log_history({"ts": datetime.now(timezone.utc).isoformat(), "event": "dedup_merge",
                             "canonical_id": c["id"], "duplicate_id": d["id"], "score": g["score"],
                             "type": g["type"]})

    if apply:
        con.commit()
        print()
        print(f"[OK] {total} doublon(s) fusionne(s) vers leur canonical. DB sauvegardee avant modif.")
    else:
        print()
        print(f"[DRY-RUN] {total} fusion(s) potentielle(s) — rien modifie. Relancer avec --apply si OK.")
    con.close()


if __name__ == "__main__":
    main()