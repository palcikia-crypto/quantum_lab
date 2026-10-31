#!/usr/bin/env python3
"""strategy_mutator.py — мутирует параметры стратегий (stoch, mean_rev, rsi, ema, bb)."""
import numpy as np

def mutate_stoch(period=20, lo=20, hi=80):
    def strat(o,h,l,c,v, ind):
        n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
        if n < period: return up, dn
        for i in range(period, n):
            lo_p = min(l[i-period+1:i+1]); hi_p = max(h[i-period+1:i+1])
            if hi_p == lo_p: continue
            k = 100 * (c[i] - lo_p) / (hi_p - lo_p)
            if k < lo: up[i] = True
            elif k > hi: dn[i] = True
        return up, dn
    strat.__name__ = f"stoch_{period}_{lo}_{hi}"
    return strat

def mutate_mean_rev(period=20, threshold=2.0):
    def strat(o,h,l,c,v, ind):
        n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
        if n < period: return up, dn
        sma = np.convolve(c, np.ones(period)/period, 'same')
        std = np.array([np.std(c[max(0,i-period+1):i+1]) for i in range(n)])
        for i in range(period, n):
            if std[i] == 0: continue
            z = (c[i] - sma[i]) / std[i]
            if z < -threshold: up[i] = True
            elif z > threshold: dn[i] = True
        return up, dn
    strat.__name__ = f"mean_rev_{period}_{threshold}"
    return strat

def mutate_rsi(period=14, lo=30, hi=70):
    def strat(o,h,l,c,v, ind):
        n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
        if n < period+1: return up, dn
        delta = np.diff(c, prepend=c[0])
        gain = np.where(delta > 0, delta, 0); loss = np.where(delta < 0, -delta, 0)
        ag = np.convolve(gain, np.ones(period)/period, 'same')
        al = np.convolve(loss, np.ones(period)/period, 'same')
        rs = ag / np.maximum(al, 1e-9); rsi = 100 - 100/(1+rs)
        for i in range(period, n):
            if rsi[i] < lo: up[i] = True
            elif rsi[i] > hi: dn[i] = True
        return up, dn
    strat.__name__ = f"rsi_{period}_{lo}_{hi}"
    return strat

def mutate_ema(fast=9, slow=21):
    def strat(o,h,l,c,v, ind):
        n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
        if n < slow+1: return up, dn
        ema_f = np.convolve(c, np.ones(fast)/fast, 'same')
        ema_s = np.convolve(c, np.ones(slow)/slow, 'same')
        for i in range(slow, n):
            if ema_f[i] > ema_s[i] and ema_f[i-1] <= ema_s[i-1]: up[i] = True
            elif ema_f[i] < ema_s[i] and ema_f[i-1] >= ema_s[i-1]: dn[i] = True
        return up, dn
    strat.__name__ = f"ema_{fast}_{slow}"
    return strat

def mutate_bb(period=20, k=2.0):
    def strat(o,h,l,c,v, ind):
        n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
        if n < period: return up, dn
        sma = np.convolve(c, np.ones(period)/period, 'same')
        std = np.array([np.std(c[max(0,i-period+1):i+1]) for i in range(n)])
        for i in range(period, n):
            upper = sma[i] + k*std[i]; lower = sma[i] - k*std[i]
            if c[i] < lower: up[i] = True
            elif c[i] > upper: dn[i] = True
        return up, dn
    strat.__name__ = f"bb_{period}_{k}"
    return strat

def generate_mutations(max_mutants=40):
    mutants = {}
    # stoch: 3 периода × 3 порога = 9
    for p in [14, 20, 30]:
        for lo, hi in [(15,85), (20,80), (25,75)]:
            mutants[f"stoch_{p}_{lo}_{hi}"] = mutate_stoch(p, lo, hi)
            if len(mutants) >= max_mutants: return mutants
    # mean_rev: 3 периода × 3 порога = 9
    for p in [15, 20, 30]:
        for th in [1.5, 2.0, 2.5]:
            mutants[f"mean_rev_{p}_{th}"] = mutate_mean_rev(p, th)
            if len(mutants) >= max_mutants: return mutants
    # rsi: 2 периода × 3 пары порогов = 6
    for p in [7, 14]:
        for lo, hi in [(20,80), (30,70), (25,75)]:
            mutants[f"rsi_{p}_{lo}_{hi}"] = mutate_rsi(p, lo, hi)
            if len(mutants) >= max_mutants: return mutants
    # ema: 4 пары = 4
    for fast, slow in [(5,20), (9,21), (10,30), (12,26)]:
        mutants[f"ema_{fast}_{slow}"] = mutate_ema(fast, slow)
        if len(mutants) >= max_mutants: return mutants
    # bb: 3 периода × 3 k = 9
    for p in [15, 20, 30]:
        for k in [1.5, 2.0, 2.5]:
            mutants[f"bb_{p}_{k}"] = mutate_bb(p, k)
            if len(mutants) >= max_mutants: return mutants
    return mutants
