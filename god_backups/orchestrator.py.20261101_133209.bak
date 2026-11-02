#!/usr/bin/env python3
"""orchestrator.py — автономный цикл Quantum Lab.
Каждые 6 часов: data_manager -> gate_v2 -> active_strategies -> live_monitor.
Ночью (00:00-06:00) тяжёлые прогоны с nice 19."""
import os, sys, json, time, subprocess
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
CYCLE_HOURS = 6
NIGHT_START = 0
NIGHT_END = 6

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/orchestrator.log'), 'a') as f: f.write(line+'\n')

def is_night():
    h = datetime.now().hour
    return NIGHT_START <= h < NIGHT_END

def run_module(name, script, args=None):
    log(f'--- {name} ---')
    cmd = ['python3', script] + (args or [])
    try:
        nice = ['nice', '-n', '19'] if is_night() else []
        r = subprocess.run(nice + cmd, cwd=BASE, capture_output=True, text=True, timeout=1800)
        if r.returncode == 0:
            log(f'{name}: OK')
            return True
        log(f'{name}: FAIL (rc={r.returncode}) {r.stderr[:200]}')
        return False
    except subprocess.TimeoutExpired:
        log(f'{name}: TIMEOUT'); return False
    except Exception as e:
        log(f'{name}: ERROR {e}'); return False

def update_active():
    """Берёт gate_v2.json, выбирает GOLDEN + TRADE_NOW, пишет active_strategies.json."""
    gate = os.path.join(BASE, 'data/gate_v2.json')
    out = os.path.join(BASE, 'data/active_strategies.json')
    if not os.path.exists(gate):
        log('gate_v2.json нет, пропускаю'); return
    try:
        d = json.load(open(gate))
        pairs = {}
        for r in d.get('results', []):
            if r['verdict'] not in ('GOLDEN', 'TRADE_NOW'): continue
            pair = r['symbol']; tf = r['tf']
            key = f'{pair}_{tf}'
            if key not in pairs or r['L1']['wr'] > pairs[key]['wr']:
                pairs[key] = {
                    'symbol': pair, 'tf': tf, 'strategy': r['strategy'],
                    'wr': r['L1']['wr'], 'n': r['L1']['n'], 'p': r['L1']['p'],
                    'verdict': r['verdict'], 'score': r['score'], 'model': r['model'],
                }
        out_data = {'updated_at': datetime.now().isoformat(), 'pairs': pairs}
        with open(out, 'w') as f: json.dump(out_data, f, indent=2, ensure_ascii=False)
        log(f'active_strategies: {len(pairs)} стратегий')
    except Exception as e:
        log(f'update_active error: {e}')

def main():
    log('=== ORCHESTRATOR STARTED ===')
    while True:
        try:
            log(f'--- CYCLE START (night={is_night()}) ---')
            run_module('data_manager', 'core/data_manager.py')
            run_module('gate_v2', 'core/gate_v2.py')
            update_active()
            run_module('live_monitor', 'core/live_monitor.py')
            log('--- CYCLE DONE ---')
        except Exception as e:
            log(f'CYCLE ERROR: {e}')
        log(f'сплю {CYCLE_HOURS}ч')
        time.sleep(CYCLE_HOURS * 3600)

if __name__ == '__main__':
    main()
