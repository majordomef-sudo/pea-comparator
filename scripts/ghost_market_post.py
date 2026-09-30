"""
Ghost Market Post — Publie un article blog avec les donnees de marche

Usage:
    python3 scripts/ghost_market_post.py [--publish] [--dry-run]
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
import time
import base64
import hmac
import hashlib

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
MARKET_FILE = os.path.join(WORKSPACE, 'data', 'market', 'market_latest.json')
SECRETS_FILE = '/home/ubuntu/.secrets/ghost_keys.txt'

def load_market_data():
    with open(MARKET_FILE) as f:
        return json.load(f)

def get_ghost_token():
    """Generate Ghost Admin API token from staff key"""
    try:
        with open(SECRETS_FILE) as f:
            for line in f:
                if 'GHOST_ADMIN_API_KEY_STAFF' in line and '=' in line:
                    key = line.split('=', 1)[1].strip().strip('"\'"')
                    break
            else:
                return None
        
        # Ghost Admin API key format: {id}:{secret}
        parts = key.split(':')
        if len(parts) != 2:
            return None
        
        key_id, secret = parts
        
        # Create JWT
        iat = int(time.time())
        exp = iat + 5 * 60  # 5 minutes
        
        header = base64.urlsafe_b64encode(json.dumps({
            'alg': 'HS256', 'typ': 'JWT', 'kid': key_id
        }).encode()).rstrip(b'=').decode()
        
        payload = base64.urlsafe_b64encode(json.dumps({
            'iat': iat, 'exp': exp, 'aud': '/admin/'
        }).encode()).rstrip(b'=').decode()
        
        # Secret is hex-encoded, decode first
        secret_bytes = bytes.fromhex(secret)
        signature = base64.urlsafe_b64encode(hmac.new(
            secret_bytes, f'{header}.{payload}'.encode(), hashlib.sha256
        ).digest()).rstrip(b'=').decode()
        
        return f'{header}.{payload}.{signature}'
    except Exception as e:
        print(f'  Token error: {e}')
        return None

def build_market_post(data):
    indices = data.get('indices', [])
    etfs = data.get('etfs', [])
    today = datetime.now()
    
    html = '<!--kg-card-begin: html-->'
    html += f'<h2>Marche du {today.strftime("%d/%m/%Y")}</h2>'
    html += f'<p>Revue rapide des marches financiers au {today.strftime("%d/%m/%Y a %H:%M")}.</p>'
    
    html += '<h3>Indices actions</h3>'
    html += '<table><thead><tr><th>Indice</th><th>Valeur</th><th>Variation</th></tr></thead><tbody>'
    for idx in indices:
        if 'valeur' in idx:
            arrow = '🟢' if idx['variation'] > 0 else '🔴'
            html += f'<tr><td>{idx["nom"]}</td><td>{idx["valeur"]:,.2f}</td><td>{arrow} {idx["variation"]:+.2f}%</td></tr>'
    html += '</tbody></table>'
    
    html += '<h3>ETF phares</h3>'
    html += '<table><thead><tr><th>ETF</th><th>ISIN</th><th>Prix</th></tr></thead><tbody>'
    for etf in etfs:
        if 'prix' in etf:
            html += f'<tr><td>{etf["nom"]}</td><td><code>{etf["isin"]}</code></td><td>{etf["prix"]}€</td></tr>'
    html += '</tbody></table>'
    
    html += '<h3>Vous cherchez le meilleur ETF pour votre PEA ?</h3>'
    html += '<p>Comparez plus de 430 ETFs eligibles au PEA sur notre <a href="https://alfredstudio.mooo.com">comparateur gratuit</a>.</p>'
    html += '<!--kg-card-end: html-->'
    
    return html

def create_ghost_post(html_content, publish=False):
    token = get_ghost_token()
    if not token:
        print('❌ Token Ghost non genere')
        return False
    
    today = datetime.now()
    title = f"Marche du {today.strftime('%d/%m/%Y')} — CAC 40, S&P 500, ETFs"
    
    import requests
    
    api_url = 'https://alfredstudio.mooo.com/blog/ghost/api/admin/posts/'
    headers = {
        'Authorization': f'Ghost {token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'posts': [{
            'title': title,
            'html': html_content,
            'status': 'published' if publish else 'draft',
            'feature_image': None,
            'tags': ['marche', 'finance', 'ETF', 'indices'],
            'meta_title': f"Marche {today.strftime('%d/%m/%Y')} — CAC 40, ETF PEA",
            'meta_description': f"Revue des marches du {today.strftime('%d/%m/%Y')} : indices et ETFs PEA en direct."
        }]
    }
    
    try:
        r = requests.post(api_url, headers=headers, json=payload, timeout=15)
        if r.status_code in (200, 201):
            post = r.json().get('posts', [{}])[0]
            url = post.get('url', '')
            print(f"✅ Article cree: {title}")
            print(f"   Status: {'publie' if publish else 'brouillon'}")
            return True
        else:
            print(f"❌ Erreur Ghost: {r.status_code} - {r.text[:300]}")
            return False
    except Exception as e:
        print(f"❌ Erreur requete: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true', help='Publier au lieu de brouillon')
    parser.add_argument('--dry-run', action='store_true', help='Afficher le contenu sans publier')
    
    args = parser.parse_args()
    
    print('📝 Ghost Market Post Generator')
    print(f'   Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    
    data = load_market_data()
    print(f'   Donnees: {len(data.get("indices",[]))} indices, {len(data.get("etfs",[]))} ETFs')
    
    html = build_market_post(data)
    
    if args.dry_run:
        print(f'\n--- HTML ({len(html)} chars) ---')
        print(html[:500] + '...')
        print('\n✅ Dry-run')
        return
    
    result = create_ghost_post(html, publish=args.publish)
    print(f'\n{"✅ OK" if result else "❌ Echec"}')

if __name__ == '__main__':
    main()
