#!/usr/bin/env python3
import os, json, subprocess
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
REPORT = os.path.join(BASE, 'data/evolve_report.json'); LOG = os.path.join(BASE, 'logs/evolve_agent.log')
def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')
def main():
    log('=== EVOLVE AGENT ===')
    log('запускаю evolution.py')
    try:
        r = subprocess.run(['nice','-n','19','python3', os.path.join(BASE,'core/evolution.py')],
                          capture_output=True, text=True, timeout=3600)
        result = {'status': 'ok' if r.returncode == 0 else 'fail', 'output': r.stdout[-300:]}
    except Exception as e: result = {'status': 'fail', 'error': str(e)}
    log(f'evolution: {result["status"]}')
    with open(REPORT, 'w') as f: json.dump({'timestamp': datetime.now().isoformat(), 'result': result}, f, indent=2)
if __name__ == '__main__': main()
