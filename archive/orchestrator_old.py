#!/usr/bin/env python3
import os, sys, time
sys.path.insert(0, os.path.expanduser('~/quantlab'))
from core.strategy_manager import update_from_findings, FINDINGS
from datetime import datetime
CHECK_INTERVAL = 300
def log(m): print(f'[{datetime.now():%H:%M:%S}] {m}', flush=True)
def main():
    log('Orchestrator запущен')
    last_mtime = 0; last_check = 0
    while True:
        try:
            now = time.time()
            if now - last_check < CHECK_INTERVAL: time.sleep(10); continue
            last_check = now
            if not os.path.exists(FINDINGS): log('findings нет'); continue
            mtime = os.path.getmtime(FINDINGS)
            if mtime == last_mtime: log('findings не менялся'); continue
            log(f'findings обновлён ({datetime.fromtimestamp(mtime):%H:%M:%S})')
            result = update_from_findings()
            log(f'изменений: {result.get("changes", 0)}, пар: {result.get("pairs", 0)}')
            last_mtime = mtime
        except Exception as e:
            log(f'ERROR: {e}'); time.sleep(60)
if __name__ == '__main__': main()
