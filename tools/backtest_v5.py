#!/usr/bin/env python3
"""tools/backtest_v5.py — честная валидация стратегий okx_bot_v5 на истории OKX.

Правила честности (без подгонок):
  - параметры фиксированы и совпадают с live-ботом, НИКАКОЙ оптимизации
  - сигнал по закрытому бару, вход по open следующего (no lookahead)
  - издержки: 0.10% комиссия + 0.02% проскальзывание за сторону (0.24% круг)
  - если внутри бара возможны и TP и SL — засчитан SL (пессимизм)
  - два окна: последние 7 дней и предыдущие 7 дней
  - funding — из реальной истории funding-rate-history
  - исторического стакана нет: mr_z/donchian проверены без OBI-фильтра;
    в live OBI лишь ДОПОЛНИТЕЛЬНО срезает часть сигналов (не создаёт новых)
Результат: data/backtest_report.json (пушится в master через GH_TOKEN).
"""
import base64, json, math, os, time, urllib.request

UNIVERSE = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'BNBUSDT', 'ADAUSDT', 'LINKUSDT']
FEE_SIDE = 0.0012
DAYS = 14
OUT = os.path.join(os.path.expanduser('~/quantum_lab'), 'data/backtest_report.json')

def log(m):
    print('[bt] %s' % m, flush=True)

def api(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'quantum-lab/5.0'})
    with urllib.request.urlopen(req, timeout=15) as f:
        return json.load(f)

def to_inst(sym):
    return sym[:-4] + '-USDT' if sym.endswith('USDT') and '-' not in sym else sym

def hist_1m(sym, days):
    inst = to_inst(sym)
    end = int(time.time())
    start = end - days * 86400
    out = {}
    after = None
    while True:
        url = 'https://www.okx.com/api/v5/market/history-candles?instId=%s&bar=1m&limit=100' % inst
        if after:
            url += '&after=' + str(after)
        try:
            d = api(url)
        except Exception as e:
            log('hist %s err: %s' % (sym, e))
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
        time.sleep(0.12)
    bars = sorted(out.values())
    log('%s: %d bars 1m' % (sym, len(bars)))
    return bars

def funding_hist(sym):
    try:
        d = api('https://www.okx.com/api/v5/public/funding-rate-history?instId=%s-SWAP&limit=100' % to_inst(sym))
        return sorted((int(x['fundingTime']), float(x['fundingRate'])) for x in (d.get('data') or []))
    except Exception:
        return []

def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0

def stdv(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))

def resample5m(bars):
    buckets = {}
    for b in bars:
        buckets.setdefault(b[0] // 300, []).append(b)
    out = []
    for k in sorted(buckets):
        g = buckets[k]
        out.append((k * 300, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4]))
    return out

def atr(bars):
    if len(bars) < 2:
        return 0.0
    rs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i][2], bars[i][3], bars[i - 1][4]
        rs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return mean(rs)

def simulate(bars, fnd):
    trades = []
    open_t = None
    fi = 0
    c5 = resample5m(bars)
    idx5 = {b[0]: k for k, b in enumerate(c5)}
    for i in range(30, len(bars) - 1):
        b = bars[i]
        ts = b[0]
        while fi < len(fnd) and fnd[fi][0] <= ts:
            fi += 1
        fr = fnd[fi - 1][1] if fi > 0 else None
        closes = [x[4] for x in bars[i - 19:i + 1]]
        m = mean(closes)
        s = stdv(closes)
        z = (b[4] - m) / s if s > 0 else 0.0
        if open_t is not None:
            side, strat, ep, tp, sl, expiry = open_t
            hi, lo = b[2], b[3]
            hit = None
            exit_p = None
            if side == 'SHORT':
                tp_ok = lo <= ep * (1 - tp)
                sl_ok = hi >= ep * (1 + sl)
            else:
                tp_ok = hi >= ep * (1 + tp)
                sl_ok = lo <= ep * (1 - sl)
            if sl_ok:
                hit = 'SL'
                exit_p = ep * (1 + sl) if side == 'SHORT' else ep * (1 - sl)
            elif tp_ok:
                hit = 'TP'
                exit_p = ep * (1 - tp) if side == 'SHORT' else ep * (1 + tp)
            if hit is None and ts >= expiry:
                hit = 'TIMEOUT'
                exit_p = b[4]
            if hit:
                d = 1 if side == 'LONG' else -1
                pnl = d * (exit_p - ep) / ep - 2 * FEE_SIDE
                trades.append({'strategy': strat, 'side': side, 'pnl': pnl, 'exit': hit})
                open_t = None
            continue
        sig = None
        if ts % 300 == 299:
            k = idx5.get((ts // 300) * 300)
            if k is not None and k >= 24:
                prior = c5[k - 24:k]
                hh = max(x[2] for x in prior)
                ll = min(x[3] for x in prior)
                a_now = atr(c5[k - 5:k + 1])
                a_avg = atr(c5[max(0, k - 29):k + 1])
                last5 = c5[k][4]
                if a_avg > 0 and a_now > 1.2 * a_avg:
                    if last5 > hh:
                        sig = ('LONG', 'donchian_atr', 0.008, 0.004, 7200)
                    elif last5 < ll:
                        sig = ('SHORT', 'donchian_atr', 0.008, 0.004, 7200)
        if sig is None and abs(z) > 2.2:
            sig = ('SHORT', 'mr_z', 0.0035, 0.0025, 1800) if z > 0 else ('LONG', 'mr_z', 0.0035, 0.0025, 1800)
        if sig is None and fr is not None:
            if fr > 0.0003 and z > 1.5:
                sig = ('SHORT', 'funding_squeeze', 0.005, 0.0035, 14400)
            elif fr < -0.0003 and z < -1.5:
                sig = ('LONG', 'funding_squeeze', 0.005, 0.0035, 14400)
        if sig:
            side, strat, tp, sl, tmo = sig
            nb = bars[i + 1]
            open_t = (side, strat, nb[1], tp, sl, nb[0] + tmo)
    return trades

def stats(trades):
    n = len(trades)
    if not n:
        return {'n': 0, 'wr': 0.0, 'pnl': 0.0, 'pf': 0.0, 'avg': 0.0}
    wins = [t['pnl'] for t in trades if t['pnl'] > 0]
    losses = [t['pnl'] for t in trades if t['pnl'] <= 0]
    gw = sum(wins)
    gl = -sum(losses)
    return {'n': n,
            'wr': round(100.0 * len(wins) / n, 1),
            'pnl': round(100.0 * sum(t['pnl'] for t in trades), 2),
            'pf': round(gw / gl, 2) if gl > 0 else 99.0,
            'avg': round(100.0 * sum(t['pnl'] for t in trades) / n, 3)}

def push_github(b64):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        log('no GH_TOKEN, local file only')
        return
    url = 'https://api.github.com/repos/palcikia-crypto/quantum_lab/contents/data/backtest_report.json'
    sha = None
    try:
        req = urllib.request.Request(url)
        req.add_header('Authorization', 'Bearer ' + token)
        with urllib.request.urlopen(req, timeout=15) as f:
            sha = json.load(f).get('sha')
    except Exception:
        pass
    payload = {'message': 'Backtest v5 report', 'content': b64, 'branch': 'master'}
    if sha:
        payload['sha'] = sha
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='PUT')
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Content-Type', 'application/json')
    urllib.request.urlopen(req, timeout=15).read()
    log('report pushed to master')

def main():
    now = int(time.time())
    report = {'updated_at': now, 'engine': 'backtest_v5', 'fee_side': FEE_SIDE,
              'universe': UNIVERSE, 'days': DAYS,
              'note': 'fixed live params; entry at next bar open; costs 0.24%/round; SL priority; real funding; live OBI only filters signals further',
              'strategies': {}}
    per = {}
    for sym in UNIVERSE:
        bars = hist_1m(sym, DAYS)
        if len(bars) < 600:
            log('%s: too few bars, skip' % sym)
            continue
        fnd = funding_hist(sym)
        cut = len(bars)
        for i, b in enumerate(bars):
            if b[0] >= now - 7 * 86400:
                cut = i
                break
        for w, sub in (('w7', bars[cut:]), ('w_prev', bars[:cut])):
            for t in simulate(sub, fnd):
                per.setdefault(t['strategy'], {}).setdefault(w, []).append(t)
    for strat, wins in per.items():
        entry = {}
        ok = True
        for w in ('w7', 'w_prev'):
            st = stats(wins.get(w) or [])
            entry[w] = st
            if st['n'] < 5 or st['pnl'] <= 0 or st['pf'] < 1.05:
                ok = False
        total = entry['w7']['pnl'] + entry['w_prev']['pnl']
        entry['verdict'] = 'ROBUST' if ok else ('TEST' if total > 0 else 'FRAGILE')
        report['strategies'][strat] = entry
        log('%s: w7 %s | prev %s => %s' % (strat, entry['w7'], entry['w_prev'], entry['verdict']))
    data = json.dumps(report, ensure_ascii=False, indent=1)
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, 'w') as f:
            f.write(data)
    except Exception as e:
        log('local write: %s' % e)
    try:
        push_github(base64.b64encode(data.encode()).decode())
    except Exception as e:
        log('push: %s' % e)

if __name__ == '__main__':
    main()
