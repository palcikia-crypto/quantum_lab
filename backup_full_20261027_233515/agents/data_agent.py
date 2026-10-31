#!/usr/bin/env python3
import os, sys, json, sqlite3, subprocess
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab'); DB = os.path.join(BASE, 'data/market.db')
REPORT = os.path.join(BASE, 'data/data_report.json'); LOG = os.path.join(BASE, 'logs/data_agent.log')
def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')
def main():
    log('=== DATA AGENT ===')
    if not os.path.exists(DB): log('DB нет'); return
    try:
        c = sqlite3.connect(DB, timeout=5)
        r = c.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM candles").fetchone()
        c.close()
        mtime = datetime.fromtimestamp(os.path.getmtime(DB))
        age_h = (datetime.now() - mtime).total_seconds() / 3600
        result = {'pairs': r[1], 'candles': r[0], 'age_hours': round(age_h,1), 'need': age_h > 6 or r[1] < 10}
        log(f'check: {result}')
        if result['need']:
            log('запускаю data_manager')
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/data_manager.py')],
                            stdout=open(os.path.join(BASE,'logs/data_manager.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
        with open(REPORT, 'w') as f: json.dump({'timestamp': datetime.now().isoformat(), 'result': result}, f, indent=2)
    except Exception as e: log(f'error: {e}')
if __name__ == '__main__': main()
