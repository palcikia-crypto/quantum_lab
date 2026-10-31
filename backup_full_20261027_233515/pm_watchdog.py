#!/usr/bin/env python3
import os, subprocess, time
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
RSBOT = os.path.expanduser('~/rsbot')
LOG = os.path.join(BASE, 'logs/watchdog.log')
CHECK = 30

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')

def is_running(pattern):
    if isinstance(pattern, list):
        pattern = pattern[0]
    r = subprocess.run(['pgrep','-f',pattern], capture_output=True)
    return bool(r.stdout)

def get_load():
    try:
        r = subprocess.run(['ps','aux'], capture_output=True, text=True)
        return len(r.stdout.split('\n'))
    except:
        return 0

def start(name, script, log_path, nice=False):
    if isinstance(script, list):
        cmd = ['python3','-u'] + script
    else:
        cmd = ['python3','-u',script]
    if nice: cmd = ['nice','-n','19'] + cmd
    subprocess.Popen(cmd, stdout=open(log_path,'a'), stderr=subprocess.STDOUT, start_new_session=True)
    log(f'  ✅ {name} запущен')

def main():
    log('=== PM WATCHDOG STARTED ===')
    comps = [
        ('V1', os.path.join(RSBOT,'pm_bot.py'), os.path.join(RSBOT,'pm_v1.log'), False),
        ('V4', os.path.join(RSBOT,'pm_bot_v4.py'), os.path.join(RSBOT,'pm_bot_v4.log'), False),
        ('V5', os.path.join(RSBOT,'pm_bot_v5.py'), os.path.join(RSBOT,'pm_v5.log'), False),
        ('V6.1', os.path.join(RSBOT,'pm_bot_v6.py'), os.path.join(RSBOT,'pm_bot_v6.log'), False),
        ('V7', os.path.join(RSBOT,'pm_bot_v7.py'), os.path.join(RSBOT,'pm_v7.log'), False),
        ('oracle', ['core/oracle.py', 'loop'], os.path.join(BASE,'logs/oracle.log'), True),
        ('brain', 'core/brain_loop.py', os.path.join(BASE,'logs/brain_loop.log'), False),
        ('web', ['web/app.py'], os.path.join(BASE,'logs/web.log'), False),
        ('self_org', 'core/self_organizer.py', os.path.join(BASE,'logs/self_organizer.log'), False),
    ]
    while True:
        load = get_load()
        for name, script, logp, nice in comps:
            pattern = (script[0] if isinstance(script, list) else script).split()[0].split('/')[-1]
            if not is_running(pattern):
                log(f'⚠️ {name} упал — перезапуск (load {load})')
                start(name, script, logp, nice)
        # Эволюция и gate — только если load < 500 (ps даёт количество строк, не loadavg)
        if load < 500:
            if not is_running('evolution.py'):
                log(f'  эволюция (load {load})')
                start('evolution', os.path.join(BASE,'core/evolution.py'), os.path.join(BASE,'logs/evolution.log'), True)
            if not is_running('run_gate_full.py'):
                log(f'  gate (load {load})')
                start('gate', os.path.join(BASE,'run_gate_full.py'), os.path.join(BASE,'logs/gate_full.log'), True)
        time.sleep(CHECK)

if __name__ == '__main__': main()
