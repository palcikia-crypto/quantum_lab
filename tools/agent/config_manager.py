#!/usr/bin/env python3
import os, json, shutil
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/agent.log')
CONFIGS = {
    'lab': os.path.join(BASE, 'config/lab.json'),
    'tpsl_v4': os.path.join(BASE, 'data/okx_tpsl_v4.json'),
    'rules': os.path.join(BASE, 'tools/agent/rules.json'),
}
def log(m):
    with open(LOG, 'a') as f: f.write(f'[{datetime.now():%H:%M:%S}] [config] {m}\n')
def read(name):
    p = CONFIGS.get(name)
    if not p or not os.path.exists(p): return None
    try: return json.load(open(p))
    except: return None
def write(name, data):
    p = CONFIGS.get(name)
    if not p: return False
    if os.path.exists(p):
        shutil.copy(p, p + '.bak.' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    try:
        json.dump(data, open(p, 'w'), indent=2, ensure_ascii=False)
        log(f'write {name}: ok'); return True
    except: return False
def validate(name):
    d = read(name)
    if d is None: return False
    if name == 'tpsl_v4':
        for sym, cfg in d.items():
            if not isinstance(cfg, dict) or 'tp' not in cfg or 'sl' not in cfg: return False
    return True
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2: print('usage: <read|validate> <name>'); sys.exit(1)
    if sys.argv[1] == 'read': print(json.dumps(read(sys.argv[2]), indent=2, ensure_ascii=False))
    elif sys.argv[1] == 'validate': print('valid' if validate(sys.argv[2]) else 'invalid')
