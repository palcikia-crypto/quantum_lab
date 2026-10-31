#!/usr/bin/env python3
"""Тестовый тюнер: сравнивает TP/SL С УЧЁТОМ таймаута. НЕ трогает конфиг v4."""
import os, json, sqlite3
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB_V4 = os.path.join(BASE, 'data/okx_paper_v4.db')
LOG = os.path.join(BASE, 'logs/tpsl_test.log')

# Сетка TP/SL: от узких (текущих) до широких
GRID = [
    (0.0010, 0.0005),  # 0.10% / 0.05%
    (0.0015, 0.00075), # 0.15% / 0.07% (текущий)
    (0.0020, 0.0010),  # 0.20% / 0.10%
    (0.0030, 0.0015),  # 0.30% / 0.15%
    (0.0040, 0.0020),  # 0.40% / 0.20%
    (0.0050, 0.0025),  # 0.50% / 0.25%
    (0.0060, 0.0030),  # 0.60% / 0.30%
]
TIMEOUT = 60
FEE = 0.0005  # 0.05% за сторону

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def get_trades(n=200):
    c = sqlite3.connect(DB_V4, timeout=10)
    rows = c.execute("""SELECT symbol, side, entry_price, exit_price, pnl,
                               entry_ts, exit_ts, tp, sl
                        FROM trades WHERE status='CLOSED'
                        ORDER BY exit_ts DESC LIMIT ?""", (n,)).fetchall()
    c.close()
    return rows

def simulate(trades, new_tp, new_sl):
    """Симуляция: для каждой сделки пересчитываем PnL с учётом таймаута."""
    n = len(trades)
    wins = 0
    losses = 0
    neutral = 0
    pnl = 0.0
    for t in trades:
        sym, side, ep, xp, pnl_real, ets, xts, tp_old, sl_old = t
        if ep is None or ep == 0: continue
        # берём реальную цену выхода (xp) — она уже после таймаута
        if xp is None or xp == 0: continue
        move = (xp - ep) / ep if side == 'LONG' else (ep - xp) / ep
        # проверяем: дошло ли до нового TP или SL
        if move >= new_tp:
            r = new_tp - 2*FEE  # win
            wins += 1
        elif move <= -new_sl:
            r = -new_sl - 2*FEE  # loss
            losses += 1
        else:
            # таймаут: цена между TP и SL — берём реальный move
            r = move - 2*FEE
            neutral += 1
        pnl += r * 100  # в %
    total = wins + losses + neutral
    if total == 0: return None
    return {
        'tp': new_tp, 'sl': new_sl,
        'n': total, 'wins': wins, 'losses': losses, 'neutral': neutral,
        'wr': round(100*wins/total, 1),
        'pnl': round(pnl, 2),
    }

def main():
    log('=== TPSL TEST (с таймаутом) ===')
    trades = get_trades(200)
    log(f'сделок: {len(trades)}')
    if not trades:
        log('❌ нет сделок'); return
    results = []
    for tp, sl in GRID:
        r = simulate(trades, tp, sl)
        if r:
            results.append(r)
            log(f"  TP={tp*100:.2f}% SL={sl*100:.2f}%: n={r['n']} W={r['wins']} L={r['losses']} N={r['neutral']} WR={r['wr']}% PnL={r['pnl']:+.2f}%")
    # лучший по PnL
    if results:
        best = max(results, key=lambda x: x['pnl'])
        log(f"✅ ЛУЧШИЙ: TP={best['tp']*100:.2f}% SL={best['sl']*100:.2f}% PnL={best['pnl']:+.2f}%")
        # сравнение с текущим
        cur = next((r for r in results if abs(r['tp']-0.0015)<1e-6 and abs(r['sl']-0.00075)<1e-6), None)
        if cur:
            log(f"📊 ТЕКУЩИЙ (0.15%/0.07%): PnL={cur['pnl']:+.2f}%")
            diff = best['pnl'] - cur['pnl']
            log(f"📊 РАЗНИЦА: {diff:+.2f}% ({'✅ лучше' if diff>0 else '❌ хуже'})")
    log('=== DONE ===')

if __name__ == '__main__':
    main()
