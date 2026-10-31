import sys, os, json
sys.path.insert(0, os.path.expanduser('~/quantum_lab/core'))
from strategy_pool import STRATEGIES
from gate_v3 import run_gate
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
# 5 пар × 2 ТФ = 110 прогонов (вместо 440)
pairs = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT']
tf_model = {'15m':'current','4h':'open'}
results = []
for pair in pairs:
    for tf, model in tf_model.items():
        for name, fn in STRATEGIES.items():
            try:
                r = run_gate(pair, tf, name, fn, model=model, use_h1=True)
                if r and r['L1']['n'] >= 50: results.append(r)
            except: pass
results.sort(key=lambda x: (-x['score'], -x['L1']['wr']))
summary = {v: sum(1 for r in results if r['verdict']==v) for v in ['GOLDEN','TRADE_NOW','WATCH','SKIP']}
with open(f'{BASE}/data/gate_v3.json','w') as f:
    json.dump({'timestamp':datetime.now().isoformat(),'summary':summary,'results':results}, f, indent=2, ensure_ascii=False)
print('Прогонов: ' + str(len(results)))
print('Summary: ' + str(summary))
for r in results[:10]:
    print('  ' + r['symbol'].ljust(10) + ' ' + r['tf'].ljust(3) + ' ' + r['strategy'].ljust(15) + ' ' + r['verdict'].ljust(10) + ' WR=' + str(r['L1']['wr']) + '% n=' + str(r['L1']['n']))
