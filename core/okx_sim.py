#!/usr/bin/env python3
"""okx_sim.py — правильная симуляция: стоп/тейк, проскальзывание, комиссия."""
import numpy as np

def simulate_scalp(up, dn, o, h, l, c, sl_pct=0.003, tp_pct=0.005, fee=0.001, slip=0.0002, max_bars=10):
    trades = []
    n = len(c)
    for i in range(20, n-1):
        if not (up[i] or dn[i]):
            continue
        side = 'LONG' if up[i] else 'SHORT'
        entry = o[i+1] * (1 + slip if side == 'LONG' else 1 - slip)
        sl = entry * (1 - sl_pct if side == 'LONG' else 1 + sl_pct)
        tp = entry * (1 + tp_pct if side == 'LONG' else 1 - tp_pct)
        exit_p = None
        for j in range(i+1, min(i+1+max_bars, n)):
            if side == 'LONG':
                if l[j] <= sl: exit_p = sl; break
                if h[j] >= tp: exit_p = tp; break
            else:
                if h[j] >= sl: exit_p = sl; break
                if l[j] <= tp: exit_p = tp; break
        if exit_p is None:
            exit_p = c[min(i+max_bars, n-1)]
        pnl = (exit_p - entry) / entry if side == 'LONG' else (entry - exit_p) / entry
        pnl -= fee * 2
        trades.append(pnl)
    return trades

def check_l1(pnls):
    n = len(pnls)
    if n < 30: return {'wr': 0, 'n': n, 'pass': False, 'pf': 0}
    wins = sum(1 for p in pnls if p > 0)
    wr = 100 * wins / n
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    pf = gross_win / gross_loss if gross_loss > 0 else 999
    return {'wr': round(wr,1), 'n': n, 'pf': round(pf,2), 'pass': wr >= 52 and n >= 30 and pf >= 1.2}

if __name__ == '__main__':
    print('✅ okx_sim: готов')
