#!/usr/bin/env python3
"""alerts.py — алерты при проблемах. Пишет в logs/alerts.log + опционально Telegram."""
import os, sys, json
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
import brain

def send_alert(msg):
    line = f'[{datetime.now():%H:%M:%S}] ALERT: {msg}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/alerts.log', encoding='utf-8'), 'a') as f: f.write(line+'\n')
    # Telegram (если есть токен в env)
    token = os.environ.get('TG_BOT_TOKEN')
    chat = os.environ.get('TG_CHAT_ID')
    if token and chat:
        try:
            import urllib.request
            url = f'https://api.telegram.org/bot{token}/sendMessage'
            data = json.dumps({'chat_id': chat, 'text': msg}).encode()
            req = urllib.request.Request(url, data=data, headers={'Content-Type':'application/json'})
            urllib.request.urlopen(req, timeout=10, encoding='utf-8')
        except Exception: pass

def check():
    h = brain.health_check()
    if not h['healthy']:
        send_alert(' | '.join(h['issues']))

if __name__ == '__main__':
    check()
