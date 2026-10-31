#!/usr/bin/env python3
"""okx_orchestrator.py — автономная OKX-лаборатория: докачка → мутанты → гейт → active."""
import os, sys, json, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.expanduser('~/quantum_lab')
ACTIVE = os.path.join(BASE, 'data/okx_active.json')
LOG = os.path.join(BASE, 'logs/okx_orchestrator.log')
CYCLE = 1800

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def atomic_write(path, data):
    tmp = path + '.tmp'
    json.dump(data, open(tmp, 'w'), ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def run_cycle():
    log('=== OKX CYCLE START ===')
    # 1. Докачка
    try:
        from okx_downloader import download
        for sym in ['BTC-USDT','ETH-USDT','XRP-USDT','SOL-USDT','DOGE-USDT','ADA-USDT','AVAX-USDT']:
            download(sym, '15m', max_pages=30)
        log('✅ download')
    except Exception as e: log(f'⚠️ download: {e}')
    # 2. OBI (скальпер)
    try:
        import asyncio
        from okx_scalper import collect_obi, init_db
        init_db()
        asyncio.run(collect_obi('BTC-USDT', duration=60))
        log('✅ obi')
    except Exception as e: log(f'⚠️ obi: {e}')
    # 3. Мутанты + гейт
    try:
        from okx_gate import run_gate
        from okx_mutator import generate_mutants
        muts = generate_mutants()
        log(f'мутантов: {len(muts)}')
        results = []
        for name, fn in muts.items():
            for sym in ['BTC-USDT','ETH-USDT','XRP-USDT','SOL-USDT','DOGE-USDT']:
                try:
                    r = run_gate(sym, '15m', name, fn)
                    if r: results.append(r)
                except: pass
        golden = [r for r in results if r['verdict'] == 'GOLDEN']
        log(f'✅ gate: {len(golden)} GOLDEN из {len(results)}')
        d = {'pairs': {}, 'updated_at': datetime.now().isoformat()}
        for r in golden:
            key = f"{r['symbol']}_15m_{r['strategy']}"
            d['pairs'][key] = {'symbol': r['symbol'], 'tf': '15m', 'strategy': r['strategy'],
                               'wr': r['L1']['wr'], 'n': r['L1']['n'], 'trade': True}
        atomic_write(ACTIVE, d)
        log(f'✅ active: {len(d["pairs"])} пар')
    except Exception as e: log(f'⚠️ gate: {e}')
    log('=== OKX CYCLE DONE ===')

def main():
    log('=== OKX ORCHESTRATOR STARTED ===')
    while True:
        try: run_cycle()
        except Exception as e: log(f'❌ CYCLE ERROR: {e}')
        log(f'сплю {CYCLE} сек...')
        time.sleep(CYCLE)

if __name__ == '__main__': main()
