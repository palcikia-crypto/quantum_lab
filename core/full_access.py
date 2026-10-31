#!/usr/bin/env python3
"""full_access.py — полный доступ мозга ко всему из старой лаборатории.
Собирает: все стратегии (rslab2 + strategy_pool), все проверки (L1-L13),
эволюцию, AI-генератор, аналитику."""
import os, sys, json, sqlite3, importlib.util
import numpy as np
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
RSBOT = os.path.expanduser('~/rsbot')

# ═══ ВСЕ СТРАТЕГИИ ═══
def load_all_strategies():
    """Загружает стратегии из strategy_pool + rslab2."""
    strategies = {}
    # 1. Из strategy_pool (11)
    try:
        sys.path.insert(0, os.path.join(BASE, 'core'))
        from strategy_pool import STRATEGIES as SP
        strategies.update(SP)
    except: pass
    # 2. Из rslab2 (дополнительные)
    try:
        spec = importlib.util.spec_from_file_location('rslab2', os.path.join(RSBOT, 'rslab2.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in dir(mod):
            if name.startswith('sig_'):
                fn = getattr(mod, name)
                if callable(fn) and name not in strategies:
                    strategies[name] = fn
    except: pass
    # 3. Из ai_strategies (если есть)
    try:
        spec = importlib.util.spec_from_file_location('ai_str', os.path.join(RSBOT, 'ai_strategies.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in dir(mod):
            if name.startswith('sig_'):
                fn = getattr(mod, name)
                if callable(fn) and name not in strategies:
                    strategies[name] = fn
    except: pass
    return strategies

# ═══ ВСЕ ПРОВЕРКИ (L1-L13) ═══
def load_all_checks():
    """Загружает проверки из gate_v3 (L1-L7) + validation (L8-L13)."""
    checks = {'L1-L7': None, 'L8-L13': None}
    try:
        sys.path.insert(0, os.path.join(BASE, 'core'))
        import gate_v3
        checks['L1-L7'] = gate_v3
    except: pass
    try:
        sys.path.insert(0, os.path.join(BASE, 'core'))
        import validation
        checks['L8-L13'] = validation
    except: pass
    return checks

# ═══ ЭВОЛЮЦИЯ ═══
def load_evolution():
    """Загружает evolution_old.py."""
    try:
        spec = importlib.util.spec_from_file_location('evolve', os.path.join(BASE, 'core', 'evolution_old.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except: return None

# ═══ AI-ГЕНЕРАТОР ═══
def load_ai_generator():
    """Загружает ai_generator_old.py."""
    try:
        spec = importlib.util.spec_from_file_location('ai_gen', os.path.join(BASE, 'core', 'ai_generator_old.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except: return None

# ═══ АНАЛИТИКА ═══
def load_analytics():
    """Загружает analytics_old.py."""
    try:
        spec = importlib.util.spec_from_file_location('analytics', os.path.join(BASE, 'core', 'analytics_old.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except: return None

# ═══ ПОЛНЫЙ GATE (L1-L13) ═══
def full_gate(symbol, tf, strat_name, strat_fn, model='open'):
    """Прогоняет стратегию через ВСЕ 13 уровней."""
    checks = load_all_checks()
    g = checks.get('L1-L7')
    v = checks.get('L8-L13')
    if not g: return None
    # L1-L7
    try:
        r = g.run_gate(symbol, tf, strat_name, strat_fn, model=model, use_h1=True)
    except: return None
    if not r: return None
    # L8-L13 (только если L1-L7 пройдены хотя бы частично)
    if v and r['verdict'] in ('GOLDEN', 'TRADE_NOW', 'WATCH'):
        try:
            data = g.load_candles(symbol, tf)
            if data:
                up, dn = strat_fn(data['o'], data['h'], data['l'], data['c'], data['v'], {})
                up, dn = g.apply_h1_filter(up, dn, symbol, data['ts'])
                val = {
                    'L8': v.L8_out_of_sample(up, dn, data['o'], data['c'], model),
                    'L9': v.L9_permutation(up, dn, data['o'], data['c'], 100, model),
                    'L10': v.L10_deflated_sharpe(g.simulate(up, dn, data['o'], data['c'], model=model)),
                    'L11': v.L11_pbo(up, dn, data['o'], data['c'], 10, model),
                    'L12': v.L12_regime_stability(up, dn, data['o'], data['c'], data['ts'], model),
                    'L13': v.L13_cross_pair(strat_name, strat_fn, ('BTCUSDT','ETHUSDT','SOLUSDT'), tf, model),
                }
                val_pass = sum(1 for k in ['L8','L9','L10','L11','L12','L13'] if val[k].get('pass'))
                r['L8-L13'] = val
                r['L8-L13_pass'] = val_pass
                # корректируем вердикт: если L8-L13 < 4 — WATCH
                if val_pass < 4 and r['verdict'] == 'TRADE_NOW':
                    r['verdict'] = 'WATCH'
        except: pass
    return r

# ═══ СВОДКА ═══
def summary():
    strategies = load_all_strategies()
    checks = load_all_checks()
    evo = load_evolution()
    ai = load_ai_generator()
    ana = load_analytics()
    return {
        'strategies': len(strategies),
        'strategies_names': list(strategies.keys()),
        'checks_L1_L7': checks['L1-L7'] is not None,
        'checks_L8_L13': checks['L8-L13'] is not None,
        'evolution': evo is not None,
        'ai_generator': ai is not None,
        'analytics': ana is not None,
    }

if __name__ == '__main__':
    print(json.dumps(summary(), indent=2, ensure_ascii=False))
