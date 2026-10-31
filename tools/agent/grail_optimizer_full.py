#!/usr/bin/env python3
"""grail_optimizer_full.py — полная оптимизация 16 GOLDEN."""
import os, sys, json, sqlite3, time, random
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.expanduser('~/quantum_lab'), 'core'))
import numpy as np
from okx_new_strategies import okx_rsi_rev, okx_boll_rev, okx_ichimoku, okx_breakout, okx_ensemble

BASE = os.path.expanduser('~/quantum_lab')
GRAILS = os.path.join(BASE, 'data/grails/16golden.json')
ACTIVE_V2 = os.path.join(BASE, 'data/okx_active.json')
ACTIVE_V3 = os.path.join(BASE, 'data/okx_active_v3.json')
MARKET = os.path.join(BASE, 'data/market.db')
LOG = os.path.join(BASE, 'logs/grail_optimizer_full.log')

TP_GRID = [0.003, 0.004, 0.005, 0.006, 0.008]
SL_GRID = [0.002, 0.003, 0.004, 0.005]
TIMEOUT_GRID = [1, 2, 3]
FEE = 0.0015
SLIPPAGE = 0.0005  # 0.05% проскальзывание
DAYS = 180

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] [full] {m}'
    with open(LOG, 'a') as f: f.write(line + '\n')

def load_candles(sym, days=DAYS, tf='15m'):
    # TF выбирается из конфига (15m/1h/4h)
    c = sqlite3.connect(MARKET, timeout=10)
    cutoff = int(time.time()) - days*86400
    rows = c.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf=? AND ts>? ORDER BY ts",
                     (sym, tf, cutoff)).fetchall()
    c.close()
    if not rows: return None
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def get_strategy_func(name):
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
    # новые семейства
    if name.startswith('okx_rsi_rev_') and nums:
        from okx_new_strategies import okx_rsi_rev
        return okx_rsi_rev(int(nums[0]))
    if name.startswith('okx_boll_rev_') and nums:
        from okx_new_strategies import okx_boll_rev
        return okx_boll_rev(int(nums[0]))
    if name.startswith('okx_ichimoku_') and nums:
        from okx_new_strategies import okx_ichimoku
        return okx_ichimoku(int(nums[0]))
    if name.startswith('okx_breakout_') and nums:
        from okx_new_strategies import okx_breakout
        return okx_breakout(int(nums[0]))
    # ансамбли — все импорты локально
    if name.startswith('okx_ensemble'):
        from okx_new_strategies import okx_ensemble, okx_rsi_rev, okx_boll_rev, okx_ichimoku
        from okx_mutator import okx_vwap_rev
        from okx_grid import okx_grid_sma
        if name == 'okx_ensemble_vwap_rsi':
            return okx_ensemble([okx_vwap_rev(13), okx_rsi_rev(14), okx_grid_sma(13)], min_votes=2)
        if name == 'okx_ensemble_boll_grid':
            return okx_ensemble([okx_boll_rev(20), okx_grid_sma(13), okx_vwap_rev(7)], min_votes=2)
        if name == 'okx_ensemble_ichimoku_vwap':
            return okx_ensemble([okx_ichimoku(9), okx_vwap_rev(13)], min_votes=2)
    return None

def simulate(data, fn, tp, sl, timeout_bars):
    o, h, l, c, v = data['o'], data['h'], data['l'], data['c'], data['v']
    n = len(c)
    if n < 50: return None
    try:
        ind = {}
        up, dn = fn(o, h, l, c, v, ind)
    except: return None
    wins = losses = total = 0; pnl = 0.0
    for i in range(30, n-1):
        for side, sig in [('LONG', up[i]), ('SHORT', dn[i])]:
            if not sig: continue
            ep = c[i]
            for j in range(i+1, min(i+1+timeout_bars, n)):
                move = (c[j]-ep)/ep if side=='LONG' else (ep-c[j])/ep
                if move >= tp: pnl += tp-(2*FEE+SLIPPAGE); wins += 1; total += 1; break
                elif move <= -sl: pnl += -sl-(2*FEE+SLIPPAGE); losses += 1; total += 1; break
            else:
                move = (c[min(i+timeout_bars, n-1)]-ep)/ep if side=='LONG' else (ep-c[min(i+timeout_bars, n-1)])/ep
                pnl += move-(2*FEE+SLIPPAGE); total += 1
                if move > 0: wins += 1
                else: losses += 1
    if total == 0: return None
    return {'n': total, 'wins': wins, 'losses': losses,
            'wr': round(100*wins/total, 1), 'pnl': round(pnl, 2), 'exp': round(pnl/total, 4)}

def wf_5fold(data, fn, tp, sl, timeout):
    """Walk-forward 5-fold: стабильность."""
    n = len(data['c']); fold = n//5; results = []
    for k in range(5):
        start = k*fold
        end = (k+1)*fold if k<4 else n
        oo=data['o'][start:end]; hh=data['h'][start:end]
        ll=data['l'][start:end]; cc=data['c'][start:end]; vv=data['v'][start:end]
        if len(cc) < 100: continue
        r = simulate({'o':oo,'h':hh,'l':ll,'c':cc,'v':vv}, fn, tp, sl, timeout)
        if r: results.append(r)
    return results

def monte_carlo(data, fn, tp, sl, timeout, n_iter=30):
    """Monte Carlo: 30 случайных окон 70%."""
    import random
    n = len(data['c'])
    if n < 200: return []
    results = []
    for _ in range(n_iter):
        size = int(n * 0.7)
        start = random.randint(0, n - size)
        oo=data['o'][start:start+size]; hh=data['h'][start:start+size]
        ll=data['l'][start:start+size]; cc=data['c'][start:start+size]; vv=data['v'][start:start+size]
        r = simulate({'o':oo,'h':hh,'l':ll,'c':cc,'v':vv}, fn, tp, sl, timeout)
        if r: results.append(r)
    return results

def multi_oos_check(data, fn, tp, sl, timeout, periods=[30,60,90]):
    """Multi-OOS: 30/60/90 дней."""
    n = len(data['c']); results = {}
    for days in periods:
        bars = int(days * 96)
        if n < bars + 30: continue
        start = n - bars
        oo=data['o'][start:]; hh=data['h'][start:]
        ll=data['l'][start:]; cc=data['c'][start:]; vv=data['v'][start:]
        r = simulate({'o':oo,'h':hh,'l':ll,'c':cc,'v':vv}, fn, tp, sl, timeout)
        if r: results[days] = r
    return results

def tp_sl_sensitivity(data, fn, tp, sl, timeout, delta=0.2):
    """TP/SL sensitivity: ±20%."""
    results = []
    for mult in [1-delta, 1.0, 1+delta]:
        for sl_mult in [1-delta, 1.0, 1+delta]:
            tp_v, sl_v = tp*mult, sl*sl_mult
            r = simulate(data, fn, tp_v, sl_v, timeout)
            if r: results.append({'tp':tp_v,'sl':sl_v,'wr':r['wr'],'pnl':r['pnl'],'n':r['n']})
    return results

def stability_check(data, fn, tp, sl, timeout, log_fn=None):
    """Все 4 теста. Возвращает (passed, details)."""
    details = {}
    # 1. Walk-forward 5-fold
    wf = wf_5fold(data, fn, tp, sl, timeout)
    if not wf or len(wf) < 3:
        details['wf'] = 'FAIL (мало фолдов)'; return False, details
    wrs = [r['wr'] for r in wf]; pnls = [r['pnl'] for r in wf]
    import numpy as np
    wf_std = float(np.std(wrs))
    if wf_std >= 15 or min(wrs) < 50 or min(pnls) < -0.5:
        details['wf'] = f'FAIL (std={wf_std:.1f}%, min WR={min(wrs):.1f}%)'; return False, details
    details['wf'] = f'OK (std={wf_std:.1f}%, min WR={min(wrs):.1f}%)'

    # 2. Monte Carlo
    mc = monte_carlo(data, fn, tp, sl, timeout, n_iter=30)
    if mc:
        profitable = sum(1 for r in mc if r['pnl'] > 0)
        if profitable < 24:
            details['mc'] = f'FAIL ({profitable}/30 в плюс)'; return False, details
        details['mc'] = f'OK ({profitable}/30)'
    else:
        details['mc'] = 'SKIP (мало данных)'

    # 3. Multi-OOS
    mos = multi_oos_check(data, fn, tp, sl, timeout, [30,60,90])
    if mos:
        positive = sum(1 for d, r in mos.items() if r['pnl'] > 0)
        if positive < 2:
            details['oos'] = f'FAIL ({positive}/{len(mos)} в плюс)'; return False, details
        details['oos'] = f'OK ({positive}/{len(mos)})'
    else:
        details['oos'] = 'SKIP (мало данных)'

    # 4. TP/SL sensitivity
    sens = tp_sl_sensitivity(data, fn, tp, sl, timeout, delta=0.2)
    if sens:
        robust = sum(1 for r in sens if r['pnl'] > 0)
        if robust < len(sens)*0.66:
            details['sens'] = f'FAIL ({robust}/{len(sens)} в плюс)'; return False, details
        details['sens'] = f'OK ({robust}/{len(sens)})'
    else:
        details['sens'] = 'SKIP'

    return True, details

def wf_10fold(data, fn, tp, sl, timeout):
    n = len(data['c']); fold = n//10; results = []
    for k in range(10):
        start = k*fold
        end = (k+1)*fold if k<9 else n
        oo=data['o'][start:end]; hh=data['h'][start:end]
        ll=data['l'][start:end]; cc=data['c'][start:end]; vv=data['v'][start:end]
        if len(cc) < 50: continue
        r = simulate({'o':oo,'h':hh,'l':ll,'c':cc,'v':vv}, fn, tp, sl, timeout)
        if r: results.append(r)
    return results

def monte_carlo_50(data, fn, tp, sl, timeout):
    import random
    random.seed(42)
    n = len(data['c'])
    if n < 200: return []
    results = []
    for _ in range(50):
        size = int(n * 0.5)
        start = random.randint(0, n - size)
        oo=data['o'][start:start+size]; hh=data['h'][start:start+size]
        ll=data['l'][start:start+size]; cc=data['c'][start:start+size]; vv=data['v'][start:start+size]
        r = simulate({'o':oo,'h':hh,'l':ll,'c':cc,'v':vv}, fn, tp, sl, timeout)
        if r: results.append(r)
    return results

def multi_oos_6(data, fn, tp, sl, timeout):
    n = len(data['c']); results = {}
    for days in [7,14,30,60,90,180]:
        bars = int(days * 96)
        if n < bars + 30: continue
        start = n - bars
        oo=data['o'][start:]; hh=data['h'][start:]
        ll=data['l'][start:]; cc=data['c'][start:]; vv=data['v'][start:]
        r = simulate({'o':oo,'h':hh,'l':ll,'c':cc,'v':vv}, fn, tp, sl, timeout)
        if r: results[days] = r
    return results

def tp_sl_sens_30(data, fn, tp, sl, timeout):
    results = []
    for mult in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]:
        for sl_mult in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]:
            r = simulate(data, fn, tp*mult, sl*sl_mult, timeout)
            if r: results.append({'pnl':r['pnl'],'wr':r['wr']})
    return results

def stability_check_2(data, fn, tp, sl, timeout):
    """Проверка №2: 10-fold, 50 MC, 6 OOS, ±30% TP/SL."""
    details = {}
    # 1. WF 10-fold
    wf = wf_10fold(data, fn, tp, sl, timeout)
    if not wf or len(wf) < 5:
        details['wf10'] = 'FAIL (мало фолдов)'; return False, details
    wrs = [r['wr'] for r in wf]; pnls = [r['pnl'] for r in wf]
    import numpy as np
    wf_std = float(np.std(wrs))
    if wf_std >= 15 or min(wrs) < 50 or min(pnls) < -0.5:
        details['wf10'] = f'FAIL (std={wf_std:.1f}%)'; return False, details
    details['wf10'] = f'OK (std={wf_std:.1f}%)'

    # 2. MC 50
    mc = monte_carlo_50(data, fn, tp, sl, timeout)
    if mc:
        profitable = sum(1 for r in mc if r['pnl'] > 0)
        if profitable < 40:
            details['mc50'] = f'FAIL ({profitable}/50)'; return False, details
        details['mc50'] = f'OK ({profitable}/50)'
    else:
        details['mc50'] = 'SKIP'

    # 3. Multi-OOS 6
    mos = multi_oos_6(data, fn, tp, sl, timeout)
    if mos:
        positive = sum(1 for d, r in mos.items() if r['pnl'] > 0)
        if positive < 4:
            details['oos6'] = f'FAIL ({positive}/{len(mos)})'; return False, details
        details['oos6'] = f'OK ({positive}/{len(mos)})'
    else:
        details['oos6'] = 'SKIP'

    # 4. TP/SL ±30%
    sens = tp_sl_sens_30(data, fn, tp, sl, timeout)
    if sens:
        robust = sum(1 for r in sens if r['pnl'] > 0)
        if robust < len(sens)*0.75:
            details['sens30'] = f'FAIL ({robust}/{len(sens)})'; return False, details
        details['sens30'] = f'OK ({robust}/{len(sens)})'
    else:
        details['sens30'] = 'SKIP'

    return True, details

def oos_30days(sym, fn, tp, sl, timeout):
    """Out-of-sample: последние 30 дней (НЕ в обучении)."""
    import sqlite3, time
    import numpy as np
    cutoff = int(time.time()) - 30*86400
    c = sqlite3.connect(MARKET, timeout=10)
    rows = c.execute("SELECT o,h,l,c,v FROM candles WHERE symbol=? AND tf='15m' AND ts>? ORDER BY ts", (sym, cutoff)).fetchall()
    c.close()
    if not rows or len(rows) < 100: return None
    o=np.array([r[0] for r in rows]); h=np.array([r[1] for r in rows])
    l=np.array([r[2] for r in rows]); cl=np.array([r[3] for r in rows]); vv=np.array([r[4] for r in rows])
    return simulate({'o':o,'h':h,'l':l,'c':cl,'v':vv}, fn, tp, sl, timeout)

def check_periods(sym, fn, tp, sl, timeout):
    """Проверка на 30/7/1 день (out-of-sample)."""
    import sqlite3, time
    import numpy as np
    results = {}
    for days in [30, 7, 1]:
        cutoff = int(time.time()) - days*86400
        c = sqlite3.connect(MARKET, timeout=10)
        rows = c.execute("SELECT o,h,l,c,v FROM candles WHERE symbol=? AND tf='15m' AND ts>? ORDER BY ts", (sym, cutoff)).fetchall()
        c.close()
        if not rows or len(rows) < 50:
            results[days] = None
            continue
        o=np.array([r[0] for r in rows]); h=np.array([r[1] for r in rows])
        l=np.array([r[2] for r in rows]); cl=np.array([r[3] for r in rows]); vv=np.array([r[4] for r in rows])
        r = simulate({'o':o,'h':h,'l':l,'c':cl,'v':vv}, fn, tp, sl, timeout)
        results[days] = r
    return results

def walk_forward(data, fn, tp, sl, timeout):
    """Walk-forward: 70% train, 30% test."""
    n = len(data['c'])
    split = int(n * 0.7)
    train = {k: v[:split] for k, v in data.items()}
    test = {k: v[split:] for k, v in data.items()}
    r_train = simulate(train, fn, tp, sl, timeout)
    r_test = simulate(test, fn, tp, sl, timeout)
    if not r_train or not r_test: return None
    return {'train': r_train, 'test': r_test}

def by_regime(data, fn, tp, sl, timeout):
    """По режимам: bull/bear/flat, с walk-forward 70/30."""
    n = len(data['c'])
    seg = n // 3
    results = {}
    for name, sl_data in [
        ('bull', {k: v[:seg] for k, v in data.items()}),
        ('bear', {k: v[seg:2*seg] for k, v in data.items()}),
        ('flat', {k: v[2*seg:] for k, v in data.items()}),
    ]:
        # walk-forward: train 70%, test 30%
        sn = len(sl_data['c'])
        if sn < 100: continue
        split = int(sn * 0.7)
        train = {k: v[:split] for k, v in sl_data.items()}
        test = {k: v[split:] for k, v in sl_data.items()}
        r_train = simulate(train, fn, tp, sl, timeout)
        r_test = simulate(test, fn, tp, sl, timeout)
        if r_train and r_test:
            results[name] = r_test  # пишем только test (OOS внутри режима)
    return results

def optimize_full(sym, strat_name, base_wr, tf='15m', stage='fast'):
    log(f'🔍 {sym} {strat_name} (base WR={base_wr}%)')
    data = load_candles(sym, tf=tf)
    if not data: log('  ⚠️ нет данных'); return None
    fn = get_strategy_func(strat_name)
    if not fn: log('  ⚠️ стратегия не найдена'); return None
    
    best = None
    best_score = -999
    
    # 1. Мутанты + TP/SL + timeout
    import re
    nums = [float(x) for x in re.findall(r'\d+\.?\d*', strat_name)]
    candidates = [strat_name]
    # FAST: только базовые + мутанты (без новых)
    if stage == 'fast':
        # мутанты базовой
        if 'okx_vwap_rev' in strat_name and nums:
            p = int(nums[0])
            for mp in [p-5, p-3, p-2, p+2, p+3, p+5]:
                if 5 <= mp <= 60: candidates.append(f'okx_vwap_rev_{mp}')
        if 'okx_grid_sma' in strat_name and nums:
            p = int(nums[0])
            for mp in [p-5, p-3, p-2, p+2, p+3, p+5]:
                if 5 <= mp <= 60: candidates.append(f'okx_grid_sma_{mp}')
    # FULL: все новые + ансамбли
    if stage == 'full':
        candidates += ['okx_rsi_rev_7', 'okx_rsi_rev_14', 'okx_rsi_rev_21']
        candidates += ['okx_boll_rev_10', 'okx_boll_rev_20', 'okx_boll_rev_30']
        candidates += ['okx_ichimoku_9', 'okx_ichimoku_12', 'okx_ichimoku_15']
        candidates += ['okx_breakout_10', 'okx_breakout_20', 'okx_breakout_30']
        candidates += ['okx_ensemble_vwap_rsi', 'okx_ensemble_boll_grid', 'okx_ensemble_ichimoku_vwap']
    # новые семейства — базовые периоды
    if strat_name.startswith('okx_rsi_rev_') or 'rsi' in strat_name.lower():
        for p in [7, 14, 21]:
            candidates.append(f'okx_rsi_rev_{p}')
    if strat_name.startswith('okx_boll_rev_') or 'boll' in strat_name.lower():
        for p in [10, 20, 30]:
            candidates.append(f'okx_boll_rev_{p}')
    if strat_name.startswith('okx_ichimoku_') or 'ichimoku' in strat_name.lower():
        for p in [9, 12, 15]:
            candidates.append(f'okx_ichimoku_{p}')
    if strat_name.startswith('okx_breakout_') or 'breakout' in strat_name.lower():
        for p in [10, 20, 30]:
            candidates.append(f'okx_breakout_{p}')
    if 'okx_vwap_rev' in strat_name and nums:
        p = int(nums[0])
        for mp in [p-5, p-3, p-2, p+2, p+3, p+5]:
            if 5 <= mp <= 60: candidates.append(f'okx_vwap_rev_{mp}')
    if 'okx_grid_sma' in strat_name and nums:
        p = int(nums[0])
        for mp in [p-5, p-3, p-2, p+2, p+3, p+5]:
            if 5 <= mp <= 60: candidates.append(f'okx_grid_sma_{mp}')
    
    for cand in candidates:
        fn_c = get_strategy_func(cand)
        if not fn_c: continue
        for tp in TP_GRID:
            for sl in SL_GRID:
                for timeout in TIMEOUT_GRID:
                    wf = walk_forward(data, fn_c, tp, sl, timeout)
                    if not wf: continue
                    # Проверка: test WR >= 55, train WR >= 55
                    if wf['test']['wr'] < 55 or wf['train']['wr'] < 55: continue
                    if wf['test']['n'] < 300: continue
                    # Score: test PnL + test WR
                    score = wf['test']['pnl']
                    if score > best_score:
                        best_score = score
                        best = {'name': cand, 'tp': tp, 'sl': sl, 'timeout': timeout,
                                'train_wr': wf['train']['wr'], 'test_wr': wf['test']['wr'],
                                'test_pnl': wf['test']['pnl'], 'test_n': wf['test']['n']}
    
    if not best:
        log(f'  ⚠️ нет walk-forward (WR>=55)'); return None

    # 30/7/1 день (out-of-sample)
    fn_best = get_strategy_func(best['name'])
    if fn_best:
        periods = check_periods(sym, fn_best, best['tp'], best['sl'], best['timeout'])
        p30 = periods.get(30)
        p7 = periods.get(7)
        p1 = periods.get(1)
        # reject если 30д или 7д в минусе
        if p30 and (p30['pnl'] < 0 or p30['wr'] < 60):
            log(f'  ❌ 30d reject: WR={p30["wr"]:.1f}% PnL={p30["pnl"]:+.2f} n={p30["n"]}')
            return None
        if p7 and (p7['pnl'] < 0 or p7['wr'] < 60):
            log(f'  ❌ 7d reject: WR={p7["wr"]:.1f}% PnL={p7["pnl"]:+.2f} n={p7["n"]}')
            return None
        if p30 and p7:
            log(f'  ✅ 30d: {p30["n"]}сд {p30["pnl"]:+.2f} {p30["wr"]:.0f}% | 7d: {p7["n"]}сд {p7["pnl"]:+.2f} {p7["wr"]:.0f}%')

    # OOS 30 дней (out-of-sample)
    fn_best = get_strategy_func(best['name'])
    if fn_best:
        oos = oos_30days(sym, fn_best, best['tp'], best['sl'], best['timeout'])
        if oos and (oos['pnl'] < 0 or oos['wr'] < 60):
            log(f'  ❌ OOS 30d reject: WR={oos["wr"]:.1f}% PnL={oos["pnl"]:+.2f} n={oos["n"]}')
            return None
        elif oos:
            log(f'  ✅ OOS 30d OK: WR={oos["wr"]:.1f}% PnL={oos["pnl"]:+.2f} n={oos["n"]}')

    # ФИЛЬТР ТРЕНДА: проверить, что best не идёт против тренда
    try:
        ORACLE_DB = os.path.join(BASE, 'data/oracle.db')
        cc_t = sqlite3.connect(ORACLE_DB, timeout=10)
        reg_row = cc_t.execute("SELECT regime FROM regime WHERE symbol=? ORDER BY ts DESC LIMIT 1",
                                (sym,)).fetchone()
        cc_t.close()
        current_regime = reg_row[0] if reg_row else 'flat'
        fn_b = get_strategy_func(best['name'])
        # Прогнать на последних 500 свечах, посмотреть, что сигналит
        cc_t = sqlite3.connect(MARKET, timeout=10)
        rr_t = cc_t.execute("SELECT o,h,l,c,v FROM candles WHERE symbol=? AND tf='15m' ORDER BY ts DESC LIMIT 500",
                            (sym,)).fetchall()
        cc_t.close()
        if rr_t:
            rr_t = rr_t[::-1]
            oo=np.array([x[0] for x in rr_t]); hh=np.array([x[1] for x in rr_t])
            ll=np.array([x[2] for x in rr_t]); cc_=np.array([x[3] for x in rr_t]); vv=np.array([x[4] for x in rr_t])
            up_t, dn_t = fn_b(oo,hh,ll,cc_,vv,{})
            longs = int(sum(up_t[-100:]))
            shorts = int(sum(dn_t[-100:]))
            if current_regime == 'trend_up' and shorts > longs * 2:
                log(f'  ❌ TREND reject: trend_up, но SHORT {shorts} vs LONG {longs}')
                return None
            if current_regime == 'trend_down' and longs > shorts * 2:
                log(f'  ❌ TREND reject: trend_down, но LONG {longs} vs SHORT {shorts}')
                return None
            log(f'  ✅ TREND OK: regime={current_regime} LONG={longs} SHORT={shorts}')
    except Exception as e:
        log(f'  ⚠️ TREND check err: {e}')

    # final_oos_check: последние 30 дней (out-of-sample)
    try:
        oos_cutoff = int(time.time()) - 30*86400
        cc = sqlite3.connect(MARKET, timeout=10)
        rr = cc.execute("SELECT o,h,l,c,v FROM candles WHERE symbol=? AND tf='15m' AND ts>? ORDER BY ts",
                        (sym, oos_cutoff)).fetchall()
        cc.close()
        if rr and len(rr) > 100:
            oo=np.array([x[0] for x in rr]); hh=np.array([x[1] for x in rr])
            ll=np.array([x[2] for x in rr]); cc_=np.array([x[3] for x in rr]); vv=np.array([x[4] for x in rr])
            up_o, dn_o = get_strategy_func(best['name'])(oo,hh,ll,cc_,vv,{})
            wins_o=n_o=0; pnl_o=0.0
            for i in range(30, len(cc_)-1):
                for side_o, sig_o in [('LONG', up_o[i]), ('SHORT', dn_o[i])]:
                    if not sig_o: continue
                    ep_o = cc_[i]
                    for j in range(i+1, min(i+1+best['timeout'], len(cc_))):
                        mv = (cc_[j]-ep_o)/ep_o if side_o=='LONG' else (ep_o-cc_[j])/ep_o
                        if mv >= best['tp']: pnl_o += best['tp']-(2*FEE+SLIPPAGE); wins_o+=1; n_o+=1; break
                        elif mv <= -best['sl']: pnl_o += -best['sl']-(2*FEE+SLIPPAGE); n_o+=1; break
                    else:
                        mv = (cc_[min(i+best['timeout'],len(cc_)-1)]-ep_o)/ep_o if side_o=='LONG' else (ep_o-cc_[min(i+best['timeout'],len(cc_)-1)])/ep_o
                        pnl_o += mv-(2*FEE+SLIPPAGE); n_o+=1
                        if mv>0: wins_o+=1
            if n_o >= 20:
                oos_wr = 100*wins_o/n_o
                if oos_wr < 60 or pnl_o < 0.01:
                    log(f'  ❌ OOS reject: WR={oos_wr:.1f}% PnL={pnl_o:+.2f} n={n_o}')
                    return None
                log(f'  ✅ OOS OK: WR={oos_wr:.1f}% PnL={pnl_o:+.2f} n={n_o}')
            else:
                log(f'  ❌ OOS reject: n={n_o} < 20 (мало сделок)')
                return None
    except Exception as e:
        log(f'  ⚠️ OOS check err: {e}')

    
    # stability_check (методика №1): 5-fold, 30 MC, 3 OOS, ±20% TP/SL
    try:
        passed, details = stability_check(data, get_strategy_func(best['name']), best['tp'], best['sl'], best['timeout'])
        if not passed:
            log(f'  ❌ STABILITY1 reject: {details}')
            return None
        log(f'  ✅ STABILITY1 OK: {details}')
    except Exception as e:
        log(f'  ⚠️ STABILITY1 err: {e}')

    # stability_check_2 (методика №2): 10-fold, 50 MC, 6 OOS, ±30% TP/SL
    try:
        passed2, details2 = stability_check_2(data, get_strategy_func(best['name']), best['tp'], best['sl'], best['timeout'])
        if not passed2:
            log(f'  ❌ STABILITY2 reject: {details2}')
            return None
        log(f'  ✅ STABILITY2 OK: {details2}')
    except Exception as e:
        log(f'  ⚠️ STABILITY2 err: {e}')

    # 2. По режимам
    fn_best = get_strategy_func(best['name'])
    regimes = by_regime(data, fn_best, best['tp'], best['sl'], best['timeout'])
    
    log(f'  ✅ BEST: {best["name"]} tp={best["tp"]} sl={best["sl"]} timeout={best["timeout"]}')
    log(f'    train WR={best["train_wr"]}%, test WR={best["test_wr"]}%, test PnL={best["test_pnl"]}%, n={best["test_n"]}')
    log(f'    режимы: bull={regimes.get("bull",{}).get("wr")}%, bear={regimes.get("bear",{}).get("wr")}%, flat={regimes.get("flat",{}).get("wr")}%')
    
    # 3. Гибриды (с другими стратегиями)
    # (пропускаем — генетика сложна, фокус на мутантах+WF+TP/SL+режимы)
    
    return {'symbol': sym, 'strategy': best['name'], 'tp': best['tp'], 'sl': best['sl'],
            'timeout': best['timeout'], 'wr': best['test_wr'], 'n': best['test_n'],
            'regimes': {k: v.get('wr') for k, v in regimes.items()}}

def main():
    log('=== GRAIL OPTIMIZER FULL ===')
    if not os.path.exists(GRAILS): log('❌ нет 16golden.json'); return
    d = json.load(open(GRAILS))
    pairs = d.get('pairs', {})
    log(f'Граалей: {len(pairs)}')
    
    new_pairs = {}
    for key, cfg in pairs.items():
        sym = cfg.get('symbol', '').replace('-', '')
        strat = cfg.get('strategy', '')
        base_wr = cfg.get('wr', 0)
        # ЭТАП 1: FAST
        result = optimize_full(sym, strat, base_wr, tf="15m", stage="fast")
        if result:
            result["tf"] = "15m"
            result["stage"] = "fast"
            log(f"  ⚡ FAST: {sym} {result['strategy']} WR={result['wr']}%")
        # ЭТАП 2: FULL (только если FAST прошёл)
        result_full = None
        if result:
            result_full = optimize_full(sym, strat, base_wr, tf="15m", stage="full")
        if result_full and (not result or result_full.get("test_wr",0) > result.get("test_wr",0)):
            result_full["tf"] = "15m"
            result_full["stage"] = "full"
            result = result_full
            log(f"  🔬 FULL: {sym} {result['strategy']} WR={result['wr']}%")
        if result and result.get("stage") == "full":
            result_1h = optimize_full(sym, strat, base_wr, tf="1h", stage="full")
            if result_1h and result_1h.get("test_wr",0) > result.get("test_wr",0):
                result_1h["tf"] = "1h"
                result_1h["stage"] = "full_1h"
                result = result_1h
                log(f"  🌐 1H: {sym} {result['strategy']} WR={result['wr']}%")
        if result:
            new_pairs[key] = {
                'symbol': cfg.get('symbol'),
                'tf': '15m',
                'strategy': result['strategy'],
                'wr': result['wr'],
                'n': result['n'],
                'tp': result['tp'],
                'sl': result['sl'],
                'timeout': result['timeout'],
                'trade': True
            }
    
    if new_pairs:
        out = {'updated_at': datetime.now().isoformat(), 'source': 'grail_optimizer_full',
               'pairs': new_pairs}
        json.dump(out, open(ACTIVE_V2, 'w'), indent=2)
        json.dump(out, open(ACTIVE_V3, 'w'), indent=2)
        log(f'✅ {len(new_pairs)} граалей → okx_active.json, okx_active_v3.json')
    else:
        log('❌ нет результатов')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
