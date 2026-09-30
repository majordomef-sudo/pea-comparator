#!/usr/bin/env python3
import os, sys, datetime
def send_tg(text):
    try:
        sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/scripts')
        import notify_alfred
        return notify_alfred.send_telegram(text, parse_mode='HTML')
    except Exception as e:
        print('TG fail: ' + str(e))
        return False
def main():
    dry = '--dry' in sys.argv
    today = datetime.date.today().strftime('%Y%m%d')
    log = os.path.expanduser('~/output/logs/neuro_finance_' + today + '.log')
    content = ''
    if os.path.exists(log):
        content = open(log).read()
    else:
        content = 'LOG INTROUVABLE'
    if 'Done: exit=0' in content and 'Echec idee' not in content:
        msg = '✅ Pipeline ' + today + ': OK (exit=0, vidéo publiée)'
    else:
        tail = content[-1200:]
        msg = '⚠️ Pipeline ' + today + ': échec (pas de Done exit=0)' + chr(10) + tail
    print(msg)
    if not dry:
        send_tg(msg)
main()
