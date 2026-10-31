#!/usr/bin/env python3
"""Автовосстановление: если v4 остановлен агентом — перезапустить через час."""
import os, json, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
STATE = os.path.join(BASE, 'tools/agent/recovery.json')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/agent.log'), 'a') as f:
        f.write(line + '\n')

def load():
    if os.path.exists(STATE):
        try: return json.load(open(STATE))
        except: pass
    return {'stopped_v4_at': 0}

def save(s):
    json.dump(s, open(STATE, 'w'))

def main():
    s = load()
    if s.get('stopped_v4_at', 0) == 0:
        return
    # если прошло > 1 часа — перезапустить v4
    if time.time() - s['stopped_v4_at'] > 3600:
        import subprocess
        subprocess.Popen(['python3', '-u', 'core/okx_bot_paper_v4.py'],
                         cwd=BASE,
                         stdout=open(os.path.join(BASE, 'logs/okx_bot_paper_v4.log'), 'a'),
                         stderr=subprocess.STDOUT)
        log('🔄 recovery: v4 перезапущен после stop_v4')
        s['stopped_v4_at'] = 0
        save(s)

if __name__ == '__main__':
    main()
