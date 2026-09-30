#!/usr/bin/env python3
"""
memory_ttl.py - Cycle de vie des souvenirs Nocturne (style Mem0).
Types et TTL : EPISODIC 30j | SEMANTIC 365j | PROCEDURAL aucun
JAMAIS de suppression : ACTIVE -> ARCHIVED (deprecated=1) + snapshot JSON restaure 1:1.
Usage:
  python3 scripts/memory_ttl.py --dry-run         # rapport seul (defaut)
  python3 scripts/memory_ttl.py --apply           # archive (backup DB auto)
  python3 scripts/memory_ttl.py --restore <id>    # restaure une memoire
  python3 scripts/memory_ttl.py --list-archived   # liste des archivees
"""
import argparse, json, shutil, sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path("/home/ubuntu/nocturne_memory/nocturne_data.db")
WORK = Path("/home/ubuntu/.openclaw/workspace")
ARCHIVE_DIR = WORK / "state" / "memory_ttl_archive"
HISTORY_LOG = WORK / "state" / "memory_ttl_history.jsonl"
BACKUP_DIR = WORK / "missions" / "impl-2026-09-11" / "backups"


def detect_type(uri, content):
    u = (uri or "").lower()
    c = (content or "").lower()
    if any(k in u for k in ("procedural", "lesson", "howto")) or "lecon" in c or "savoir-faire" in c:
        return "PROCEDURAL"
    if any(k in u for k in ("session", "episodic", "log", "event")):
        return "EPISODIC"
    return "SEMANTIC"


def backup_db():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"nocturne_data_pre_ttl_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(DB, dest)
    print(f"[BACKUP] {dest}")


def log_history(entry):
    HISTORY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + chr(10))


def list_candidates(con, ttl_cfg):
    cur = con.cursor()
    cur.execute("SELECT m.id, m.content, m.created_at, s.uri FROM memories m LEFT JOIN search_documents s ON s.memory_id=m.id WHERE m.deprecated=0 AND m.content IS NOT NULL")
    now = datetime.now(timezone.utc)
    cands = []
    for r in cur.fetchall():
        mid, content, created_raw, uri = r[0], r[1], r[2], (r[3] or "")
        if not created_raw:
            continue
        try:
            created = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        mtype = detect_type(uri, content)
        ttl_days = ttl_cfg.get(mtype)
        if ttl_days is None:
            continue
        age = (now - created).total_seconds() / 86400.0
        if age > ttl_days:
            cands.append({"id": mid, "type": mtype, "ttl_days": ttl_days, "age_days": round(age, 1),
                          "uri": uri, "preview": (content or "")[:90]})
    return cands


def snapshot(con, mid, extra):
    cur = con.cursor()
    cur.execute("SELECT id, content, deprecated, migrated_to, created_at, node_uuid FROM memories WHERE id=?", (mid,))
    row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "content": row[1], "created_at": str(row[4]), "node_uuid": row[5],
            "archived_at": datetime.now(timezone.utc).isoformat(), **extra}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", type=int, default=None)
    ap.add_argument("--list-archived", action="store_true")
    ap.add_argument("--ttl-episodic", type=int, default=30)
    ap.add_argument("--ttl-semantic", type=int, default=365)
    args = ap.parse_args()

    con = sqlite3.connect(str(DB))
    ttl_cfg = {"EPISODIC": args.ttl_episodic, "SEMANTIC": args.ttl_semantic, "PROCEDURAL": None}

    if args.restore:
        snaps = sorted(ARCHIVE_DIR.glob(f"memory_{args.restore}_archived_*.json"))
        if not snaps:
            print(f"[TTL] Aucun snapshot pour #{args.restore}")
            con.close()
            return
        con.execute("UPDATE memories SET deprecated=0 WHERE id=?", (args.restore,))
        log_history({"ts": datetime.now(timezone.utc).isoformat(), "event": "ttl_restore", "memory_id": args.restore})
        con.commit()
        print(f"[TTL] Memoire #{args.restore} restauree (deprecated=0) depuis {snaps[-1].name}")
        con.close()
        return

    if args.list_archived:
        files = sorted(ARCHIVE_DIR.glob("memory_*_archived_*.json"))
        print(f"[TTL] {len(files)} memoire(s) archivee(s):")
        for f in files[-20:]:
            d = json.loads(f.read_text(encoding="utf-8"))
            print(f"  #{d['id']} [{d.get('type','?')}] age={d.get('age_days')}j date={d.get('archived_at','')[:16]}")
        con.close()
        return

    cands = list_candidates(con, ttl_cfg)
    print(f"[TTL] {len(cands)} candidate(s) a l'archivage (ep={args.ttl_episodic}j sem={args.ttl_semantic}j)")
    for c in cands:
        print(f"  #{c['id']} [{c['type']}] age={c['age_days']}j (ttl={c['ttl_days']}j) | {c['preview']}")

    if args.apply:
        backup_db()
        n = 0
        for c in cands:
            snap = snapshot(con, c["id"], {"type": c["type"], "ttl_days": c["ttl_days"], "age_days": c["age_days"]})
            if not snap:
                continue
            con.execute("UPDATE memories SET deprecated=1, migrated_to=NULL WHERE id=?", (c["id"],))
            f = ARCHIVE_DIR / f"memory_{c['id']}_archived_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
            log_history({"ts": datetime.now(timezone.utc).isoformat(), "event": "ttl_archive",
                         "memory_id": c["id"], "type": c["type"], "age_days": c["age_days"]})
            n += 1
        con.commit()
        print(f"[OK] {n} memoire(s) archivee(s). Snapshots: {ARCHIVE_DIR}")
    else:
        print(f"[DRY-RUN] {len(cands)} archivage(s) potentiel(s) - rien modifie. --apply pour archiver.")
    con.close()


if __name__ == "__main__":
    main()
