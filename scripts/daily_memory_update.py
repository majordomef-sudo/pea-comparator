#!/usr/bin/env python3
"""daily_memory_update.py - Updates MEMORY.md with daily metrics.
Cron: 0 23 * * * (daily at 23:00 UTC)"""
import json, re
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/home/ubuntu/.openclaw/workspace')
MEMORY_FILE = WORKSPACE / 'MEMORY.md'
REVENUE_DIR = WORKSPACE / 'state' / 'revenue_audit'
YT_HISTORY = WORKSPACE / 'state' / 'yt_stats_history.json'

def get_revenue_metrics():
    latest = REVENUE_DIR / 'latest.json'
    if not latest.exists():
        return None
    try:
        data = json.loads(latest.read_text())
        t = data.get('traffic', {})
        s = data.get('results', {}).get('site', {})
        return {
            'hits_24h': t.get('hits_24h', '?'),
            'ips_24h': t.get('ips_24h', '?'),
            'hits_7d': t.get('hits_7d', '?'),
            'ips_7d': t.get('ips_7d', '?'),
            'date': data.get('date', '?'),
            'site_ok': s.get('ok', '?'),
            'site_total': s.get('total', '?'),
            'youtube_subs': data.get('results', {}).get('youtube', {}).get('subs', '?'),
            'youtube_views': data.get('results', {}).get('youtube', {}).get('views', '?'),
        }
    except:
        return None

def update_memory_metrics():
    revenue = get_revenue_metrics()
    content = MEMORY_FILE.read_text()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = []
    lines.append('')
    lines.append('### Metriques (' + now + ')')
    if revenue:
        lines.append('- Site: ' + str(revenue['site_ok']) + '/' + str(revenue['site_total']) + ' pages OK')
        lines.append('- Trafic 24h: ' + str(revenue['hits_24h']) + ' hits, ' + str(revenue['ips_24h']) + ' visiteurs')
        lines.append('- Trafic 7j: ' + str(revenue['hits_7d']) + ' hits, ' + str(revenue['ips_7d']) + ' visiteurs')
        lines.append('- YouTube: ' + str(revenue['youtube_subs']) + ' abos, ' + str(revenue['youtube_views']) + ' vues')
    lines.append('')
    metrics_section = '\n'.join(lines)
    if '### Metriques' in content:
        content = re.sub(r'### Metriques \(.*?\).*?(?=\n### |\n## |\Z)', metrics_section, content, flags=re.DOTALL)
    else:
        content += metrics_section
    MEMORY_FILE.write_text(content)
    print('MEMORY.md metrics updated (' + now + ')')

if __name__ == '__main__':
    update_memory_metrics()
