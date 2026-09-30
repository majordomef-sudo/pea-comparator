#!/usr/bin/env python3
"""end_of_session.py - Extracts learnings from session notes."""
import json, sys
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/home/ubuntu/.openclaw/workspace')
MEMORY_DIR = WORKSPACE / 'memory'
REFLECTION_DIR = WORKSPACE / 'state' / 'auto-reflection'
ERRORS_FILE = REFLECTION_DIR / 'errors.json'
LEARNINGS_FILE = MEMORY_DIR / 'agent_learnings.json'
IMPROVEMENTS_LOG = REFLECTION_DIR / 'improvements.log'
REFLECTION_DIR.mkdir(parents=True, exist_ok=True)

def get_latest_session():
    files = sorted(MEMORY_DIR.glob('2026-*.md'), reverse=True)
    files = [f for f in files if 'pending_synthesis' not in f.name and 'agent_learnings' not in f.name]
    return files[0] if files else None

def extract_sections(content):
    sections = {'errors': [], 'lessons': [], 'actions': []}
    current = 'misc'
    for line in content.split('\n'):
        l = line.strip().lower()
        if l.startswith('### erreur') or l.startswith('### error') or l.startswith('### bug'):
            current = 'errors'
        elif l.startswith('### lecon') or l.startswith('### lesson'):
            current = 'lessons'
        elif l.startswith('### action') or l.startswith('### todo'):
            current = 'actions'
        elif l.startswith('###'):
            current = 'misc'
        elif (line.strip().startswith('- ') or line.strip().startswith('* ')) and current in sections:
            sections[current].append(line.strip().lstrip('- *'))
    return sections

def detect_patterns(errors):
    patterns = {}
    for e in errors:
        el = e.lower()
        for pat, words in [('path_issues', ['cron','chemin','path']), ('pipeline_issues', ['hook','whisper','pipeline']), ('deployment_issues', ['deploy','nginx','cache']), ('js_issues', ['js','javascript','event'])]:
            if any(w in el for w in words):
                patterns[pat] = patterns.get(pat, 0) + 1
    return patterns

def update_errors(patterns):
    data = {'patterns': {}, 'total_errors': 0, 'last_analysis': ''}
    if ERRORS_FILE.exists():
        try: data = json.loads(ERRORS_FILE.read_text())
        except: pass
    for p, c in patterns.items():
        data['patterns'][p] = data['patterns'].get(p, 0) + c
    data['total_errors'] = sum(data['patterns'].values())
    data['last_analysis'] = datetime.now().isoformat()
    ERRORS_FILE.write_text(json.dumps(data, indent=2))
    return data

def update_learnings(sections, src_name):
    learnings = {}
    if LEARNINGS_FILE.exists():
        try: learnings = json.loads(LEARNINGS_FILE.read_text())
        except: learnings = {}
    entries = []
    for l in sections.get('lessons', []):
        entries.append({'learning': l.strip(), 'category': 'lesson', 'source': src_name, 'timestamp': datetime.now().isoformat()})
    for e in sections.get('errors', []):
        entries.append({'learning': e.strip(), 'category': 'failure', 'source': src_name, 'timestamp': datetime.now().isoformat()})
    if entries:
        learnings.setdefault('end_of_session', [])
        existing = {x.get('source', '') for x in learnings['end_of_session']}
        for e in entries:
            if e['source'] not in existing:
                learnings['end_of_session'].append(e)
        learnings['end_of_session'] = learnings['end_of_session'][-50:]
        LEARNINGS_FILE.write_text(json.dumps(learnings, indent=2, ensure_ascii=False))
    return len(entries)

def log_improvements(src_name, counts):
    if not counts:
        return
    ts = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    fix_map = {'path_issues': 'Verifier chemins', 'pipeline_issues': 'Verifier pipeline', 'deployment_issues': 'Ajouter cache-busting', 'js_issues': 'Utiliser event delegation'}
    lines = ['', '--- ' + ts + ' ---', 'Fichier: ' + src_name]
    for p, c in counts.items():
        lines.append('  ' + p + ': ' + str(c) + 'x')
        if c >= 3 and p in fix_map:
            lines.append('  SUGGESTION: ' + fix_map[p])
    IMPROVEMENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(IMPROVEMENTS_LOG, 'a') as f:
        f.write('\n'.join(lines))

def run(content, src_name):
    sections = extract_sections(content)
    patterns = detect_patterns(sections['errors'])
    update_errors(patterns)
    n = update_learnings(sections, src_name)
    log_improvements(src_name, patterns)
    return {'learnings': n, 'patterns': patterns}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true')
    parser.add_argument('--session')
    parser.add_argument('--cron', action='store_true')
    args = parser.parse_args()
    if args.auto:
        sf = get_latest_session()
        if not sf:
            return
        r = run(sf.read_text(), sf.name)
        if not args.cron:
            print('Session: ' + sf.name + ' | L: ' + str(r['learnings']) + ' | P: ' + str(r['patterns']))
    elif args.session:
        p = Path(args.session)
        if not p.exists():
            return
        r = run(p.read_text(), p.name)
        if not args.cron:
            print('Session: ' + p.name + ' | L: ' + str(r['learnings']))
    else:
        print('Usage: --auto or --session <file>')

if __name__ == '__main__':
    main()
