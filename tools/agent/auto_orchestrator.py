#!/usr/bin/env python3
"""auto_orchestrator.py — сам контролирует backfill → evolution → strategy_bot."""
import os, sys, json, sqlite3, subprocess, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/orchestrator.log')
MARKET = os.path.join(BASE, 'data/market.db')
EVO = os.path.join(BASE, 'data/evolution.json')
PAIRS_312 = ['BTCUSDT', 'ETHUSDT', 'DOGEUSDT', 'XRPUSDT', 'SOLUSDT']

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] [orch] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def get_coverage():
    """Сколько дней у каждой пары (15m)."""
    c = sqlite3.connect(MARKET, timeout=10)
    rows = c.execute("""SELECT symbol, ROUND((MAX(ts)-MIN(ts))/86400.0,0)
                        FROM candles WHERE tf='15m' GROUP BY symbol""").fetchall()
    c.close()
    return dict(rows)

def check_backfill_done():
    cov = get_coverage()
    done = [s for s in PAIRS_312 if cov.get(s, 0) >= 300]
    return len(done) >= 4, cov  # хотя бы 4 из 5

def get_gold_count():
    try:
        d = json.load(open(EVO))
        return len([s for s in d.get('top', []) if s.get('wr', 0) >= 55 and s.get('n', 0) >= 100])
    except: return 0

def restart_evolution():
    log('🔄 перезапуск evolution.py')
    subprocess.run(['pkill', '-9', '-f', 'core/evolution.py'], capture_output=True)
    time.sleep(2)
    subprocess.Popen(['python3', '-u', 'core/evolution.py'], cwd=BASE,
                     stdout=open(os.path.join(BASE, 'logs/evolution.log'), 'a'),
                     stderr=subprocess.STDOUT)
    time.sleep(40)  # ждём завершения
    log(f'✅ evolution завершён, граалей: {get_gold_count()}')

def restart_strategy_bot():
    log('🔄 перезапуск strategy_bot')
    subprocess.run(['pkill', '-9', '-f', 'strategy_bot'], capture_output=True)
    time.sleep(2)
    subprocess.Popen(['python3', '-u', 'core/strategy_bot.py'], cwd=BASE,
                     stdout=open(os.path.join(BASE, 'logs/strategy_bot.log'), 'a'),
                     stderr=subprocess.STDOUT)
    log('✅ strategy_bot перезапущен')

def main():
    log('=== ORCHESTRATOR RUN ===')
    
    # 1. Backfill завершён?
    done, cov = check_backfill_done()
    pairs_ok = {s: d for s, d in cov.items() if s in PAIRS_312}
    log(f'backfill: {pairs_ok}')
    
    if not done:
        log('⏳ backfill ещё идёт — ждём')
        return
    
    # 2. Проверяем граали
    gold = get_gold_count()
    log(f'граалей сейчас: {gold}')
    
    # 3. Если данных много, а граалей мало — перезапускаем evolution
    if gold < 10:
        log('⚠️ граалей < 10 — перезапускаем evolution')
        restart_evolution()
        gold = get_gold_count()
        log(f'граалей после: {gold}')
    
    # 4. Если граалей >= 10 — перезапускаем strategy_bot
    if gold >= 10:
        log('✅ граалей >= 10 — перезапускаем strategy_bot')
        restart_strategy_bot()
    else:
        log('⚠️ граалей всё ещё < 10 — ждём следующего запуска')
    
    log('=== DONE ===')

if __name__ == '__main__':
    main()
