#!/usr/bin/env python3
"""check_etf_data_freshness.py - Veille d'obsolescence des donnees ETF du site.

Verifie que les donnees affichees sur alfredstudio.mooo.com sont fraiches :
1. Date declaree DATA_UPDATE_DATE (app.min.js) vs aujourd'hui
2. Age des fichiers de donnees (etf-data.js / min / etf-scores.js)
3. Dernier log des scrapers (hebdo dimanche, fondamentaux quotidien, catchup)

Alerte Telegram (via notify_alfred) si un seuil est depasse. Rapport JSON dans state/etf_freshness/.
Usage: python3 scripts/check_etf_data_freshness.py [--threshold N] [--quiet]
"""
import argparse, datetime, glob, json, os, re, sys

WORKSPACE = '/home/ubuntu/.openclaw/workspace'
WEB = os.path.join(WORKSPACE, 'web/pea-comparator')
STATE_DIR = os.path.join(WORKSPACE, 'state/etf_freshness')
LOG_DIR = os.path.join(os.path.expanduser('~'), 'output/logs')
sys.path.insert(0, os.path.join(WORKSPACE, 'scripts'))
from notify_alfred import send_telegram

# Pattern sans backslash/guillemet : prend la date apres DATA_UPDATE_DATE jusqu au 1er chiffre
DATE_PAT = re.compile('DATA_UPDATE_DATE[^0-9]+([0-9]{2}/[0-9]{2}/[0-9]{4})')

def parse_date(s):
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threshold', type=int, default=10, help='Jours max avant alerte')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    today = datetime.date.today()
    issues = []
    checks = {}

    # 1) DATA_UPDATE_DATE declaree (source + live)
    for label, path in [('source', os.path.join(WEB, 'app.min.js')),
                        ('live', '/var/www/html/app.min.js')]:
        try:
            txt = open(path, encoding='utf-8').read()
        except Exception as e:
            issues.append('app.min.js ' + label + ' illisible: ' + str(e))
            continue
        m = DATE_PAT.search(txt)
        if not m:
            issues.append('DATA_UPDATE_DATE introuvable (' + label + ')')
            continue
        d = parse_date(m.group(1))
        if not d:
            issues.append('DATA_UPDATE_DATE non parsee (' + label + '): ' + repr(m.group(1)))
            continue
        age = (today - d).days
        checks['declared_' + label] = {'date': str(d), 'age_jours': age}
        if age > args.threshold:
            issues.append('Donnees declarees ' + label + ': ' + str(d) + ' (age ' + str(age) + 'j, seuil ' + str(args.threshold) + 'j)')

    # 2) Age des fichiers (mtime)
    for name in ['etf-data.js', 'etf-data.min.js', 'etf-scores.js']:
        for label, path in [('source', os.path.join(WEB, name)), ('live', '/var/www/html/' + name)]:
            try:
                mt = datetime.date.fromtimestamp(os.path.getmtime(path))
                age = (today - mt).days
                checks['file_' + label + '_' + name] = {'date': str(mt), 'age_jours': age}
                if age > args.threshold:
                    issues.append('Fichier ' + name + ' (' + label + ') non modifie depuis ' + str(age) + 'j')
            except Exception:
                pass

    # 3) Dernier log des scrapers
    patterns = {'scraper_hebdo': 'etf_scraper_*.log',
                'fondamentaux_daily': 'etf_fundamentals_daily_*.log',
                'catchup': 'etf_peap_*.log'}
    for k, pat in patterns.items():
        files = sorted(glob.glob(os.path.join(LOG_DIR, pat)), key=os.path.getmtime)
        if not files:
            checks['log_' + k] = 'aucun log'
            continue
        last = files[-1]
        mt = datetime.date.fromtimestamp(os.path.getmtime(last))
        age = (today - mt).days
        checks['log_' + k] = {'fichier': os.path.basename(last), 'age_jours': age}
        if age > max(args.threshold, 14):
            issues.append('Dernier log ' + k + ' date de ' + str(age) + 'j (' + os.path.basename(last) + ')')

    os.makedirs(STATE_DIR, exist_ok=True)
    report = {'date': str(today), 'checks': checks, 'issues': issues,
              'statut': 'OBSOLETE' if issues else 'FRAIS'}
    with open(os.path.join(STATE_DIR, 'latest.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if issues:
        txt = 'Donnees ETF possiblement OBSOLETES:' + chr(10) + chr(10).join('- ' + i for i in issues)
        send_telegram(txt, parse_mode='HTML')  # toujours alerter en cas de probleme (meme --quiet)
        if not args.quiet:
            print(txt)
        sys.exit(1)
    if not args.quiet:
        ages = [c.get('age_jours', 0) for c in checks.values() if isinstance(c, dict)]
        print('Donnees ETF fraiches (max ' + str(max(ages, default=0)) + 'j, seuil ' + str(args.threshold) + 'j)')
    sys.exit(0)

if __name__ == '__main__':
    main()
