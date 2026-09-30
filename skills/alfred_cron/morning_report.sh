#!/bin/bash
LOCKFILE="/tmp/morning_report.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "skip morning_report"; exit 0; }
# morning_report.sh — Wrapper pour le rapport matinal V2
set -euo pipefail
source ~/.secrets/env
cd ~/.openclaw/workspace
python3 scripts/morning_report.py
echo "✅ Rapport matinal V2 terminé"