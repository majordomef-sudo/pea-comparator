#!/usr/bin/env python3
"""
memory_qdrant.py — Couche memoire long terme vectorielle (Qdrant + fastembed, 100% local).
Architecture : SQLite/Nocturne (court terme) -> Qdrant (long terme, dense+sparse) -> MEMORY.md (resume).
Recherche : dense (HNSW) + sparse BM25 (vecteurs natifs + modificateur IDF) + hybride (fusion RRF serveur).
Filtres : type (EPISODIC/SEMANTIC/PROCEDURAL) + scope (namespace) + status (ACTIVE/ARCHIVED).
Dedup : hash sha256 dans le payload + verification cosinus >= 0.85 (dedup_check).
TTL : scan par age/type -> status=ARCHIVED (jamais de delete).

Usage :
  python3 scripts/memory_qdrant.py --reindex      # (re)cree la collection + indexe Nocturne
  python3 scripts/memory_qdrant.py --search "q" [--type X] [--scope /core] [--mode dense|bm25|hybrid]
  python3 scripts/memory_qdrant.py --dedup-check "texte"
  python3 scripts/memory_qdrant.py --ttl-scan [--apply]
  python3 scripts/memory_qdrant.py --test          # validations automatiques
"""
import argparse, hashlib, json, re, sqlite3, unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (Distance, PointStruct, VectorParams, PayloadSchemaType,
                                  Filter, FieldCondition, MatchValue,
                                  SparseVector, SparseVectorParams, Modifier,
                                  Prefetch, Fusion, FusionQuery)

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION = "memories"
DENSE_NAME = "dense"
SPARSE_NAME = "text-sparse"
DB = Path("/home/ubuntu/nocturne_memory/nocturne_data.db")
WORK = Path("/home/ubuntu/.openclaw/workspace")
DENSE_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SPARSE_MODEL = "Qdrant/bm25"
_dense = None
_sparse = None


# ---------------- Embeddings locaux (zero cout API) ----------------

def get_dense():
    global _dense
    if _dense is None:
        from fastembed import TextEmbedding
        _dense = TextEmbedding(model_name=DENSE_MODEL, cache_dir="/home/ubuntu/.cache/fastembed")
    return _dense


def get_sparse():
    global _sparse
    if _sparse is None:
        from fastembed import SparseTextEmbedding
        _sparse = SparseTextEmbedding(model_name=SPARSE_MODEL, cache_dir="/home/ubuntu/.cache/fastembed")
    return _sparse


def embed_dense(texts, batch=64):
    model = get_dense()
    vecs = []
    for i in range(0, len(texts), batch):
        for v in model.embed(texts[i:i + batch]):
            vecs.append(np.asarray(v, dtype=np.float32))
    return np.vstack(vecs) if vecs else np.zeros((0, 384), dtype=np.float32)


def embed_sparse(texts, batch=32):
    model = get_sparse()
    out = []
    for i in range(0, len(texts), batch):
        for v in model.embed(texts[i:i + batch]):
            out.append({"indices": [int(x) for x in v.indices], "values": [float(x) for x in v.values]})
    return out


# ---------------- Utilitaires ----------------

def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sha(s):
    return hashlib.sha256(norm(s).encode()).hexdigest()[:24]


def detect_type(uri, content):
    u = (uri or "").lower()
    c = (content or "").lower()
    if any(k in u for k in ("procedural", "lesson", "howto")) or "lecon" in c or "savoir-faire" in c:
        return "PROCEDURAL"
    if any(k in u for k in ("session", "episodic", "log", "event")):
        return "EPISODIC"
    return "SEMANTIC"


def load_active_memories():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cur.execute("""
        SELECT m.id, m.content, m.created_at, s.uri, s.namespace
        FROM memories m LEFT JOIN search_documents s ON s.memory_id = m.id
        WHERE m.deprecated = 0 AND m.content IS NOT NULL AND TRIM(m.content) != ''
    """)
    rows = cur.fetchall()
    con.close()
    out = []
    for r in rows:
        uri = r[3] or ""
        ns = r[4] or ""
        if not ns and "://" in uri:
            ns = uri.split("://", 1)[0]  # ex: core://agent -> core
        out.append({"id": r[0], "content": r[1], "created_at": str(r[2]) if r[2] else "",
                    "uri": uri, "namespace": ns,
                    "type": detect_type(uri, r[1])})
    return out


def get_client():
    return QdrantClient(url=QDRANT_URL, timeout=60)


# ---------------- Collection / indexation ----------------

def recreate_collection(client):
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        COLLECTION,
        vectors_config={DENSE_NAME: VectorParams(size=384, distance=Distance.COSINE)},
        sparse_vectors_config={SPARSE_NAME: SparseVectorParams(modifier=Modifier.IDF)},
    )
    client.create_payload_index(COLLECTION, "content", field_schema=PayloadSchemaType.TEXT)
    client.create_payload_index(COLLECTION, "type", field_schema=PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION, "namespace", field_schema=PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION, "status", field_schema=PayloadSchemaType.KEYWORD)
    print(f"[QDRANT] Collection '{COLLECTION}' (re)creee : dense 384d + sparse BM25 + index payload")


def index_memories():
    client = get_client()
    recreate_collection(client)
    mems = load_active_memories()
    print(f"[QDRANT] Indexation de {len(mems)} memoires actives ...")
    texts = [m["content"] for m in mems]
    dense = embed_dense(texts)
    sparse = embed_sparse(texts)
    points = []
    for i, m in enumerate(mems):
        sv = SparseVector(indices=sparse[i]["indices"], values=sparse[i]["values"])
        points.append(PointStruct(
            id=m["id"],
            vector={DENSE_NAME: dense[i].tolist(), SPARSE_NAME: sv},
            payload={"content": m["content"], "uri": m["uri"], "namespace": m["namespace"],
                     "type": m["type"], "created_at": m["created_at"],
                     "hash": sha(m["content"]), "status": "ACTIVE",
                     "indexed_at": datetime.now(timezone.utc).isoformat()}
        ))
    for i in range(0, len(points), 100):
        client.upsert(COLLECTION, points[i:i + 100], wait=True)
    n = client.count(COLLECTION, exact=True).count
    print(f"[QDRANT] OK : {len(points)} points (dense+sparse) | total = {n}")
    return n


# ---------------- Recherche ----------------

def build_filter(mtype=None, scope=None, status="ACTIVE"):
    must = []
    if mtype:
        must.append(FieldCondition(key="type", match=MatchValue(value=mtype)))
    if scope:
        must.append(FieldCondition(key="namespace", match=MatchValue(value=scope)))
    if status:
        must.append(FieldCondition(key="status", match=MatchValue(value=status)))
    return Filter(must=must) if must else None


def search_dense(client, text, k=5, mtype=None, scope=None):
    vec = embed_dense([text])[0].tolist()
    f = build_filter(mtype, scope)
    r = client.query_points(COLLECTION, query=vec, using=DENSE_NAME, limit=k,
                            query_filter=f, with_payload=True)
    return [(p.id, p.score, p.payload) for p in r.points]


def search_bm25(client, text, k=5, mtype=None, scope=None):
    s = embed_sparse([text])[0]
    sv = SparseVector(indices=s["indices"], values=s["values"])
    f = build_filter(mtype, scope)
    r = client.query_points(COLLECTION, query=sv, using=SPARSE_NAME, limit=k,
                            query_filter=f, with_payload=True)
    return [(p.id, p.score, p.payload) for p in r.points]


def search_hybrid(client, text, k=5, mtype=None, scope=None):
    """Hybride natif : prefetch dense + sparse, fusion RRF cote serveur."""
    dense_vec = embed_dense([text])[0].tolist()
    s = embed_sparse([text])[0]
    sparse_vec = SparseVector(indices=s["indices"], values=s["values"])
    f = build_filter(mtype, scope)
    r = client.query_points(
        COLLECTION,
        prefetch=[
            Prefetch(query=dense_vec, using=DENSE_NAME, limit=k * 3, filter=f),
            Prefetch(query=sparse_vec, using=SPARSE_NAME, limit=k * 3, filter=f),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=k, with_payload=True,
    )
    return [(p.id, p.score, p.payload) for p in r.points]


def dedup_check(text, threshold=0.85, k=5):
    client = get_client()
    vec = embed_dense([text])[0].tolist()
    f = build_filter(status="ACTIVE")
    r = client.query_points(COLLECTION, query=vec, using=DENSE_NAME, limit=k,
                            query_filter=f, with_payload=True)
    dups = [{"id": p.id, "score": round(p.score, 3),
             "content": p.payload.get("content", "")[:120],
             "uri": p.payload.get("uri", "")}
            for p in r.points if p.score >= threshold]
    return dups


def ttl_scan(ttl_cfg=None, apply=False):
    ttl_cfg = ttl_cfg or {"EPISODIC": 30, "SEMANTIC": 365, "PROCEDURAL": None}
    client = get_client()
    now = datetime.now(timezone.utc)
    f = build_filter(status="ACTIVE")
    pts = client.scroll(COLLECTION, scroll_filter=f, limit=5000, with_payload=True)[0]
    to_archive = []
    for p in pts:
        created_raw = p.payload.get("created_at") or ""
        mtype = p.payload.get("type", "SEMANTIC")
        ttl = ttl_cfg.get(mtype)
        if not created_raw or ttl is None:
            continue
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        age = (now - created).total_seconds() / 86400.0
        if age > ttl:
            to_archive.append(p)
    print(f"[QDRANT TTL] {len(to_archive)} point(s) expire(s) (ep={ttl_cfg['EPISODIC']}j sem={ttl_cfg['SEMANTIC']}j)")
    for p in to_archive[:10]:
        created_raw2 = p.payload.get('created_at') or ''
        try:
            cd = datetime.fromisoformat(created_raw2.replace('Z', '+00:00'))
            if cd.tzinfo is None:
                cd = cd.replace(tzinfo=timezone.utc)
            age_disp = round((now - cd).total_seconds() / 86400.0, 1)
        except Exception:
            age_disp = '?'
        print(f"  #{p.id} [{p.payload.get('type')}] age={age_disp}j | {p.payload.get('content','')[:70]}")
    if apply and to_archive:
        client.set_payload(COLLECTION, {"status": "ARCHIVED"}, [p.id for p in to_archive])
        print(f"[OK] {len(to_archive)} point(s) -> status=ARCHIVED (reversible)")
    return to_archive


# ---------------- Tests de validation ----------------

def run_tests():
    print("=== VALIDATIONS MEMORY_QDRANT ===")
    client = get_client()
    if client.count(COLLECTION, exact=True).count == 0:
        print("[TEST] collection vide -> reindexation")
        index_memories()
    n = client.count(COLLECTION, exact=True).count
    print(f"[TEST] {n} points indexes")
    q = "le pipeline video fonctionne chaque jour et publie sur youtube"
    ok = True

    # 1) Dense
    d = search_dense(client, q, mtype="SEMANTIC")
    print(f"[1 DENSE] {len(d)} resultat(s) | top={d[0][0]} score={round(d[0][1],3)}" if d else "[1 DENSE] VIDE")
    ok &= bool(d)

    # 2) BM25 (sparse)
    b = search_bm25(client, "pipeline video", k=3)
    print(f"[2 BM25] {len(b)} resultat(s) | top={b[0][0]} score={round(b[0][1],3)}" if b else "[2 BM25] VIDE")
    ok &= bool(b)

    # 3) Hybride RRF
    h = search_hybrid(client, q, k=3, scope="core")
    print(f"[3 HYBRIDE/scope] {len(h)} resultat(s) | top={h[0][0]} rrf={round(h[0][1],4)}" if h else "[3 HYBRIDE] VIDE")
    ok &= bool(h)

    # 4) Filtre type
    ep = search_dense(client, q, mtype="EPISODIC")
    ok_f = bool(ep) and all(p[2].get("type") == "EPISODIC" for p in ep)
    print(f"[4 FILTRE TYPE] {len(ep)} resultat(s), tous EPISODIC={ok_f}")
    ok &= ok_f

    # 5) Dedup-check (probe cree a partir d'une memoire existante)
    mems = load_active_memories()
    probe = (mems[1]["content"]) if len(mems) > 1 else (mems[0]["content"] if mems else "")
    dd = dedup_check(probe) if probe else []
    print(f"[5 DEDUP-CHECK] {len(dd)} doublon(s) >= 0.85 (probe='{probe[:40]}')")
    ok &= len(dd) > 0 if probe else True

    # 6) TTL scan dry
    tl = ttl_scan(apply=False)
    print(f"[6 TTL-SCAN] {len(tl)} candidat(s) a l'archivage")
    print("=== FIN VALIDATIONS ===  " + ("TOUT OK" if ok else "AU MOINS UN TEST A ECHOUE"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--search", type=str, default=None)
    ap.add_argument("--dedup-check", type=str, default=None)
    ap.add_argument("--ttl-scan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--type", type=str, default=None)
    ap.add_argument("--scope", type=str, default=None)
    ap.add_argument("--mode", type=str, default="hybrid", choices=["dense", "bm25", "hybrid"])
    args = ap.parse_args()

    if args.reindex:
        index_memories()
    elif args.search:
        client = get_client()
        modes = {"dense": search_dense, "bm25": search_bm25, "hybrid": search_hybrid}
        res = modes[args.mode](client, args.search, mtype=args.type, scope=args.scope)
        print(f"[QDRANT {args.mode.upper()}] {len(res)} resultat(s) ({args.type or 'tous types'} / {args.scope or 'tous scopes'}) :")
        for pid, score, payload in res:
            print(f"  #{pid} score={score} [{payload.get('type')}] {payload.get('content','')[:90]}")
    elif args.dedup_check:
        dd = dedup_check(args.dedup_check)
        if dd:
            print(f"[DEDUP] {len(dd)} doublon(s) :")
            for d in dd:
                print(f"  #{d['id']} score={d['score']} | {d['content']}")
        else:
            print("[DEDUP] aucun doublon >= 0.85")
    elif args.ttl_scan:
        ttl_scan(apply=args.apply)
    elif args.test:
        run_tests()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
