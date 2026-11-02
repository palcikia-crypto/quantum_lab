#!/usr/bin/env python3
"""auto_data.py — автодокачка данных (market.db, oracle.db, orderbook.db)."""
import os, json, sqlite3, time, subprocess
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/auto_data.log'), 'a') as f:
        f.write(line + '\n')

def check_freshness(db, table, max_age_sec):
    try:
        c = sqlite3.connect(db, timeout=5)
        r = c.execute(f"SELECT MAX(ts) FROM {table}").fetchone()
        c.close()
        if r and r[0]:
            age = int(time.time()) - r[0]
            return age < max_age_sec, age
    except:
        pass
    return False, 999999

def run_script(script):
    subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE, 'core', script)],
                    stdout=open(os.path.join(BASE, f'logs/{script.replace(".py","")}.log'),'a'),
                    stderr=subprocess.STDOUT, start_new_session=True)
    log(f'  запущен {script}')

def main():
    log('=== AUTO DATA ===')

    fresh, age = check_freshness(os.path.join(BASE, 'data/market.db'), 'candles', 2*3600)
    if not fresh:
        log(f'market.db устарел ({age//60} мин) → data_manager')
        run_script('data_manager.py')
    else:
        log(f'market.db свежий ({age//60} мин)')

    fresh, age = check_freshness(os.path.join(BASE, 'data/oracle.db'), 'regime', 300)
    if not fresh:
        log(f'oracle.db устарел ({age} сек) → перезапуск oracle')
        subprocess.run(['pkill','-f','core/oracle.py'], capture_output=True)
        time.sleep(1)
        subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/oracle.py'),'loop'],
                        stdout=open(os.path.join(BASE,'logs/oracle.log'),'a'),
                        stderr=subprocess.STDOUT, start_new_session=True)
        log('  oracle перезапущен')
    else:
        log(f'oracle.db свежий ({age} сек)')

    fresh, age = check_freshness(os.path.join(BASE, 'data/orderbook.db'), 'orderbooks', 120)
    if not fresh:
        log(f'orderbook.db устарел ({age} сек) → перезапуск orderbook_oracle')
        subprocess.run(['pkill','-f','orderbook_oracle'], capture_output=True)
        time.sleep(1)
        subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/orderbook_oracle.py')],
                        stdout=open(os.path.join(BASE,'logs/orderbook_oracle.log'),'a'),
                        stderr=subprocess.STDOUT, start_new_session=True)
        log('  orderbook_oracle перезапущен')
    else:
        log(f'orderbook.db свежий ({age} сек)')

    log('=== AUTO DATA DONE ===')

if __name__ == '__main__':
    main()
