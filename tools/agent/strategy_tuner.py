#!/usr/bin/env python3
"""strategy_tuner.py — оптимизирует TP/SL для Strategy Bot по live-сделкам."""
import os, json, sqlite3, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/strategy_paper.db')
CFG = os.path.join(BASE, 'data/strategy_tpsl.json')
LOG = os.path.join(BASE, 'logs/strategy_tuner.log')

# Сетка TP/SL: от узких (быстрых) до широких (медленных)
GRID = [
    (0.0010, 0.0005),  # 0.10% / 0.05%
    (0.0015, 0.00075), # 0.15% / 0.075% (текущий)
    (0.0020, 0.0010),  # 0.20% / 0.10%
    (0.0025, 0.0010),  # 0.25% / 0.10%
    (0.0030, 0.0010),  # 0.30% / 0.10%
    (0.0030, 0.00075), # 0.30% / 0.075%
    (0.0040, 0.0010),  # 0.40% / 0.10%
]
FEE = 0.001  # 0.1%

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def get_trades(n=100):
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
    log('=== STRATEGY TUNER ===')
    trades = get_trades(100)
    log(f'сделок: {len(trades)}')
    if len(trades) < 10:
        log('⚠️ мало сделок (<10) — не оптимизируем')
        return
    results = []
    for tp, sl in GRID:
        r = simulate(trades, tp, sl)
        if r:
            results.append(r)
            log(f"  TP={tp*100:.2f}% SL={sl*100:.2f}%: W={r['wins']} L={r['losses']} N={r['neutral']} WR={r['wr']}% PnL={r['pnl']:+.2f}%")
    if not results:
        log('❌ нет результатов'); return
    # Лучший по PnL, но с учётом: WR >= 45% и n >= 10
    valid = [r for r in results if r['wr'] >= 45 and r['n'] >= 10]
    if not valid:
        log('⚠️ нет TP/SL с WR>=45 — не меняем')
        return
    best = max(valid, key=lambda x: x['pnl'])
    log(f"✅ ЛУЧШИЙ: TP={best['tp']*100:.2f}% SL={best['sl']*100:.2f}% PnL={best['pnl']:+.2f}% WR={best['wr']}%")
    # Записываем в конфиг
    cfg = {'tp': best['tp'], 'sl': best['sl'], 'wr': best['wr'],
           'pnl': best['pnl'], 'updated_at': datetime.now().isoformat(),
           'source': 'strategy_tuner'}
    json.dump(cfg, open(CFG, 'w'), indent=2)
    log(f"✅ записано в {CFG}")
    log('=== DONE ===')

if __name__ == '__main__':
    main()
