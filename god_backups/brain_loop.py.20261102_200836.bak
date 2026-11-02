#!/usr/bin/env python3
"""brain_loop.py v2 — использует brain.decide() + brain.execute().
Сам решает, сам исполняет. Цикл 60 сек."""
import os, sys, time
BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
import brain
from datetime import datetime

CHECK_INTERVAL = 60

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/brain_loop.log'), 'a') as f: f.write(line+'\n')

def main():
    log('=== BRAIN LOOP v2 STARTED ===')
    brain.init_db()
    last_exec = {}
    while True:
        try:
            state = brain.get_full_state()
            decisions = brain.decide(state)
            if decisions:
                log(f'решений: {len(decisions)}')
                for d in decisions:
                    action = d['action']
                    # антидубль: не повторять < 5 мин
                    if action in last_exec and time.time()-last_exec[action] < 300:
                        continue
                    log(f'  -> {action} ({d["reason"]})')
                    brain.execute(d)
                    last_exec[action] = time.time()
            else:
                log('всё ок, действий не нужно')
        except Exception as e:
            log(f'ERROR: {e}')
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
