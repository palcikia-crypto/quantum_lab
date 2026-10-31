#!/usr/bin/env python3
"""sanity_check.py — проверка целостности ботов и стратегий."""
import os, sys, json, sqlite3, re
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/sanity_check.log')
ACTIVE = os.path.join(BASE, 'data/okx_active.json')
ACTIVE_V3 = os.path.join(BASE, 'data/okx_active_v3.json')
MARKET = os.path.join(BASE, 'data/market.db')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

errors = []
warnings = []

# 1. Конфиги — одинаковые пары
for f in [ACTIVE, ACTIVE_V3]:
    if not os.path.exists(f):
        errors.append(f'❌ {f} не существует')
        continue
    d = json.load(open(f))
    pairs = d.get('pairs', {})
    if len(pairs) == 0:
        errors.append(f'❌ {f}: 0 пар')
    for k, v in pairs.items():
        if not v.get('symbol') or not v.get('strategy'):
            errors.append(f'❌ {f}: {k} — нет symbol/strategy')
        if not v.get('tf'):
            warnings.append(f'⚠️ {f}: {k} — нет tf (по умолчанию 15m)')

# 2. Дубли символов (XRP×2 и т.д.)
from collections import Counter
d = json.load(open(ACTIVE))
symbols = [v['symbol'] for v in d.get('pairs', {}).values()]
dups = [s for s, c in Counter(symbols).items() if c > 1]
if dups:
    errors.append(f'❌ Дубли символов в {ACTIVE}: {dups}')

# 3. Данные в market.db
if not os.path.exists(MARKET):
    errors.append(f'❌ {MARKET} не существует')
else:
    c = sqlite3.connect(MARKET)
    for k, v in d.get('pairs', {}).items():
        sym = v['symbol'].replace('-', '')
        tf = v.get('tf', '15m')
        cnt = c.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND tf=?", (sym, tf)).fetchone()[0]
        if cnt < 100:
            errors.append(f'❌ {sym} {tf}: {cnt} свечей (< 100)')
        # свежесть
        age = c.execute("SELECT (strftime('%s','now') - MAX(ts)) FROM candles WHERE symbol=? AND tf=?", (sym, tf)).fetchone()[0]
        if age and age > 3600:
            warnings.append(f'⚠️ {sym} {tf}: последняя свеча {age} сек назад (> 1 часа)')
    c.close()

# 4. Проверка кода ботов — ключевые паттерны
bots = [
    'core/okx_bot_paper_v2.py',
    'core/okx_bot_paper_v3.py',
    'core/okx_bot_paper_v4.py',
]
for bot in bots:
    if not os.path.exists(bot):
        continue
    s = open(bot).read()
    # НЕТ get_candles (API) в close_open_trades
    if 'def close_open_trades' in s:
        # Проверка: get_candles_fresh (не get_candles)
        block = s.split('def close_open_trades')[1].split('def ')[0]
        if 'get_candles(' in block and 'get_candles_fresh' not in block:
            errors.append(f'❌ {bot}: close_open_trades использует get_candles (API) — должен get_candles_fresh (market.db)')
        # Проверка: TP/SL после entry_ts
        if "for j in range(len(data['h']))" in block and "data['ts'][j] < ets" not in block:
            errors.append(f'❌ {bot}: TP/SL проверяется по всем свечам (включая до входа)')
    # check_signal — не generate_mutants
    if 'def check_signal' in s:
        block = s.split('def check_signal')[1].split('def ')[0]
        if 'generate_mutants()' in block and 'okx_grid_sma_' not in block:
            errors.append(f'❌ {bot}: check_signal использует generate_mutants (нет okx_grid_sma_13/15/17)')
    # entry = c[-2] (look-ahead)
    if "entry = float(data['c'][-2])" in s:
        errors.append(f'❌ {bot}: entry = c[-2] (look-ahead) — должен c[-1]')

# 5. PnL — sanity
for db in ['data/okx_paper.db', 'data/okx_paper_v3.db', 'data/okx_paper_v4.db']:
    f = os.path.join(BASE, db)
    if not os.path.exists(f):
        continue
    c = sqlite3.connect(f)
    rows = c.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2) FROM trades WHERE status='CLOSED'").fetchone()
    log(f'  📊 {db}: {rows[0]} сделок, PnL={rows[1]}')
    c.close()

# 6. Открытые сделки — sanity
c = sqlite3.connect(os.path.join(BASE, 'data/okx_paper_v3.db'))
open_trades = c.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
c.close()
log(f'  📊 v3 открытых: {open_trades}')

# ИТОГ
print()
if errors:
    log('❌ ОШИБКИ:')
    for e in errors: log(f'  {e}')
else:
    log('✅ ОШИБОК НЕТ')
if warnings:
    log('⚠️ ПРЕДУПРЕЖДЕНИЯ:')
    for w in warnings: log(f'  {w}')
log(f'=== ИТОГ: {len(errors)} ошибок, {len(warnings)} предупреждений ===')
sys.exit(1 if errors else 0)
