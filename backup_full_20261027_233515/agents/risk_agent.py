#!/usr/bin/env python3
import os, json
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
REPORT = os.path.join(BASE, 'data/risk_report.json'); LOG = os.path.join(BASE, 'logs/risk_agent.log')
def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')
def kelly(wr, rr):
    if rr <= 0: return 0
    return max(0, wr - (1-wr)/rr)
def main():
    log('=== RISK AGENT ===')
    p = os.path.join(BASE, 'data/active_strategies.json')
    if not os.path.exists(p): log('active нет'); return
    active = json.load(open(p))
    results = []
    for key, cfg in active.get('pairs', {}).items():
        wr = cfg.get('wr', 0) / 100
        k = kelly(wr, 1.0)
        results.append({'key': key, 'wr': cfg.get('wr'), 'kelly': round(k,3), 'bet': round(min(k*100,20),1), 'trade': cfg.get('trade')})
    log(f'risk: {len(results)} стратегий')
    with open(REPORT, 'w') as f: json.dump({'timestamp': datetime.now().isoformat(), 'results': results}, f, indent=2)
if __name__ == '__main__': main()
