#!/usr/bin/env python3
"""genetic.py — скрещивает лучших мутантов."""
import numpy as np, re

def parse_params(name):
    return [float(n) for n in re.findall(r'\d+\.?\d*', name)]

def mutate_mean_rev(period, threshold):
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

def mutate_stoch(period, lo, hi):
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

def crossover(name_a, name_b):
    pa = parse_params(name_a); pb = parse_params(name_b)
    if len(pa) != len(pb) or not pa: return None
    child = [(a+b)/2 for a,b in zip(pa, pb)]
    if 'mean_rev' in name_a:
        return mutate_mean_rev(int(child[0]), child[1])
    elif 'stoch' in name_a:
        return mutate_stoch(int(child[0]), child[1], child[2])
    return None

def generate_hybrids(best_names, max_hybrids=10):
    hybrids = {}
    for i, a in enumerate(best_names):
        for b in best_names[i+1:]:
            if len(hybrids) >= max_hybrids: break
            h = crossover(a, b)
            if h: hybrids[h.__name__] = h
    return hybrids
