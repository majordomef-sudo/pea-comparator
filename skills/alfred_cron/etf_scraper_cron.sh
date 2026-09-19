#!/bin/bash
# ETF Scraper Cron - 4 passes : prix/perfs (yfinance) + fondamentaux justETF + validation + Score Alfred
# Dimanche 10h UTC apres cloture europeenne. Un seul script, une seule source de verite.

LOCKFILE="/tmp/etf_scraper.lock"
LOGDIR="$HOME/output/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/etf_scraper_$(date +%Y%m%d).log"

exec 200>"$LOCKFILE"
flock -n 200 || { echo "[$(date)] Lock pris, scraper deja en cours" >> "$LOG"; exit 1; }

echo "[$(date)] Debut scraper ETF (prix + fondamentaux + validation + score)" >> "$LOG"
cd "$HOME/.openclaw/workspace"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "[$(date)] Pass 1/3 - prix/perfs (--batch 20)" >> "$LOG"
python3 scripts/etf_scrapler.py --batch 20 >> "$LOG" 2>&1

echo "[$(date)] Pass 2/3 - fondamentaux justETF (--fundamentals 60 --build-min)" >> "$LOG"
python3 scripts/etf_scrapler.py --fundamentals 60 --build-min >> "$LOG" 2>&1

echo "[$(date)] Pass 3/3 - validation donnees" >> "$LOG"
python3 scripts/validate_etf_data.py /home/ubuntu/.openclaw/workspace/web/pea-comparator/etf-data.js >> "$LOG" 2>&1

echo "[$(date)] Pass 4/4 - Score Alfred (--emit-scores, deploiement+cache-bust)" >> "$LOG"
(cd web/pea-comparator && python3 etf_quality_score.py --emit-scores) >> "$LOG" 2>&1

EXIT_CODE=$?
echo "[$(date)] Termine. Exit code: $EXIT_CODE" >> "$LOG"
flock -u 200
exit $EXIT_CODE
