#!/usr/bin/env python3
"""Veille continue des 6 depots de reference (Composio, OpenHands, SWE-agent, PydanticAI, Mem0, Qdrant).
Compare HEAD + derniers tags via git ls-remote (sans auth, sans rate-limit).
Ecrit un rapport de changements dans missions/architecture-audit-2026-09/veille/.
Usage : python3 scripts/monitor_ref_repos.py [--force]
"""
import json, os, subprocess, sys, datetime
from pathlib import Path

REPOS = {
    "composio":  "https://github.com/ComposioHQ/composio.git",
    "openhands": "https://github.com/All-Hands-AI/OpenHands.git",
    "swe-agent": "https://github.com/SWE-agent/SWE-agent.git",
    "pydanticai":"https://github.com/pydantic/pydantic-ai.git",
    "mem0":      "https://github.com/mem0ai/mem0.git",
    "qdrant":    "https://github.com/qdrant/qdrant.git",
}
BASE = Path("/home/ubuntu/.openclaw/workspace/missions/architecture-audit-2026-09")
STATE_FILE = BASE / "veille" / "state.json"
OUT_DIR = BASE / "veille"
FORCE = "--force" in sys.argv


def ls_remote(url):
    """Retourne {tag: sha} des refs distantes (sans clone)."""
    r = subprocess.run(["git", "ls-remote", "--tags", "--heads", url],
                       capture_output=True, text=True, timeout=60)
    refs = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            sha, ref = parts
            name = ref.split("/")[-1]
            if name and name != "^{}":
                refs[name] = sha
    return refs


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
    today = datetime.date.today().isoformat()
    changes = []
    for name, url in REPOS.items():
        try:
            refs = ls_remote(url)
        except Exception as e:
            changes.append(f"- {name}: ERREUR ls-remote: {e}")
            continue
        head = refs.get("HEAD") or refs.get("main") or refs.get("master") or ""
        # derniers tags tries par nom (approximatif) -> garder premier tag semver
        tags = sorted([t for t in refs if t not in ("HEAD","main","master")],
                      reverse=True)[:5]
        prev = state.get(name, {})
        new_head = head and head != prev.get("head")
        new_tag = bool(tags) and tags[:1] != prev.get("tags", [])[:1]
        reason = []
        if new_head: reason.append(f"HEAD change: {prev.get('head','-')[:8]} -> {head[:8]}")
        if new_tag:  reason.append(f"tag: {prev.get('tags',['-'])[:1]} -> {tags[:1]}")
        if (new_head or new_tag or FORCE) and reason:
            changes.append(f"- {name}: " + " ; ".join(reason))
        state[name] = {"head": head, "tags": tags, "seen": today}
    STATE_FILE.write_text(json.dumps(state, indent=2))
    if changes:
        report = OUT_DIR / f"REVIEW-{today}.md"
        content = (f"# Veille repos reference - {today}\n\n"
                   + "\n".join(changes) + "\n")
        report.write_text(content)
        print("NOUVEAUX CHANGEMENTS DETECTES:")
        print("\n".join(changes))
        print(f"Rapport: {report}")
    else:
        print("Aucun changement nouveau. Veille a jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
