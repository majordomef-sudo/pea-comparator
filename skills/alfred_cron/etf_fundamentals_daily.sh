#!/bin/bash
# ETF Fundamentals DAILY - enrichit ~30 ETF/jour (encours, devise, dist/cap...) + score + validation
# Complement du cron hebdomadaire (dimanche 10h). Meme script, meme source de verite, lock dedie.

LOCKFILE="/tmp/etf_fundamentals_daily.lock"
LOGDIR="$HOME/output/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/etf_fundamentals_daily_$(date +%Y%m%d).log"

exec 200>"$LOCKFILE"
flock -n 200 || { echo "[$(date)] Lock pris, deja en cours" >> "$LOG"; exit 1; }

echo "[$(date)] Debut passe quotidienne fondamentaux (30 ETF)" >> "$LOG"
cd "$HOME/.openclaw/workspace"
if [ -f "venv/bin/activate" ]; then source venv/bin/activate; fi

python3 scripts/etf_scrapler.py --fundamentals 30 --build-min >> "$LOG" 2>&1

# Validation apres enrichissement
python3 scripts/validate_etf_data.py /home/ubuntu/.openclaw/workspace/web/pea-comparator/etf-data.js >> "$LOG" 2>&1

# Score Alfred a jour (deploiement + cache-bust)
(cd web/pea-comparator && python3 etf_quality_score.py --emit-scores) >> "$LOG" 2>&1

echo "[$(date)] Termine. Exit code: $?" >> "$LOG"
flock -u 200
