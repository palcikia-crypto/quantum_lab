#!/usr/bin/env python3
"""grail_optimizer.py — оптимизирует 16 GOLDEN через бэктесты и мутантов."""
import os, sys, json, sqlite3, time, subprocess
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.expanduser('~/quantum_lab'), 'core'))

BASE = os.path.expanduser('~/quantum_lab')
GRAILS = os.path.join(BASE, 'data/grails/16golden.json')
ACTIVE_V2 = os.path.join(BASE, 'data/okx_active.json')
ACTIVE_V3 = os.path.join(BASE, 'data/okx_active_v3.json')
MARKET = os.path.join(BASE, 'data/market.db')
LOG = os.path.join(BASE, 'logs/grail_optimizer.log')

# Параметры
TP = 0.006
SL = 0.004
TIMEOUT_BARS = 2
FEE = 0.001
DAYS = 90  # 90 дней (не 312 — чтобы не убивало OOM)

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] [grail] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def load_candles(sym, days=DAYS, tf='15m'):
    c = sqlite3.connect(MARKET, timeout=10)
    cutoff = int(time.time()) - days*86400
    rows = c.execute("""SELECT ts,o,h,l,c,v FROM candles
                        WHERE symbol=? AND tf=? AND ts>? ORDER BY ts""",
                     (sym, tf, cutoff)).fetchall()
    c.close()
    if not rows: return None
    return {k: __import__('numpy').array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def get_strategy_func(name):
    """Генерирует функцию стратегии по имени."""
    import re
    nums = [float(x) for x in re.findall(r'\d+\.?\d*', name)]
    
    if name.startswith('okx_vwap_rev_') and nums:
        from okx_mutator import okx_vwap_rev
        return okx_vwap_rev(int(nums[0]))
    if name.startswith('okx_grid_sma_') and nums:
        from okx_grid import okx_grid_sma
        return okx_grid_sma(int(nums[0]))
    if name.startswith('okx_ema_') and len(nums) >= 2:
        from okx_mutator import ema_cross
        return ema_cross(int(nums[0]), int(nums[1]))
    return None

def simulate(data, fn, tp=TP, sl=SL, timeout_bars=TIMEOUT_BARS):
    """Бэктест: считает WR, PnL, n."""
    import numpy as np
    o, h, l, c, v, ts = data['o'], data['h'], data['l'], data['c'], data['v'], data['ts']
    n = len(c)
    if n < 50: return None
    try:
        ind = {}
        up, dn = fn(o, h, l, c, v, ind)
    except Exception as e:
        return None
    wins = 0; losses = 0; total = 0; pnl = 0.0
    for i in range(30, n-1):
        if up[i]:
            ep = c[i]
            for j in range(i+1, min(i+1+timeout_bars, n)):
                move = (c[j] - ep) / ep
                if move >= tp: pnl += tp - 2*FEE; wins += 1; total += 1; break
                elif move <= -sl: pnl += -sl - 2*FEE; losses += 1; total += 1; break
            else:
                move = (c[min(i+timeout_bars, n-1)] - ep) / ep
                pnl += move - 2*FEE; total += 1
                if move > 0: wins += 1
                else: losses += 1
        elif dn[i]:
            ep = c[i]
            for j in range(i+1, min(i+1+timeout_bars, n)):
                move = (ep - c[j]) / ep
                if move >= tp: pnl += tp - 2*FEE; wins += 1; total += 1; break
                elif move <= -sl: pnl += -sl - 2*FEE; losses += 1; total += 1; break
            else:
                move = (ep - c[min(i+timeout_bars, n-1)]) / ep
                pnl += move - 2*FEE; total += 1
                if move > 0: wins += 1
                else: losses += 1
    if total == 0: return None
    return {'n': total, 'wins': wins, 'losses': losses,
            'wr': round(100*wins/total, 1), 'pnl': round(pnl, 2),
            'exp': round(pnl/total, 4)}

def optimize_grail(sym, strat_name, base_wr):
    """Оптимизирует 1 грааль: мутанты + бэктест."""
    log(f'🔍 {sym} {strat_name} (base WR={base_wr}%)')
    data = load_candles(sym)
    if not data:
        log(f'  ⚠️ нет данных'); return None
    
    # 1. Базовая стратегия
    fn = get_strategy_func(strat_name)
    if not fn:
        log(f'  ⚠️ стратегия не найдена'); return None
    
    base = simulate(data, fn)
    if not base:
        log(f'  ⚠️ бэктест не удался'); return None
    log(f'  base: WR={base["wr"]}% n={base["n"]} PnL={base["pnl"]}% exp={base["exp"]}')
    
    # 2. Мутанты (параметры вокруг базовой)
    import re
    nums = [float(x) for x in re.findall(r'\d+\.?\d*', strat_name)]
    results = [{'name': strat_name, **base}]
    
    if 'okx_vwap_rev' in strat_name and nums:
        period = int(nums[0])
        for p in [period-5, period-3, period-2, period+2, period+3, period+5]:
            if p < 5 or p > 60: continue
            try:
                from okx_mutator import okx_vwap_rev
                fn_m = okx_vwap_rev(p)
                r = simulate(data, fn_m)
                if r:
                    results.append({'name': f'okx_vwap_rev_{p}', **r})
                    log(f'  mut okx_vwap_rev_{p}: WR={r["wr"]}% n={r["n"]} PnL={r["pnl"]}%')
            except: pass
    
    if 'okx_grid_sma' in strat_name and nums:
        period = int(nums[0])
        for p in [period-5, period-3, period-2, period+2, period+3, period+5]:
            if p < 5 or p > 60: continue
            try:
                from okx_grid import okx_grid_sma
                fn_m = okx_grid_sma(p)
                r = simulate(data, fn_m)
                if r:
                    results.append({'name': f'okx_grid_sma_{p}', **r})
                    log(f'  mut okx_grid_sma_{p}: WR={r["wr"]}% n={r["n"]} PnL={r["pnl"]}%')
            except: pass
    
    # 3. Лучший по PnL (WR >= 55, n >= 30)
    valid = [r for r in results if r['wr'] >= 55 and r['n'] >= 30]
    if not valid:
        log(f'  ⚠️ нет мутантов с WR>=55'); return None
    
    best = max(valid, key=lambda x: x['pnl'])
    log(f'  ✅ BEST: {best["name"]} WR={best["wr"]}% n={best["n"]} PnL={best["pnl"]}%')
    return best

def main():
    log('=== GRAIL OPTIMIZER START ===')
    if not os.path.exists(GRAILS):
        log('❌ нет 16golden.json'); return
    
    d = json.load(open(GRAILS))
    pairs = d.get('pairs', {})
    log(f'Граалей: {len(pairs)}')
    
    new_pairs = {}
    for key, cfg in pairs.items():
        sym = cfg.get('symbol', '').replace('-', '')
        strat = cfg.get('strategy', '')
        base_wr = cfg.get('wr', 0)
        
        best = optimize_grail(sym, strat, base_wr)
        if best:
            new_pairs[key] = {
                'symbol': cfg.get('symbol'),
                'tf': cfg.get('tf', '15m'),
                'strategy': best['name'],
                'wr': best['wr'],
                'n': best['n'],
                'trade': True
            }
    
    if new_pairs:
        out = {'updated_at': datetime.now().isoformat(), 'source': 'grail_optimizer',
               'pairs': new_pairs}
        json.dump(out, open(ACTIVE_V2, 'w'), indent=2)
        json.dump(out, open(ACTIVE_V3, 'w'), indent=2)
        log(f'✅ {len(new_pairs)} граалей → okx_active.json, okx_active_v3.json')
    else:
        log('❌ нет результатов')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
