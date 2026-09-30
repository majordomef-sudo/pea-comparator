#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Memoire episodique structuree (style Mem0).
Extrait les sections horodatees des notes quotidiennes et les ecrit dans
Nocturne avec une URI episodic_* -> indexee EPISODIC dans Qdrant.
DRY-RUN par defaut. Jamais de suppression. Journal JSONL.
Usage:
  python3 scripts/memory_episodic.py --list-sources
  python3 scripts/memory_episodic.py --days 2 --max-per-day 3        (dry-run)
  python3 scripts/memory_episodic.py --days 2 --max-per-day 3 --apply
"""
import argparse, json, re, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import requests

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
MEMORY_DIR = WORKSPACE / "memory"
STATE_DIR = WORKSPACE / "state"
NOCTURNE_BASE = "http://127.0.0.1:8898"
JOURNAL = STATE_DIR / "episodic_history.jsonl"
NL = chr(10)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

def nocturne_session():
    r = requests.post(f"{NOCTURNE_BASE}/mcp", headers=HEADERS,
        json={"jsonrpc": "2.0", "id": "ep-init", "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "alfred-episodic", "version": "1.0"}}},
        timeout=15)
    return r.headers.get("Mcp-Session-Id", "")

def nocturne_create(sesh, content, title=None):
    args = {"parent_uri": "core://", "content": content, "priority": 1,
            "disclosure": "When reviewing what happened in a given session or day"}
    if title:
        args["title"] = title
    r = requests.post(f"{NOCTURNE_BASE}/mcp", headers={**HEADERS, "Mcp-Session-Id": sesh},
        json={"jsonrpc": "2.0", "id": f"e-{int(time.time()*1000)}", "method": "tools/call",
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

def parse_sections(md_text):
    sections = []
    cur = {"title": None, "lines": []}
    for line in md_text.splitlines():
        m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if m:
            if cur["title"] or cur["lines"]:
                sections.append(cur)
            cur = {"title": m.group(1).strip(), "lines": []}
        else:
            cur["lines"].append(line)
    if cur["title"] or cur["lines"]:
        sections.append(cur)
    return sections

def is_timed(title):
    return bool(re.match(r"^\d{1,2}:\d{2}", title or ""))

def build_episodic(date_str, title, lines):
    body_lines = [l for l in lines if l.strip()]
    body = NL.join(body_lines)[:1800]
    if not body.strip():
        return None
    return f"[SESSION {date_str}] {title}{NL}{body}"

def main():
    ap = argparse.ArgumentParser(description="Memoire episodique structuree")
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--max-per-day", type=int, default=3)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--list-sources", action="store_true")
    args = ap.parse_args()

    STATE_DIR.mkdir(exist_ok=True)
    if args.list_sources:
        today = datetime.utcnow().date()
        for i in range(args.days):
            f = MEMORY_DIR / f"{today - timedelta(days=i)}.md"
            if f.exists():
                n = len([s for s in parse_sections(f.read_text()) if is_timed(s["title"])])
                print(f"{f.name}: {n} section(s) horodatees")
        return

    sesh = nocturne_session()
    if not sesh:
        print("[ERR] pas de session Nocturne (MCP down ?)")
        sys.exit(1)

    today = datetime.utcnow().date()
    created = skipped = 0
    for i in range(args.days):
        d = today - timedelta(days=i)
        f = MEMORY_DIR / f"{d}.md"
        if not f.exists():
            continue
        date_str = d.isoformat()
        sections = [s for s in parse_sections(f.read_text()) if is_timed(s["title"])]
        for s in sections[-args.max_per_day:]:
            content = build_episodic(date_str, s["title"], s["lines"])
            if not content:
                continue
            slug = re.sub(r"[^a-z0-9]+", "_", (s["title"] or "notes").lower())[:40]
            title = f"episodic_session_{date_str}_{slug}"
            known = nocturne_search(sesh, f"episodic_session_{date_str}", limit=5)
            if any(title in k for k in known):
                skipped += 1
                continue
            if args.apply:
                ok = nocturne_create(sesh, content, title=title)
                if ok:
                    with JOURNAL.open("a") as jf:
                        jf.write(json.dumps({"ts": datetime.utcnow().isoformat(), "title": title, "date": date_str}) + NL)
                    created += 1
                else:
                    print(f"[ERR] {title}")
                    skipped += 1
            else:
                created += 1
                print(f"[DRY] {title} | {content[:70]}...")
    mode = "ecrites" if args.apply else "planifiees (dry-run, --apply pour ecrire)"
    print(f"Resume: {created} session(s) {mode}, {skipped} deja connues/skips")

if __name__ == "__main__":
    main()
