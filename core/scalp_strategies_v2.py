#!/usr/bin/env python3
"""scalp_strategies_v2.py — 20+ скальпинг-стратегий (OBI, pressure, VWAP, funding)."""

def make_obi_thresh(thresh, direction):
    """OBI порог: direction='long' (obi > thresh) или 'short' (obi < -thresh)."""
    def fn(obi, pressure, spread, price, vwap, funding):
        if obi is None: return None
        if direction == 'long' and obi > thresh: return 'LONG'
        if direction == 'short' and obi < -thresh: return 'SHORT'
        return None
    return fn

def make_pressure_thresh(thresh, direction):
    def fn(obi, pressure, spread, price, vwap, funding):
        if pressure is None: return None
        if direction == 'long' and pressure > thresh: return 'LONG'
        if direction == 'short' and pressure < -thresh: return 'SHORT'
        return None
    return fn

def scalp_obi_pressure(obi, pressure, spread, price, vwap, funding):
    if obi is None or pressure is None: return None
    if obi > 0.3 and pressure > 500: return 'LONG'
    if obi < -0.3 and pressure < -500: return 'SHORT'
    return None

def scalp_obi_vwap(obi, pressure, spread, price, vwap, funding):
    if obi is None or vwap is None or vwap == 0: return None
    if obi > 0.3 and price < vwap: return 'LONG'
    if obi < -0.3 and price > vwap: return 'SHORT'
    return None

def scalp_triple(obi, pressure, spread, price, vwap, funding):
    if obi is None or pressure is None or vwap is None: return None
    if obi > 0.3 and pressure > 500 and price < vwap: return 'LONG'
    if obi < -0.3 and pressure < -500 and price > vwap: return 'SHORT'
    return None

def scalp_quad(obi, pressure, spread, price, vwap, funding):
    if obi is None or pressure is None or vwap is None or funding is None: return None
    if obi > 0.3 and pressure > 500 and price < vwap and funding < 0.0001: return 'LONG'
    if obi < -0.3 and pressure < -500 and price > vwap and funding > 0.00005: return 'SHORT'
    return None

def scalp_obi_funding(obi, pressure, spread, price, vwap, funding):
    if obi is None or funding is None: return None
    if obi > 0.3 and funding < 0.0001: return 'LONG'
    if obi < -0.3 and funding > 0.00005: return 'SHORT'
    return None

def scalp_vwap_only(obi, pressure, spread, price, vwap, funding):
    if vwap is None or vwap == 0: return None
    if price < vwap * 0.999: return 'LONG'  # откат вниз
    if price > vwap * 1.001: return 'SHORT'
    return None

# Реестр: 20+ стратегий
SCALP_STRATEGIES_V2 = {}

# OBI пороги
for t in [0.2, 0.3, 0.4, 0.5, 0.6]:
    SCALP_STRATEGIES_V2[f'obi_long_{t}'] = make_obi_thresh(t, 'long')
    SCALP_STRATEGIES_V2[f'obi_short_{t}'] = make_obi_thresh(t, 'short')

# Pressure пороги
for t in [500, 1000, 2000, 5000]:
    SCALP_STRATEGIES_V2[f'pressure_long_{t}'] = make_pressure_thresh(t, 'long')
    SCALP_STRATEGIES_V2[f'pressure_short_{t}'] = make_pressure_thresh(-t, 'short')

# Комбинации
SCALP_STRATEGIES_V2['obi_pressure'] = scalp_obi_pressure
SCALP_STRATEGIES_V2['obi_vwap'] = scalp_obi_vwap
SCALP_STRATEGIES_V2['triple'] = scalp_triple
SCALP_STRATEGIES_V2['quad'] = scalp_quad
SCALP_STRATEGIES_V2['obi_funding'] = scalp_obi_funding
SCALP_STRATEGIES_V2['vwap_only'] = scalp_vwap_only
