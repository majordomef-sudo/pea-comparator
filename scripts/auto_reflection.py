#!/usr/bin/env python3
"""auto_reflection.py - Detects recurring error patterns on startup."""
import json, sys
from pathlib import Path

WORKSPACE = Path('/home/ubuntu/.openclaw/workspace')
REFLECTION_DIR = WORKSPACE / 'state' / 'auto-reflection'
ERRORS_FILE = REFLECTION_DIR / 'errors.json'

FIXES = {
    'path_issues': 'Verifier les chemins de fichiers dans les scripts et crons.',
    'pipeline_issues': 'Verifier le pipeline video (hook, whisper, montage).',
    'deployment_issues': 'Ajouter cache-busting, verifier les 3 fichiers apres deploiement.',
    'js_issues': 'Utiliser event delegation et DOMContentLoaded systematiquement.',
}

def check():
    if not ERRORS_FILE.exists():
        return {'patterns': {}, 'total_errors': 0, 'alerts': []}
    data = json.loads(ERRORS_FILE.read_text())
    patterns = data.get('patterns', {})
    total = data.get('total_errors', 0)
    alerts = []
    for p, c in patterns.items():
        if c >= 5:
            alerts.append({'pattern': p, 'count': c, 'severity': 'high', 'fix': FIXES.get(p, '')})
        elif c >= 3:
            alerts.append({'pattern': p, 'count': c, 'severity': 'medium', 'fix': FIXES.get(p, '')})
    return {'patterns': patterns, 'total_errors': total, 'alerts': alerts}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Exit code only')
    args = parser.parse_args()
    result = check()
    if args.check:
        sys.exit(1 if result['alerts'] else 0)
    if result['alerts']:
        for a in result['alerts']:
            icon = '\U0001f534' if a['severity'] == 'high' else '\U0001f7e1'
            print(icon + ' ' + a['pattern'] + ': ' + str(a['count']) + 'x')
            if a['fix']:
                print('   Fix: ' + a['fix'])
    else:
        print('\u2705 OK - ' + str(result['total_errors']) + ' erreurs totales, aucun pattern recurrent')

if __name__ == '__main__':
    main()
