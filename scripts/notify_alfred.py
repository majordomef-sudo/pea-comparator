#!/usr/bin/env python3
"""notify_alfred.py — Module partagé d'envoi Telegram pour tous les scripts Alfred."""
import json, os, subprocess, sys

SECRETS_PATH = '/home/ubuntu/.secrets/env'

def load_secrets():
    """Charge les secrets depuis .secrets/env."""
    secrets = {}
    if os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    if k.startswith('export '):
                        k = k[7:]
                    v = v.strip('"').strip("'")
                    secrets[k] = v
    return secrets


def escape_markdown(text):
    """Échappe les caractères spéciaux Markdown pour Telegram."""
    special = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for c in special:
        text = text.replace(c, f'\\{c}')
    return text


def send_telegram(message, parse_mode='Markdown'):
    """Envoie un message Telegram via le bot Alfred.
    
    Args:
        message: Texte du message (Markdown compatible)
        parse_mode: 'Markdown' ou 'HTML'
    Returns:
        bool: True si envoyé avec succès
    """
    secrets = load_secrets()
    bot_token = secrets.get('TELEGRAM_BOT_TOKEN')
    chat_id = secrets.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print(f'Erreur : token ou chat_id manquant', file=sys.stderr)
        return False
    
    # Auto-escape if Markdown to prevent "/>entity parsing errors"
    text = escape_markdown(message) if parse_mode == 'Markdown' else message
    
    cmd = [
        'curl', '-s', '-X', 'POST',
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        '-d', f'chat_id={chat_id}',
        '--data-urlencode', f'text={text}',
        '--data-urlencode', f'parse_mode={parse_mode}',
        '--data-urlencode', 'disable_web_page_preview=true'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        resp = json.loads(result.stdout)
        if resp.get('ok'):
            print(f'✅ Telegram envoyé', file=sys.stderr)
            return True
        else:
            print(f'❌ Telegram: {resp.get("description", "inconnue")}', file=sys.stderr)
            return False
    except Exception as e:
        print(f'❌ Telegram error: {e}', file=sys.stderr)
        return False

if __name__ == '__main__':
    # Test mode
    msg = '🧪 Test notification depuis notify_alfred.py'
    send_telegram(msg)
