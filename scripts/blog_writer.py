#!/usr/bin/env python3
"""
blog_writer.py V3 — Automated Blog Content Generation and Publishing for Ghost CMS 5.x
Usage: python3 blog_writer.py <free|premium>

Uses mobiledoc format with proper markup indexing.
"""

import os
import sys
import sys as _sys
_sys.path.insert(0,'/home/ubuntu/.openclaw/workspace/scripts')
from model_router import log_llm_call
import time
import json
import hmac
import hashlib
import base64
import random
import re
import requests
from datetime import datetime

# ── Ghost CMS ──────────────────────────────────────────────────────────────
def _load_secret(key):
    secrets_file = os.path.expanduser('~/.secrets/ghost_keys.txt')
    if os.path.exists(secrets_file):
        with open(secrets_file) as f:
            for line in f:
                if line.strip().startswith(key):
                    return line.strip().split('=', 1)[1]
    return None

GHOST_API_KEY = _load_secret('GHOST_ADMIN_API_KEY_STAFF') or ''
GHOST_BASE_URL = 'https://alfredstudio.mooo.com/blog/ghost/api/admin'

# ── LLM ────────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = ''
if not os.environ.get('OPENROUTER_API_KEY'):
    secrets_file = os.path.expanduser('~/.secrets/env')
    if os.path.exists(secrets_file):
        with open(secrets_file) as f:
            for line in f:
                if 'OPENROUTER_API_KEY' in line:
                    key = line.strip().split('=', 1)[1].strip().strip('"').strip("'")
                    OPENROUTER_API_KEY = key
                    break
else:
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# ── Themes ─────────────────────────────────────────────────────────────────
THEMES_FREE = [
    "L'investissement passif : pourquoi les ETF sont vos meilleurs alliés",
    "Comprendre le PEA : le guide complet pour débuter en France",
    "Inflation et pouvoir d'achat : comment protéger son épargne en 2026",
    "Pourquoi la diversification est la clé de la gestion de risque",
    "L'impact de la psychologie sur vos décisions d'investissement",
    "Les frais cachés en assurance-vie : combien vous perdez vraiment",
    "ETF capitalisant vs distribuant : lequel choisir pour votre PEA",
    "5 erreurs que tout investisseur débutant commet en bourse",
]

THEMES_PREMIUM = [
    "La stratégie Dave Cambridge appliquée au marché français",
    "Optimiser son allocation d'actifs : le modèle à 4 piliers",
    "Gestion de l'incertitude et robustesse des portefeuilles",
    "L'art du DCA : mathématiques et psychologie",
    "Stratégies de protection contre l'inflation par les actifs réels",
    "Analyse des small caps européennes accessibles en PEA",
    "Comment construire un portefeuille permanent à la Harry Browne",
    "Les corrélations cachées entre classes d'actifs en 2026",
]


# ── JWT Generator ──────────────────────────────────────────────────────────

def generate_jwt(api_key):
    key_id, secret_hex = api_key.split(':')
    iat = int(time.time())
    header = json.dumps({'alg': 'HS256', 'kid': key_id, 'typ': 'JWT'}, separators=(',', ':'))
    payload = json.dumps({'iat': iat, 'exp': iat + 300, 'aud': '/admin/'}, separators=(',', ':'))
    def b64_url(s):
        return base64.urlsafe_b64encode(s.encode()).rstrip(b'=').decode()
    sig_input = f'{b64_url(header)}.{b64_url(payload)}'.encode()
    h = hmac.new(bytes.fromhex(secret_hex), sig_input, hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(h).rstrip(b'=').decode()
    return f'{b64_url(header)}.{b64_url(payload)}.{sig}'


# ── HTML → Mobiledoc ───────────────────────────────────────────────────────

def html_to_mobiledoc(html):
    """Convert HTML to Ghost mobiledoc with proper markup indexing."""
    html = html.strip()

    # Strip markdown fences
    if html.startswith('```'):
        html = '\n'.join(html.split('\n')[1:])
    if html.endswith('```'):
        html = html.rsplit('```', 1)[0]

    # Strip html/body wrappers
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if m:
        html = m.group(1).strip()
    html = re.sub(r'</?html[^>]*>', '', html, flags=re.IGNORECASE).strip()

    # Block split
    blocks = re.split(
        r'(<(?:h[1-6]|p|ul|ol)[^>]*>.*?</(?:h[1-6]|p|ul|ol)>)',
        html, flags=re.DOTALL
    )
    blocks = [b.strip() for b in blocks if b.strip()]

    markups = []
    markup_map = {}

    def get_markup_idx(tag, href=''):
        if tag == 'strong':
            key = ('strong',)
        elif tag == 'em':
            key = ('em',)
        elif tag == 'a':
            key = ('a', href)
        else:
            return []
        if key not in markup_map:
            idx = len(markups)
            markup_map[key] = idx
            if tag == 'a':
                markups.append(['a', ['href', href]])
            else:
                markups.append([tag])
        return [markup_map[key]]

    def parse_inline(text):
        """Parse inline HTML → mobiledoc marker list."""
        markers = []
        parts = re.split(
            r'(<(?:strong|b|em|i|a[^>]*)[^>]*>.*?</(?:strong|b|em|i|a)>|<br\s*/?>)',
            text, flags=re.DOTALL
        )
        for p in parts:
            p = p.strip()
            if not p:
                continue

            sm = re.match(r'<(strong|b)>(.*?)</\1>', p, re.DOTALL | re.IGNORECASE)
            em = re.match(r'<(em|i)>(.*?)</\1>', p, re.DOTALL | re.IGNORECASE)
            am = re.match(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', p, re.DOTALL | re.IGNORECASE)
            bm = re.match(r'<br\s*/?>', p, re.IGNORECASE)

            if sm:
                idx = get_markup_idx('strong')
                t = re.sub(r'<[^>]+>', '', sm.group(2))
                markers.append([0, idx, 0, t])
            elif em:
                idx = get_markup_idx('em')
                t = re.sub(r'<[^>]+>', '', em.group(2))
                markers.append([0, idx, 0, t])
            elif am:
                idx = get_markup_idx('a', am.group(1))
                t = re.sub(r'<[^>]+>', '', am.group(2))
                markers.append([0, idx, 0, t])
            elif bm:
                markers.append([0, [], 0, ''])
            else:
                t = re.sub(r'<[^>]+>', '', p)
                if t.strip():
                    markers.append([0, [], 0, t])

        if not markers:
            markers = [[0, [], 0, text]]
        return markers

    sections = []
    for block in blocks:
        tm = re.match(r'<(h[1-6]|p|ul|ol)[^>]*>\s*(.*?)\s*</\1>', block, re.DOTALL | re.IGNORECASE)
        if not tm:
            sections.append([1, 'p', parse_inline(block)])
            continue

        tag = tm.group(1).lower()
        inner = tm.group(2)

        if tag.startswith('h'):
            sections.append([1, f'h{tag[1]}', parse_inline(inner)])
        elif tag == 'p':
            sections.append([1, 'p', parse_inline(inner)])
        elif tag in ('ul', 'ol'):
            items = re.findall(r'<li[^>]*>(.*?)</li>', inner, re.DOTALL)
            li_list = []
            for item in items:
                li_list.append([1, 'li', parse_inline(item)])
            if li_list:
                sections.append([1, tag, li_list])

    if not sections:
        sections = [[1, 'p', [[0, [], 0, html]]]]

    doc = {'version': '0.3.1', 'atoms': [], 'cards': [], 'markups': markups, 'sections': sections}
    return json.dumps(doc)


# ── LLM ────────────────────────────────────────────────────────────────────

def get_llm_text(prompt):
    if not OPENROUTER_API_KEY:
        raise Exception('OPENROUTER_API_KEY not set')
    r = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}', 'Content-Type': 'application/json'},
        json={'model': 'deepseek/deepseek-v4.1-flash', 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.7},
        timeout=120
    )
    r.raise_for_status()
    j = r.json()
    u = j.get('usage', {})
    log_llm_call('deepseek/deepseek-v4.1-flash', u.get('prompt_tokens', 0), u.get('completion_tokens', 0))
    content = j['choices'][0]['message']['content']
    if not content:
        raise Exception('LLM returned empty content')
    return content


# ── Ghost Publisher ────────────────────────────────────────────────────────

def publish_post(title, mobiledoc, visibility):
    token = generate_jwt(GHOST_API_KEY)
    headers = {'Authorization': f'Ghost {token}', 'Content-Type': 'application/json'}

    slug = re.sub(r'[^a-z0-9-]', '-', title.lower().strip())[:80].strip('-')

    body = {
        'posts': [{
            'title': title,
            'mobiledoc': mobiledoc,
            'slug': slug,
            'visibility': visibility,
            'status': 'published',
        }]
    }
    r = requests.post(f'{GHOST_BASE_URL}/posts/?source=html', headers=headers, json=body, timeout=60)
    r.raise_for_status()
    return r.json()['posts'][0]


# ── Main ───────────────────────────────────────────────────────────────────

def main(mode):
    if not OPENROUTER_API_KEY:
        print('❌ OPENROUTER_API_KEY not found in ~/.secrets/env')
        sys.exit(1)
    if not GHOST_API_KEY:
        print('❌ GHOST_ADMIN_API_KEY_STAFF not found in ~/.secrets/ghost_keys.txt')
        sys.exit(1)

    themes = THEMES_FREE if mode == 'free' else THEMES_PREMIUM
    visibility = 'public' if mode == 'free' else 'paid'
    word_count = '800' if mode == 'free' else '1500'

    theme = random.choice(themes)
    print(f'🚀 Starting {mode} blog generation...')
    print(f'🎯 Topic: {theme}')

    prompt = (
        f'Écris un article de blog professionnel en français sur : "{theme}".\n\n'
        'Site : Alfred Studio, plateforme d\'éducation financière.\n\n'
        'FORMAT HTML PUR (pas de markdown) :\n'
        '- <h2> pour le titre principal, <h3> pour les sous-sections\n'
        '- <p> pour les paragraphes, <ul><li> pour les listes\n'
        '- <strong> pour les concepts clés, <a href="https://alfredstudio.mooo.com/pea-comparator/"> pour les liens\n'
        f'~{word_count} mots. Style pédagogique avec données concrètes.\n'
        'Structure : intro + 3-4 sections + conclusion avec CTA comparateur PEA.\n'
        'PAS de ```html. Commence directement par le contenu HTML.'
    )

    print('🤖 Generating via LLM...')
    html = get_llm_text(prompt)
    html = html.strip()
    if html.startswith('```'):
        html = '\n'.join(html.split('\n')[1:])
    if html.endswith('```'):
        html = html.rsplit('```', 1)[0]
    html = html.strip()

    if not html:
        print('❌ Empty content after cleaning')
        sys.exit(1)
    print(f'✅ Content: {len(html)} chars | Preview: {html[:120]}...')

    print('🔄 Converting to mobiledoc...')
    md = html_to_mobiledoc(html)
    print(f'✅ Mobiledoc: {len(md)} chars')

    title = theme + datetime.now().strftime(' [%d/%m]')
    print(f'📤 Publishing to Ghost...')
    try:
        result = publish_post(title, md, visibility)
        print(f'✅ Published: {result.get("title", "ok")}')
        print(f'   URL: {result.get("url", "N/A")}')
    except Exception as e:
        print(f'❌ Failed: {e}')
        if hasattr(e, 'response') and e.response is not None:
            print(f'   Response: {e.response.text[:300]}')
        sys.exit(1)

    print(f'✅ Blog {mode} terminé.')


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('free', 'premium'):
        print('Usage: python3 blog_writer.py <free|premium>')
        sys.exit(1)
    main(sys.argv[1])
