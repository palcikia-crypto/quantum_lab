#!/usr/bin/env python3
"""tools/ai_core.py — МОЗГ лаборатории: самообучение на полном автомате.

1. Скан ликвидности: топ-16 USDT-пар по объёму 24ч -> data/universe.json
2. ML-модель: логистическая регрессия на 1m-фичах (направление 5-мин движения)
   -> data/ml_model.json (бот использует как ML veto)
3. Автобалансировка: по истории сделок (web_dashboard.json) отключает
   убыточные связки символ+стратегия -> data/live_weights.json
4. Отчёт о мозге -> data/ai_core.json (панель, вкладка Мозг)
Всё пушится в master через GH_TOKEN.
"""
import base64, json, math, os, time, urllib.request
import numpy as np

BASE = os.path.expanduser('~/quantum_lab')
REPO = 'palcikia-crypto/quantum_lab'

def log(m):
    print('[ai] %s' % m, flush=True)

def api(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'quantum-lab/ai/1.0'})
    with urllib.request.urlopen(req, timeout=15) as f:
        return json.load(f)

def write_local(name, obj):
    p = os.path.join(BASE, 'data', name)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w') as f:
            json.dump(obj, f, ensure_ascii=False)
    except Exception as e:
        log('local %s: %s' % (name, e))

def push_github(name, obj):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        return
    url = 'https://api.github.com/repos/%s/contents/data/%s' % (REPO, name)
    b64 = base64.b64encode(json.dumps(obj, ensure_ascii=False).encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(url)
        req.add_header('Authorization', 'Bearer ' + token)
        with urllib.request.urlopen(req, timeout=15) as f:
            sha = json.load(f).get('sha')
    except Exception:
        pass
    payload = {'message': 'AI core: ' + name, 'content': b64, 'branch': 'master'}
    if sha:
        payload['sha'] = sha
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='PUT')
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Content-Type', 'application/json')
    try:
        urllib.request.urlopen(req, timeout=20).read()
        log('pushed %s' % name)
    except Exception as e:
        log('push %s: %s' % (name, e))

def scan_universe():
    try:
        d = api('https://www.okx.com/api/v5/market/tickers?instType=SPOT')
        rows = [x for x in d.get('data') or [] if x['instId'].endswith('-USDT')]
        rows.sort(key=lambda x: float(x.get('volCcy24h') or 0), reverse=True)
        pairs = [x['instId'].replace('-USDT', 'USDT') for x in rows[:16]]
        pairs = [p for p in pairs if p]
        u = {'updated_at': int(time.time()), 'pairs': pairs}
        write_local('universe.json', u)
        push_github('universe.json', u)
        log('universe: %s' % ','.join(pairs[:8]))
        return pairs
    except Exception as e:
        log('universe err: %s' % e)
        return None

def hist_1m(sym, days):
    inst = sym[:-4] + '-USDT' if sym.endswith('USDT') and '-' not in sym else sym
    start = int(time.time()) - days * 86400
    out = {}
    after = None
    while True:
        url = 'https://www.okx.com/api/v5/market/history-candles?instId=%s&bar=1m&limit=100' % inst
        if after:
            url += '&after=' + str(after)
        d = None
        for attempt in range(4):
            try:
                d = api(url)
                break
            except Exception as e:
                log('hist %s: %s (попытка %d)' % (sym, e, attempt + 1))
                time.sleep(2 + attempt * 2)
        if not d:
            break
        rows = d.get('data') or []
        if not rows:
            break
        stop = False
        for r in rows:
            ts = int(r[0])
            if ts < start:
                stop = True
                break
            out[ts] = (ts, float(r[1]), float(r[2]), float(r[3]), float(r[4]))
            after = ts
        if stop:
            break
        time.sleep(0.1)
    return sorted(out.values())

def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0

def stdv(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))

def feats(bars, i):
    c = [b[4] for b in bars[max(0, i - 60):i + 1]]
    last = c[-1]
    m = mean(c[-20:])
    s = stdv(c[-20:])
    z = (last - m) / s if s > 0 else 0.0
    def r(n):
        return (c[-1] - c[-1 - n]) / c[-1 - n] * 100.0 if len(c) > n and c[-1 - n] else 0.0
    hi = max(c)
    lo = min(c)
    rng = (hi - lo) / last * 100.0 if last else 0.0
    pos = (last - lo) / (hi - lo) if hi > lo else 0.5
    return [z, r(5), r(15), r(60), rng, pos]

def train_ml(pairs):
    X, Y = [], []
    for sym in pairs[:6]:
        bars = hist_1m(sym, 3)
        if len(bars) < 1000:
            continue
        n0 = len(X)
        for i in range(70, len(bars) - 6):
            fwd = (bars[i + 5][4] - bars[i][4]) / bars[i][4] * 100.0
            if abs(fwd) < 0.08:
                continue
            X.append(feats(bars, i))
            Y.append(1.0 if fwd > 0 else 0.0)
        log('%s: +%d сэмплов' % (sym, len(X) - n0))
    if len(X) < 300:
        log('мало данных для ML')
        return None
    X = np.array(X)
    Y = np.array(Y)
    cut = int(len(X) * 0.8)
    Xtr, ytr = X[:cut], Y[:cut]
    Xva, yva = X[cut:], Y[cut:]
    w = np.zeros(X.shape[1])
    b = 0.0
    lr = 0.15
    for _ in range(400):
        z = Xtr.dot(w) + b
        p = 1.0 / (1.0 + np.exp(-z))
        g = p - ytr
        w -= lr * Xtr.T.dot(g) / len(ytr)
        b -= lr * float(g.mean())
    def acc(Xa, ya):
        p = 1.0 / (1.0 + np.exp(-(Xa.dot(w) + b)))
        return float(((p > 0.5) == (ya > 0.5)).mean())
    a_tr = acc(Xtr, ytr)
    a_va = acc(Xva, yva) if len(yva) else a_tr
    model = {'updated_at': int(time.time()), 'samples': int(len(X)),
              'train_acc': round(a_tr, 4), 'val_acc': round(a_va, 4),
              'weights': [round(float(x), 4) for x in w], 'bias': round(float(b), 4),
              'features': ['z20', 'ret5', 'ret15', 'ret60', 'range60', 'pos60'],
              'horizon': '5m', 'min_move': 0.08}
    write_local('ml_model.json', model)
    push_github('ml_model.json', model)
    log('ML: samples=%d train=%.3f val=%.3f' % (len(X), a_tr, a_va))
    return model

def rebalance():
    decisions = []
    disabled = []
    try:
        p = os.path.join(BASE, 'data/web_dashboard.json')
        d = json.load(open(p))
        agg = {}
        for t in d.get('trades') or []:
            if str(t.get('status') or '').upper() == 'OPEN':
                continue
            key = '%s|%s' % (t.get('symbol'), t.get('strategy'))
            agg.setdefault(key, []).append(t.get('pnl') or 0)
        for key, pnls in agg.items():
            if len(pnls) >= 8 and sum(pnls) < 0:
                wr = 100.0 * sum(1 for v in pnls if v > 0) / len(pnls)
                disabled.append(key)
                decisions.append({'key': key, 'action': 'DISABLE', 'n': len(pnls),
                                  'pnl': round(sum(pnls), 2), 'wr': round(wr, 1),
                                  'reason': 'минус на последних %d сделках' % len(pnls)})
    except Exception as e:
        log('rebalance: %s' % e)
    obj = {'updated_at': int(time.time()), 'disabled': disabled, 'decisions': decisions}
    write_local('live_weights.json', obj)
    push_github('live_weights.json', obj)
    return obj

def main():
    pairs = scan_universe() or ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'BNBUSDT', 'ADAUSDT', 'LINKUSDT']
    model = train_ml(pairs)
    rb = rebalance()
    report = {'updated_at': int(time.time()),
              'ml': {'val_acc': model['val_acc'] if model else None,
                     'samples': model['samples'] if model else 0},
              'universe': pairs, 'decisions': rb['decisions']}
    write_local('ai_core.json', report)
    push_github('ai_core.json', report)
    log('AI CORE: цикл завершён')

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        log('CRASH: %s' % e)
        err = {'updated_at': int(time.time()), 'error': str(e),
               'tb': traceback.format_exc()[-1500:]}
        write_local('ai_core.json', err)
        push_github('ai_core.json', err)
