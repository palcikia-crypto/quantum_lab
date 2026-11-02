#!/usr/bin/env python3
import os, json, subprocess
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
REPORT = os.path.join(BASE, 'data/live_report.json'); LOG = os.path.join(BASE, 'logs/live_agent.log')
def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line+'\n')
def main():
    log('=== LIVE AGENT ===')
    try:
        r = subprocess.run(['python3', os.path.join(BASE,'core/live_monitor.py')],
                          capture_output=True, text=True, timeout=120)
        result = {'status': 'ok' if r.returncode == 0 else 'fail'}
    except Exception as e: result = {'status': 'fail', 'error': str(e)}
    log(f'live_monitor: {result["status"]}')
    with open(REPORT, 'w', encoding='utf-8') as f: json.dump({'timestamp': datetime.now().isoformat(), 'result': result}, f, indent=2)
if __name__ == '__main__': main()
