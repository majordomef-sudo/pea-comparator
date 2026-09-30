#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genere state/memory_context.md : lecons PROCEDURAL recentes + sessions EPISODIC
recentes, injecte en bootstrap par le hook agent:bootstrap 'memory-context'.
Lecture SQLite Nocturne directe (~50ms, zero fastembed, zero LLM) -> hook ultra-rapide.
Usage:
  python3 scripts/memory_context_recall.py [--write] [--lessons 8] [--sessions 2]
"""
import argparse, re, sqlite3
from datetime import datetime
from pathlib import Path

DB = "/home/ubuntu/nocturne_memory/nocturne_data.db"
WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
OUT = WORKSPACE / "state" / "memory_context.md"
NL = chr(10)

def clean(s, maxlen=180):
    s = (s or "").replace("[PROCEDURAL]", "").replace("[SEMANTIC]", "").replace("[EPISODIC]", "")
    s = re.sub(r"^\[source:[^\]]*\]", "", s).strip()
    return s[:maxlen]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="ecrit state/memory_context.md (sinon stdout)")
    ap.add_argument("--lessons", type=int, default=6)
    ap.add_argument("--sessions", type=int, default=1)
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    lessons = cur.execute("""
        SELECT m.content, m.created_at FROM memories m
        JOIN search_documents s ON s.memory_id = m.id
        WHERE m.deprecated = 0 AND s.uri LIKE 'core://procedural_lesson_%'
        ORDER BY m.id DESC LIMIT ?""", (args.lessons,)).fetchall()
    sessions = cur.execute("""
        SELECT m.content, m.created_at FROM memories m
        JOIN search_documents s ON s.memory_id = m.id
        WHERE m.deprecated = 0 AND s.uri LIKE '%episodic_session_%'
        ORDER BY m.id DESC LIMIT ?""", (args.sessions,)).fetchall()
    con.close()

    L = []
    L.append("---")
    L.append("CONTEXTE MEMOIRE (injecte par le hook agent:bootstrap memory-context).")
    L.append("Source: state/memory_context.md — regenere par scripts/memory_context_recall.py. Ne pas editer a la main.")
    L.append("---")
    L.append("")
    L.append("## Lecons procedurales (les plus recentes)")
    if lessons:
        for c, ts in lessons:
            L.append(f"- {clean(c)}" + (f"  [{str(ts)[:10]}]" if ts else ""))
    else:
        L.append("- (aucune lecon procedurale indexee)")
    L.append("")
    if sessions:
        L.append("## Sessions recentes")
        for c, ts in sessions:
            L.append(f"- {clean(c, 300)}" + (f"  [{str(ts)[:10]}]" if ts else ""))
        L.append("")
    body = NL.join(L)

    if args.write:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(body + NL, encoding="utf-8")
        print(f"[OK] {OUT} ({len(body)} chars)")
    else:
        print(body)

if __name__ == "__main__":
    main()
