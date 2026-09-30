#!/bin/bash
# NeuroFinance Cron Wrapper v2 — improved resilience
set -euo pipefail

LOCKFILE="/tmp/neuro_finance.lock"
LOGDIR="$HOME/output/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/neuro_finance_$(date +%Y%m%d).log"
QUEUE_SCRIPT="$HOME/.openclaw/workspace/skills/alfred_cron/pipeline_idea_queue.py"

echo "[$(date)] START" >> "$LOG"

# ── Disk check ──
TMP_FREE=$(df /tmp --output=avail 2>/dev/null | tail -1)
if [ "${TMP_FREE:-0}" -lt 1048576 ]; then
    echo "[$(date)] FAIL: /tmp disk low (${TMP_FREE}K)" >> "$LOG"
    exit 1
fi


# ── Lock acquisition ──
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "[$(date)] BUSY: another pipeline running" >> "$LOG"
    exit 0
fi

echo "$$" > "$LOCKFILE"

# ── Cleanup old temp files ──
echo "[$(date)] Nettoyage..." >> "$LOG"
find /tmp -maxdepth 1 -name "alfred_pipeline_*" -type d -mtime +2 -exec rm -rf {} + 2>/dev/null || true
find /tmp -maxdepth 1 -name "*.MOV" -mtime +1 -delete 2>/dev/null || true

# ── Run queue ──
echo "[$(date)] Lancement queue" >> "$LOG"
cd "$HOME/.openclaw/workspace" || exit 1

START_TS=$(date +%s)
set +e
python3 "$QUEUE_SCRIPT" >> "$LOG" 2>&1
RET=$?
set -e
ELAPSED=$(( $(date +%s) - START_TS ))

echo "[$(date)] Done: exit=$RET elapsed=${ELAPSED}s" >> "$LOG"

# ── Notify on failure ──
if [ $RET -ne 0 ]; then
    source "$HOME/.secrets/env" 2>/dev/null || true
    curl -s -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN:-}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID:-}" \
        -d "text=PIPELINE FAIL: exit=$RET elapsed=${ELAPSED}s $(date)" \
        > /dev/null 2>&1 || true
fi

# ── Release lock ──
rm -f "$LOCKFILE"
flock -u 200 2>/dev/null || true

exit $RET
