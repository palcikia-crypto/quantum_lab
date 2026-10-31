#!/usr/bin/env python3
"""sync_grails_to_tpsl.py — holy_grail.json -> okx_tpsl_by_regime.json.
Оставляет только OKX-граали, добавляет недостающие пары."""
import os, json, time
from collections import defaultdict

BASE = os.path.expanduser('~/quantum_lab')
HG = os.path.join(BASE, 'data/holy_grail.json')
TPSL = os.path.join(BASE, 'data/okx_tpsl_by_regime.json')
OKX_DEFAULT_TP = 0.006
OKX_DEFAULT_SL = 0.004
OKX_DEFAULT_TIMEOUT = 2
OKX_STRATS = {'okx_vwap_rev_10','okx_vwap_rev_20','okx_vwap_rev_30',
              'okx_grid_sma_10','okx_grid_sma_20','okx_grid_sma_30',
              'okx_macd_5_35_5','okx_ema_7_25','okx_ema_8_24','okx_ema_5_20'}


def norm_dash(sym):
    if '-' in sym: return sym
    if sym.endswith('USDT'): return sym[:-4] + '-USDT'
    return sym


def main():
    try:
        load = float(open('/proc/loadavg').read().split()[0])
    except:
        load = 0
    if load > 6:
        print(f'load {load:.1f} > 6, пропускаю')
        return
    if not os.path.exists(HG):
        print(f'❌ {HG} нет'); return
    if not os.path.exists(TPSL):
        print(f'❌ {TPSL} нет'); return
    hg = json.load(open(HG))
    tpsl = json.load(open(TPSL))
    okx_grails = []
    for g in hg.get('grails', []):
        if g['strategy'] in OKX_STRATS:
            okx_grails.append({'pair': norm_dash(g['pair']), 'strategy': g['strategy']})
    if not okx_grails:
        print('ℹ️ OKX-граалей нет')
        return
    by_pair = defaultdict(list)
    for g in okx_grails:
        by_pair[g['pair']].append(g['strategy'])
    new_pp = {}
    for pair, strats in by_pair.items():
        uniq = list(dict.fromkeys(strats))
        regs = {}
        for reg in ['flat', 'trend_up', 'trend_down']:
            regs[reg] = {
                'strategy': uniq[0],
                'tp': OKX_DEFAULT_TP, 'sl': OKX_DEFAULT_SL, 'timeout_bars': OKX_DEFAULT_TIMEOUT,
                'alt_strategy': uniq[1] if len(uniq) > 1 else None,
            }
        new_pp[pair] = regs
    tpsl['per_pair'] = new_pp
    tpsl['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    tpsl['source'] = 'sync_grails'
    json.dump(tpsl, open(TPSL,'w'), indent=2, ensure_ascii=False)
    print(f'✅ sync_grails: {len(new_pp)} пар, {len(okx_grails)} OKX-граалей')


if __name__ == '__main__':
    from collections import defaultdict
    main()
