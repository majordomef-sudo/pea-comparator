#!/usr/bin/env python3
"""
memory_maintenance.py — Maintenance hebdomadaire de la memoire.
Enchaine : TTL (archivage ephemere) -> Dedup (sweep) -> Reindex Qdrant (synchronisation).
Log : /home/ubuntu/output/logs/memory_maintenance.log
Rapport : state/memory_maintenance/<date>.json
"""
import subprocess, sys, json, logging
from datetime import datetime, timezone
from pathlib import Path

WS = Path("/home/ubuntu/.openclaw/workspace")
LOG = Path("/home/ubuntu/output/logs/memory_maintenance.log")
REPORT_DIR = WS / "state" / "memory_maintenance"
LOG.parent.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(filename=str(LOG), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("memory_maintenance")

def run(step, cmd, dry=False, timeout=3600):
    log.info(f"[{step}] {cmd}" + (" (DRY)" if dry else ""))
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(WS))
        ok = r.returncode == 0
        lines = (r.stdout + r.stderr).strip().splitlines()
        tail = lines[-4:] if lines else ["(no output)"]
        log.info(f"[{step}] exit={r.returncode} | " + " | ".join(tail))
        return ok, chr(10).join(tail)
    except subprocess.TimeoutExpired:
        log.error(f"[{step}] TIMEOUT {timeout}s")
        return False, "TIMEOUT"

def main(dry=False):
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    steps = [
        ("TTL", "python3 scripts/memory_ttl.py" + ("" if dry else " --apply"), dry),
        ("DEDUP", "python3 scripts/memory_dedup.py" + ("" if dry else " --apply"), dry),
        ("REINDEX", "python3 scripts/memory_qdrant.py --reindex", dry),
    ]
    results = {}
    for name, cmd, is_dry in steps:
        if name == "REINDEX" and dry:
            log.info("[REINDEX] skippe en dry-run")
            results[name] = (True, "skippe (dry-run)")
            continue
        ok, tail = run(name, cmd, dry=is_dry)
        results[name] = (ok, tail)
        if not ok:
            log.error(f"[{name}] ECHEC -> arret de la chaine (stabilite avant tout)")
            break
    report = {"ts": stamp, "dry": dry, "results": {k: v[0] for k, v in results.items()}}
    rfile = REPORT_DIR / ("report_dry_" + stamp.replace(":", "-") + ".json" if dry else "report_" + stamp.replace(":", "-") + ".json")
    rfile.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if all(v[0] for v in results.values()) else 1

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Maintenance hebdo memoire (TTL -> dedup -> reindex Qdrant)")
    ap.add_argument("--dry-run", action="store_true", help="TTL + dedup en rapport seul (aucune ecriture)")
    args = ap.parse_args()
    sys.exit(main(dry=args.dry_run))
