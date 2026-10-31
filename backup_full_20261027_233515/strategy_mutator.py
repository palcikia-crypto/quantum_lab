#!/usr/bin/env python3
"""strategy_mutator.py — мутирует параметры стратегий."""
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

def generate_mutations(max_mutants=10):
    mutants = {}
    for p in [14, 20, 30]:
        for lo, hi in [(15,85), (20,80), (25,75)]:
            mutants[f"stoch_{p}_{lo}_{hi}"] = mutate_stoch(p, lo, hi)
            if len(mutants) >= max_mutants: return mutants
    for p in [20, 30]:
        for th in [1.5, 2.0, 2.5]:
            mutants[f"mean_rev_{p}_{th}"] = mutate_mean_rev(p, th)
            if len(mutants) >= max_mutants: return mutants
    return mutants
