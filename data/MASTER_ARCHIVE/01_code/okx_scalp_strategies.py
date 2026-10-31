#!/usr/bin/env python3
"""okx_scalp_strategies.py — 7 скальпинг-стратегий по OBI / pressure / VWAP.
Каждая функция: (obi, pressure, spread, price, vwap_1m) -> 'LONG' / 'SHORT' / None."""

def scalp_obi_long(obi, pressure, spread, price, vwap_1m):
    if obi is None: return None
    if obi > 0.4: return 'LONG'
    return None

def scalp_obi_short(obi, pressure, spread, price, vwap_1m):
    if obi is None: return None
    if obi < -0.4: return 'SHORT'
    return None

def scalp_obi_spread(obi, pressure, spread, price, vwap_1m):
    if obi is None or spread is None: return None
    if spread > 0.0005: return None  # spread > 0.05%
    if obi > 0.4: return 'LONG'
    if obi < -0.4: return 'SHORT'
    return None

def scalp_obi_pressure(obi, pressure, spread, price, vwap_1m):
    if obi is None or pressure is None: return None
    if obi > 0.3 and pressure > 0: return 'LONG'
    if obi < -0.3 and pressure < 0: return 'SHORT'
    return None

def scalp_obi_vwap(obi, pressure, spread, price, vwap_1m):
    if obi is None or vwap_1m is None or vwap_1m == 0: return None
    if obi > 0.3 and price < vwap_1m: return 'LONG'  # откат от VWAP
    if obi < -0.3 and price > vwap_1m: return 'SHORT'
    return None

def scalp_pressure_only(obi, pressure, spread, price, vwap_1m):
    if pressure is None: return None
    if pressure > 500: return 'LONG'  # порог (подбирается)
    if pressure < -500: return 'SHORT'
    return None

def scalp_triple(obi, pressure, spread, price, vwap_1m):
    if obi is None or pressure is None or vwap_1m is None or vwap_1m == 0:
        return None
    if obi > 0.3 and pressure > 0 and price < vwap_1m: return 'LONG'
    if obi < -0.3 and pressure < 0 and price > vwap_1m: return 'SHORT'
    return None

# Реестр
SCALP_STRATEGIES = {
    'scalp_obi_long':     scalp_obi_long,
    'scalp_obi_short':    scalp_obi_short,
    'scalp_obi_spread':   scalp_obi_spread,
    'scalp_obi_pressure': scalp_obi_pressure,
    'scalp_obi_vwap':     scalp_obi_vwap,
    'scalp_pressure_only': scalp_pressure_only,
    'scalp_triple':       scalp_triple,
}
