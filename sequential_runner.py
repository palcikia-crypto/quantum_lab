#!/usr/bin/env python3
import os, sys, subprocess
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/sequential_runner.log')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')

def get_load():
    try:
        return float(open('/proc/loadavg').read().split()[0])
    except:
        return 0

def run_step(name, cmd, timeout=600):
    load = get_load()
    if load > 6:
        log(f'  {name}: load {load:.1f} > 6, пропускаю')
        return False
    log(f'  {name}: запуск (load {load:.1f})')
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=BASE)
        if r.returncode == 0:
            log(f'  {name}: OK')
            return True
        log(f'  {name}: FAIL (rc={r.returncode}) {r.stderr[-200:]}')
    except subprocess.TimeoutExpired:
        log(f'  {name}: TIMEOUT')
    except Exception as e:
        log(f'  {name}: ERROR {e}')
    return False

def main():
    log('=== SEQUENTIAL RUNNER START ===')
    run_step('data_agent', ['python3', 'agents/data_agent.py'], timeout=120)
    # gate_agent: только отчёт (не запускает gate)
    if get_load() < 5:
        import subprocess as _sp
        if not _sp.run(['pgrep','-f','evolution.py'], capture_output=True).stdout:
            run_step('evolution', ['nice','-n','19','python3', 'core/evolution.py'], timeout=1800)
    else:
        log(f'  evolution: load {get_load():.1f} > 5, пропускаю')
    run_step('live_agent', ['python3', 'agents/live_agent.py'], timeout=120)
    run_step('risk_agent', ['python3', 'agents/risk_agent.py'], timeout=120)
    run_step('report_agent', ['python3', 'agents/report_agent.py'], timeout=120)
    log('=== SEQUENTIAL RUNNER DONE ===')

if __name__ == '__main__':
    main()
