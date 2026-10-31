#!/usr/bin/env python3
import os, json, sqlite3, subprocess, time
from datetime import datetime
import config_manager as cfg
BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/agent.log')
def log(m):
    with open(LOG, 'a') as f: f.write(f'[{datetime.now():%H:%M:%S}] [heal] {m}\n')
def heal_tpsl_v4():
    if not cfg.validate('tpsl_v4'):
        p = cfg.CONFIGS['tpsl_v4']
        import glob, shutil
        baks = sorted(glob.glob(p + '.bak.*'))
        if baks:
            shutil.copy(baks[-1], p); log(f'tpsl_v4 восстановлен'); return True
        return False
    return True
def clean_stale_market():
    # DELETE ОТКЛЮЧЁН — не удаляем историю
    log('market.db: очистка отключена (сохраняем историю)')
    return True
def heal_ml():
    p = os.path.join(BASE, 'data/ml_predictions_online.json')
    if not os.path.exists(p): return False
    try:
        d = json.load(open(p))
        bad = [s for s, v in d.get('predictions', {}).items() if v['proba_long'] < 0.05 or v['proba_long'] > 0.95]
        if bad:
            log(f'ML насыщена — переобучаем')
            subprocess.Popen(['python3','core/ml_online_simple.py'], cwd=BASE, stdout=open(os.path.join(BASE,'logs/ml_online.log'),'a'), stderr=subprocess.STDOUT)
            return True
    except: pass
    return False
def heal_rules():
    p = cfg.CONFIGS['rules']
    try: json.load(open(p)); return True
    except:
        import glob, shutil
        baks = sorted(glob.glob(p + '.bak.*'))
        if baks: shutil.copy(baks[-1], p); log('rules.json восстановлен'); return True
        return False
def main():
    log('=== SELF-HEAL ===')
    log(f"итог: tpsl={heal_tpsl_v4()} market={clean_stale_market()} ml={heal_ml()} rules={heal_rules()}")
if __name__ == '__main__': main()
