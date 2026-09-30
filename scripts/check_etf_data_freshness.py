#!/usr/bin/env python3
"""check_etf_data_freshness.py - Veille d'obsolescence des donnees ETF (site PEA Comparator).

Verifie que les donnees affichees sur alfredstudio.mooo.com sont fraiches :
1. Fichiers de donnees REELLEMENT charges par le site (detectes dans le HTML) :
   presence + age + coherence md5 live <-> source (detection de desynchronisation de deploy)
2. Date declaree DATA_UPDATE_DATE (app.min.js) : INFORMATIF (garde-fou 60 j)
3. Dernier log des scrapers (hebdo dimanche, fondamentaux quotidien, catchup)

Regle anti-faux-positif (30/09/2026) : un fichier present dans /var/www/html mais
reference par AUCUNE page HTML est un ORPHELIN. Il est rapporte en INFO et ne
declenche jamais d'alerte (cas /var/www/html/etf-data.js, fige depuis le 19/09
car les deploiements ne poussent que la version .min.js -> fausse alerte quotidienne).
La date declaree est elle aussi informative : elle retarde normalement sur les
donnees (scraper quotidien) et ne doit pas declencher d'alerte quotidienne.

Alerte Telegram (via notify_alfred) si un seuil est depasse. Rapport JSON dans state/etf_freshness/.
Usage: python3 scripts/check_etf_data_freshness.py [--threshold N] [--quiet] [--no-notify]
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import sys

WORKSPACE = '/home/ubuntu/.openclaw/workspace'
WEB = os.path.join(WORKSPACE, 'web/pea-comparator')
STATE_DIR = os.path.join(WORKSPACE, 'state/etf_freshness')
LOG_DIR = os.path.join(os.path.expanduser('~'), 'output/logs')
sys.path.insert(0, os.path.join(WORKSPACE, 'scripts'))
from notify_alfred import send_telegram

# Pattern sans backslash/guillemet : prend la date apres DATA_UPDATE_DATE jusqu au 1er chiffre
DATE_PAT = re.compile('DATA_UPDATE_DATE[^0-9]+([0-9]{2}/[0-9]{2}/[0-9]{4})')
SCRIPT_SRC_PAT = re.compile(r'src="([^"]+\.js)[^"]*"')
DATA_FILES = ['etf-data.js', 'etf-data.min.js', 'etf-scores.js']
DEFAULT_REFERENCED = ['etf-data.min.js', 'etf-scores.js']


def parse_date(s):
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def md5_of(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def referenced_data_files():
    """Fichiers de donnees effectivement charges par au moins une page du site."""
    refs = set()
    pages = sorted(set(glob.glob('/var/www/html/*.html') + glob.glob('/var/www/html/*/index.html')))
    for page in pages:
        try:
            txt = open(page, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        for m in SCRIPT_SRC_PAT.finditer(txt):
            base = os.path.basename(m.group(1))
            if base in DATA_FILES:
                refs.add(base)
    return refs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threshold', type=int, default=10, help='Jours max avant alerte')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--no-notify', action='store_true', help='ne pas envoyer de Telegram (tests)')
    args = ap.parse_args()

    today = datetime.date.today()
    issues = []
    checks = {}

    # 1) DATA_UPDATE_DATE declaree (source + live) -> INFORMATIF
    declared = {}
    for label, path in [('source', os.path.join(WEB, 'app.min.js')),
                        ('live', '/var/www/html/app.min.js')]:
        try:
            txt = open(path, encoding='utf-8').read()
        except Exception as e:
            issues.append('app.min.js ' + label + ' illisible: ' + str(e))
            continue
        m = DATE_PAT.search(txt)
        if not m:
            checks['declared_' + label] = 'DATA_UPDATE_DATE introuvable'
            continue
        d = parse_date(m.group(1))
        if not d:
            checks['declared_' + label] = 'non parsee: ' + repr(m.group(1))
            continue
        age = (today - d).days
        declared[label] = d
        checks['declared_' + label] = {'date': str(d), 'age_jours': age, 'role': 'informatif'}
        if age > max(60, args.threshold * 4):
            issues.append('Date declaree ' + label + ' tres ancienne: ' + str(d) + ' (' + str(age) + 'j)')

    # 1bis) Fichiers de donnees reellement charges par le site
    referenced = referenced_data_files()
    if referenced:
        checks['referenced_data_files'] = sorted(referenced)
    else:
        referenced = set(DEFAULT_REFERENCED)
        checks['referenced_data_files'] = 'non detecte -> repli sur ' + ', '.join(DEFAULT_REFERENCED)

    # 2) Age des fichiers de donnees + coherence live <-> source
    newest_source_data = None
    for name in DATA_FILES:
        src = os.path.join(WEB, name)
        live = '/var/www/html/' + name

        if name not in referenced:
            if os.path.exists(live):
                mt = datetime.date.fromtimestamp(os.path.getmtime(live))
                checks['file_orphan_' + name] = {'date': str(mt), 'age_jours': (today - mt).days,
                                                 'role': 'ORPHELIN: present dans /var/www/html mais charge par aucune page - pas d alerte'}
            continue

        if os.path.exists(src):
            mt = datetime.date.fromtimestamp(os.path.getmtime(src))
            age = (today - mt).days
            newest_source_data = mt if newest_source_data is None else max(newest_source_data, mt)
            checks['file_source_' + name] = {'date': str(mt), 'age_jours': age}
            if age > args.threshold:
                issues.append('Fichier source ' + name + ' non modifie depuis ' + str(age) + 'j')
        else:
            issues.append('[CRITIQUE] Fichier source ' + name + ' ABSENT: ' + src)

        if not os.path.exists(live):
            issues.append('[CRITIQUE] Fichier ' + name + ' ABSENT de /var/www/html (pourtant charge par le site)')
            continue
        mt = datetime.date.fromtimestamp(os.path.getmtime(live))
        age = (today - mt).days
        checks['file_live_' + name] = {'date': str(mt), 'age_jours': age}
        if age > args.threshold:
            issues.append('Fichier ' + name + ' (live) non modifie depuis ' + str(age) + 'j')
        if os.path.exists(src) and md5_of(src) != md5_of(live):
            issues.append('[CRITIQUE] Fichier ' + name + ' live DESYNCHRONISE de la source (md5 different)')

    # 2bis) Retard de la date declaree sur les donnees reelles (info seule)
    if newest_source_data and 'live' in declared:
        checks['declared_lag_jours'] = (declared['live'] - newest_source_data).days

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
        if not args.no_notify:
            send_telegram(txt, parse_mode='HTML')  # toujours alerter en cas de probleme (meme --quiet)
        if not args.quiet:
            print(txt)
        sys.exit(1)

    if not args.quiet:
        ages = [c['age_jours'] for c in checks.values() if isinstance(c, dict) and 'age_jours' in c]
        line = 'Donnees ETF fraiches (max ' + str(max(ages, default=0)) + 'j, seuil ' + str(args.threshold) + 'j)'
        orphans = [k for k in checks if k.startswith('file_orphan_')]
        if orphans:
            line += ' | orphelin(s) ignore(s): ' + ', '.join(o.replace('file_orphan_', '') for o in orphans)
        print(line)
    sys.exit(0)


if __name__ == '__main__':
    main()
