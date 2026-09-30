#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Memoire procedurale (lecons, savoir-faire) — style Mem0.
Extrait les lecons depuis MEMORY.md et les notes quotidiennes, les ecrit dans
Nocturne avec une URI procedural_* -> indexee PROCEDURAL dans Qdrant.
DRY-RUN par defaut. RECALL : retrouver les lecons pertinentes pour un sujet.
Usage:
  python3 scripts/memory_procedural.py --scan                 (dry-run)
  python3 scripts/memory_procedural.py --scan --apply
  python3 scripts/memory_procedural.py --recall "pipeline video"
"""
import argparse, json, re, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import requests

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
MEMORY_DIR = WORKSPACE / "memory"
STATE_DIR = WORKSPACE / "state"
NOCTURNE_BASE = "http://127.0.0.1:8898"
JOURNAL = STATE_DIR / "procedural_history.jsonl"
NL = chr(10)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

def nocturne_session():
    r = requests.post(f"{NOCTURNE_BASE}/mcp", headers=HEADERS,
        json={"jsonrpc": "2.0", "id": "pr-init", "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "alfred-procedural", "version": "1.0"}}},
        timeout=15)
    return r.headers.get("Mcp-Session-Id", "")

def nocturne_create(sesh, content, title=None):
    args = {"parent_uri": "core://", "content": content, "priority": 4,
            "disclosure": "When applying lessons learned or best practices"}
    if title:
        args["title"] = title
    r = requests.post(f"{NOCTURNE_BASE}/mcp", headers={**HEADERS, "Mcp-Session-Id": sesh},
        json={"jsonrpc": "2.0", "id": f"p-{int(time.time()*1000)}", "method": "tools/call",
              "params": {"name": "create_memory", "arguments": args}}, timeout=15)
    for line in r.text.splitlines():
        if line.startswith("data:"):
            d = json.loads(line[5:])
            if "result" in d:
                return True
    return False

def nocturne_search(sesh, query, limit=5):
    r = requests.post(f"{NOCTURNE_BASE}/mcp", headers={**HEADERS, "Mcp-Session-Id": sesh},
        json={"jsonrpc": "2.0", "id": f"s-{int(time.time()*1000)}", "method": "tools/call",
              "params": {"name": "search_memory", "arguments": {"query": query, "limit": limit}}},
        timeout=15)
    for line in r.text.splitlines():
        if line.startswith("data:"):
            d = json.loads(line[5:])
            if "result" in d:
                txt = d["result"]["content"][0]["text"]
                if "No matching" in txt:
                    return []
                return re.findall(r"core://\S+", txt)
    return []

BULLET = re.compile(r"^\s*[-+*]\s+(.+)")

def scan_lessons(max_days=30):
    """Lecons depuis la section 'Lecons apprises' de MEMORY.md + notes daily."""
    lessons = []
    mem = WORKSPACE / "MEMORY.md"
    if mem.exists():
        lines = mem.read_text(errors="ignore").splitlines()
        in_sec = False
        for i, line in enumerate(lines):
            if re.match(r"^#{1,3}\s*Le[çc]ons", line.strip()):
                in_sec = True
                continue
            if in_sec:
                if re.match(r"^##\s", line.strip()) and "Lecon" not in line:
                    in_sec = False  # fin: prochaine section niveau 2
                    continue
                if re.match(r"^###\s", line.strip()):
                    continue  # sous-titre: on reste dans la section
                m = BULLET.match(line)
                if m:
                    s = m.group(1).strip()
                    if len(s) > 15 and not s.startswith(("|", "Session", "Profile", "Run")):
                        lessons.append((s, "MEMORY.md"))
    today = datetime.utcnow().date()
    for i in range(max_days):
        f = MEMORY_DIR / f"{today - timedelta(days=i)}.md"
        if not f.exists():
            continue
        for line in f.read_text(errors="ignore").splitlines():
            m = BULLET.match(line)
            if not m:
                continue
            s = m.group(1).strip()
            if re.search(r"le[çc]on|fix|bug|re[^a-z]|ne jamais|toujours|retry|timeout|echec|echou|root cause", s, re.I)                and len(s) > 15:
                lessons.append((s, f.name))
    seen, out = set(), []
    for content, src in lessons:
        key = re.sub(r"[^a-z0-9]+", "", content.lower())[:60]
        if key and key not in seen:
            seen.add(key)
            out.append((content, src))
    return out

def recall(sujet, k=5):
    sys.path.insert(0, str(WORKSPACE / "scripts"))
    from memory_qdrant import get_client, search_hybrid
    client = get_client()
    res = search_hybrid(client, sujet, k=k, mtype="PROCEDURAL")
    print(f"[RECALL] '{sujet}' -> {len(res)} lecon(s):")
    for pid, score, payload in res:
        print(f"  - ({score:.3f}) {payload.get('content', '')[:150]}")
    return res

def main():
    ap = argparse.ArgumentParser(description="Memoire procedurale (lecons)")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--recall", metavar="SUJET")
    ap.add_argument("--max-days", type=int, default=30)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    STATE_DIR.mkdir(exist_ok=True)
    if args.recall:
        recall(args.recall)
        return

    lessons = scan_lessons(args.max_days)
    print(f"Scan: {len(lessons)} lecon(s) trouvee(s) (limite {args.limit})")
    lessons = lessons[:args.limit]
    sesh = nocturne_session()
    if not sesh:
        print("[ERR] pas de session Nocturne (MCP down ?)")
        sys.exit(1)
    created = skipped = 0
    for content, src in lessons:
        slug = re.sub(r"[^a-z0-9]+", "_", content.lower())[:40].strip("_") or "lecon"
        title = f"procedural_lesson_{slug}"
        known = nocturne_search(sesh, title, limit=3)
        if any(title in k for k in known):
            skipped += 1
            continue
        enriched = f"[PROCEDURAL][source:{src}] {content}"
        if args.apply:
            ok = nocturne_create(sesh, enriched, title=title)
            if ok:
                with JOURNAL.open("a") as jf:
                    jf.write(json.dumps({"ts": datetime.utcnow().isoformat(), "title": title, "source": src}) + NL)
                created += 1
            else:
                print(f"[ERR] {title}")
                skipped += 1
        else:
            created += 1
            print(f"[DRY] {title} | {content[:80]}")
    mode = "ecrites" if args.apply else "planifiees (dry-run, --apply pour ecrire)"
    print(f"Resume: {created} lecon(s) {mode}, {skipped} deja presentes/skips")

if __name__ == "__main__":
    main()
