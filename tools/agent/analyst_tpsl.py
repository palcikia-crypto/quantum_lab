#!/usr/bin/env python3
"""analyst_tpsl.py — форвард-тест TP/SL на реальных сделках Strategy Bot."""
import os, json, sqlite3, itertools
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/strategy_paper.db')
CFG = os.path.join(BASE, 'data/strategy_tpsl.json')
LOG = os.path.join(BASE, 'logs/analyst_tpsl.log')

FEE = 0.001  # 0.1% за круг

# Сетка TP/SL — 20+ вариантов
TP_GRID = [0.0010, 0.0015, 0.0020, 0.0025, 0.0030, 0.0040, 0.0050]
SL_GRID = [0.0005, 0.00075, 0.0010, 0.0015, 0.0020]

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def get_trades(n=200):
    c = sqlite3.connect(DB, timeout=10)
    rows = c.execute("""SELECT symbol, side, entry_price, exit_price, pnl,
                               entry_ts, exit_ts, tp, sl
                        FROM trades WHERE status='CLOSED'
                        ORDER BY exit_ts DESC LIMIT ?""", (n,)).fetchall()
    c.close()
    return rows

def simulate(trades, tp, sl):
    wins = 0; losses = 0; neutral = 0; pnl = 0.0
    for t in trades:
        sym, side, ep, xp, pnl_real, ets, xts, tp_old, sl_old = t
        if not ep or not xp: continue
        move = (xp - ep) / ep if side == 'LONG' else (ep - xp) / ep
        if move >= tp:
            r = tp - 2*FEE; wins += 1
        elif move <= -sl:
            r = -sl - 2*FEE; losses += 1
        else:
            r = move - 2*FEE; neutral += 1
        pnl += r * 100
    total = wins + losses + neutral
    if total == 0: return None
    return {'tp': tp, 'sl': sl, 'n': total, 'wins': wins, 'losses': losses,
            'neutral': neutral, 'wr': round(100*wins/total, 1), 'pnl': round(pnl, 2)}

def main():
    log('=== ANALYST TPSL ===')
    trades = get_trades(200)
    log(f'сделок: {len(trades)}')
    if len(trades) < 5:
        log('⚠️ мало сделок (<5) — не оптимизируем')
        return
    results = []
    for tp, sl in itertools.product(TP_GRID, SL_GRID):
        r = simulate(trades, tp, sl)
        if r:
            results.append(r)
    if not results:
        log('❌ нет результатов'); return
    
    # Фильтруем: WR >= 40 и n >= 10
    valid = [r for r in results if r['wr'] >= 40 and r['n'] >= 10]
    if not valid:
        log('⚠️ нет TP/SL с WR>=40 — не меняем')
        return
    
    # Сортируем по PnL (лучший первый)
    valid.sort(key=lambda x: x['pnl'], reverse=True)
    
    # Логируем топ-10
    log(f'\nТОП-10 TP/SL по PnL (WR>=40):')
    for r in valid[:10]:
        log(f"  TP={r['tp']*100:.2f}% SL={r['sl']*100:.2f}%: W={r['wins']} L={r['losses']} N={r['neutral']} WR={r['wr']}% PnL={r['pnl']:+.2f}%")
    
    # Лучший — первый
    best = valid[0]
    log(f"\n✅ ЛУЧШИЙ: TP={best['tp']*100:.2f}% SL={best['sl']*100:.2f}%")
    log(f"   WR={best['wr']}% PnL={best['pnl']:+.2f}% (n={best['n']})")
    
    # Записываем в конфиг
    cfg = {
        'tp': best['tp'], 'sl': best['sl'],
        'wr': best['wr'], 'pnl': best['pnl'],
        'n': best['n'],
        'updated_at': datetime.now().isoformat(),
        'source': 'analyst_tpsl'
    }
    json.dump(cfg, open(CFG, 'w'), indent=2)
    log(f"✅ записано в {CFG}")
    log('=== DONE ===')

if __name__ == '__main__':
    main()
