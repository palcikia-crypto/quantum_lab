#!/usr/bin/env python3
import os, json
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
GATE = os.path.join(BASE, 'data/gate_all.json')
REPORT = os.path.join(BASE, 'data/gate_report.json')
LOG = os.path.join(BASE, 'logs/gate_agent.log')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line+'\n')

def main():
    log('=== GATE AGENT ===')
    if os.path.exists(GATE):
        d = json.load(open(GATE, encoding='utf-8'))
        mtime = datetime.fromtimestamp(os.path.getmtime(GATE))
        age_h = (datetime.now() - mtime).total_seconds() / 3600
        result = {'summary': d.get('summary'), 'age_hours': round(age_h,1), 'need': age_h > 2}
        log(f'check: {result}')
        with open(REPORT, 'w', encoding='utf-8') as f: json.dump({'timestamp': datetime.now().isoformat(), 'result': result}, f, indent=2)
    else:
        log('gate_all.json нет')

if __name__ == '__main__': main()
