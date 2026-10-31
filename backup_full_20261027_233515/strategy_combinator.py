#!/usr/bin/env python3
"""strategy_combinator.py — генерирует новые стратегии как комбинации существующих."""
import numpy as np

def combine_and(fn_a, fn_b):
    """A AND B: сигнал только если обе согласны."""
    def strat(o,h,l,c,v, ind):
        up_a, dn_a = fn_a(o,h,l,c,v, ind)
        up_b, dn_b = fn_b(o,h,l,c,v, ind)
        return up_a & up_b, dn_a & dn_b
    strat.__name__ = f"{fn_a.__name__}_AND_{fn_b.__name__}"
    return strat

def combine_or(fn_a, fn_b):
    """A OR B: сигнал если хотя бы одна."""
    def strat(o,h,l,c,v, ind):
        up_a, dn_a = fn_a(o,h,l,c,v, ind)
        up_b, dn_b = fn_b(o,h,l,c,v, ind)
        return up_a | up_b, dn_a | dn_b
    strat.__name__ = f"{fn_a.__name__}_OR_{fn_b.__name__}"
    return strat

def combine_filter(fn_a, fn_filter):
    """A + фильтр B: сигнал A, но только если B не даёт противоположный."""
    def strat(o,h,l,c,v, ind):
        up_a, dn_a = fn_a(o,h,l,c,v, ind)
        up_f, dn_f = fn_filter(o,h,l,c,v, ind)
        return up_a & ~dn_f, dn_a & ~up_f
    strat.__name__ = f"{fn_a.__name__}_FILTER_{fn_filter.__name__}"
    return strat

def generate_combinations(base_strategies, max_combos=30):
    """Генерирует комбинации из базовых стратегий."""
    names = list(base_strategies.keys())
    combos = {}
    for i, a in enumerate(names):
        for b in names[i+1:]:
            if len(combos) >= max_combos: break
            fn_a = base_strategies[a]; fn_b = base_strategies[b]
            # AND
            combos[f"{a}_AND_{b}"] = combine_and(fn_a, fn_b)
            if len(combos) >= max_combos: break
            # OR
            combos[f"{a}_OR_{b}"] = combine_or(fn_a, fn_b)
            if len(combos) >= max_combos: break
            # FILTER
            combos[f"{a}_FILTER_{b}"] = combine_filter(fn_a, fn_b)
    return combos
