#!/usr/bin/env python3
"""tools/evolution_pipeline.py — мутационный конвейер: L1 -> L2 -> L3.

Каждые 6 часов (workflow evolution.yml):
  1. Юниверс из data/universe.json (без стейблов), топ-8 пар
  2. История OKX 1m (~3.5 дня) -> 5m бары
  3. Мутации трёх семейств:
     mean_rev (окно/z-вход/TP/SL), breakout (дончиан/TP/SL),
     momentum (EMA-кросс/TP/SL) — 24 генома x 8 пар = 192 кандидата (L1)
  4. Walk-forward: 70% история IS / 30% OOS. Издержки 0.28%/круг,
     вход по open следующего бара, внутри бара SL приоритетнее TP (пессимизм)
  5. L2: OOS >= 6 сделок, OOS pnl > 0, OOS wr >= 45%, IS pnl > 0
  6. L3: топ-20 по score = oos_pnl% * sqrt(oos_trades)
  7. data/evolution.json (панель) + data/evo_progress.json (realtime)
"""
import base64, json, math, os, time, urllib.request

BASE = os.path.expanduser('~/quantum_lab')
REPO = 'palcikia-crypto/quantum_lab'
DEFAULT_PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'BNBUSDT', 'ADAUSDT', 'LINKUSDT']
FEE_ROUND = 0.0028  # 0.12% комиссия + 0.02% слиппейдж за сторону
IS_FRAC = 0.7


def log(m):
    print('[evo] %s' % m, flush=True)


def api(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'quantum-lab/evo/1.0'})
    with urllib.request.urlopen(req, timeout=15) as f:
        return json.load(f)


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
    payload = {'message': 'Evo: ' + name, 'content': b64, 'branch': 'master'}
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


def progress(stage, txt, pct, extra=None):
    p = {'updated_at': int(time.time()), 'stage': stage, 'stage_txt': txt, 'pct': pct}
    if extra:
        p.update(extra)
    try:
        push_github('evo_progress.json', p)
    except Exception:
        pass


def universe():
    try:
        u = json.load(open(os.path.join(BASE, 'data/universe.json')))
        stables = {'USDCUSDT', 'USDTUSDT', 'FDUSDUSDT', 'DAIUSDT', 'TUSDUSDT', 'XAUTUSDT'}
        pairs = [p for p in (u.get('pairs') or []) if p not in stables][:8]
        if len(pairs) >= 4:
            return pairs
    except Exception:
        pass
    return DEFAULT_PAIRS


def hist_5m(sym):
    inst = sym[:-4] + '-USDT' if sym.endswith('USDT') and '-' not in sym else sym
    start = int(time.time()) - 4 * 86400
    out = {}
    after = None
    pages = 0
    while pages < 60:
        url = 'https://www.okx.com/api/v5/market/history-candles?instId=%s&bar=1m&limit=100' % inst
        if after:
            url += '&after=' + str(after)
        d = None
        for attempt in range(3):
            try:
                d = api(url)
                break
            except Exception as e:
                if attempt == 2:
                    log('hist %s: %s' % (sym, e))
                time.sleep(1 + attempt)
        pages += 1
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
        time.sleep(0.12)
    bars = sorted(out.values())
    buckets = {}
    for b in bars:
        buckets.setdefault(b[0] // 300, []).append(b)
    five = []
    for k in sorted(buckets):
        g = buckets[k]
        five.append((k * 300, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4]))
    return five


def roll_z(closes, win):
    zs = [0.0] * len(closes)
    s = 0.0
    sq = 0.0
    for i, c in enumerate(closes):
        if i >= win:
            s -= closes[i - win]
            sq -= closes[i - win] ** 2
        s += c
        sq += c * c
        n = min(i + 1, win)
        m = s / n
        v = sq / n - m * m
        sd = math.sqrt(v) if v > 0 else 0.0
        zs[i] = (c - m) / sd if sd > 0 else 0.0
    return zs


def ema_series(closes, n):
    out = []
    k = 2.0 / (n + 1)
    e = closes[0] if closes else 0.0
    for c in closes:
        e = c * k + e * (1 - k)
        out.append(e)
    return out


def sim_generic(bars, entries, tp, sl, is_end):
    """entries: список (i, side). Вход по open бара i+1, издержки FEE_ROUND.
    Возвращает (trades_is, trades_oos) — pnl% на сделку."""
    out = {False: [], True: []}
    open_i = set()
    pos = None
    by_i = {e[0]: e[1] for e in entries}
    for i in range(1, len(bars)):
        if pos is None:
            side = by_i.get(i - 1)
            if side and i < len(bars) - 1:
                pos = {'side': side, 'ep': bars[i][1], 'i0': i - 1}
                continue
        else:
            ep = pos['ep']
            hi, lo, cl = bars[i][2], bars[i][3], bars[i][4]
            hit = None
            if pos['side'] == 'SHORT':
                if hi >= ep * (1 + sl):
                    hit = ep * (1 + sl)
                elif lo <= ep * (1 - tp):
                    hit = ep * (1 - tp)
                elif i - pos['i0'] >= 96:
                    hit = cl
            else:
                if lo <= ep * (1 - sl):
                    hit = ep * (1 - sl)
                elif hi >= ep * (1 + tp):
                    hit = ep * (1 + tp)
                elif i - pos['i0'] >= 96:
                    hit = cl
            if hit:
                raw = (hit / ep - 1) * (1 if pos['side'] == 'LONG' else -1)
                pnl = raw - FEE_ROUND
                out[pos['i0'] >= is_end].append(round(pnl * 100, 4))
                pos = None
    return out[False], out[True]


def genomes():
    gs = []
    for win in (20, 30):
        for z_in in (1.5, 1.9, 2.3):
            for tp in (0.0025, 0.0035):
                gs.append(('mean_rev', 'mr_w%d_z%.1f_tp%.2f' % (win, z_in, tp * 100),
                           {'win': win, 'z_in': z_in, 'z_out': 0.4, 'tp': tp, 'sl': 0.002}))
    for n in (96, 192):
        for tp in (0.006, 0.009):
            gs.append(('breakout', 'bo_n%d_tp%.1f' % (n, tp * 100),
                       {'n': n, 'tp': tp, 'sl': 0.003}))
    for fast in (9, 12):
        for slow in (30, 50):
            gs.append(('momentum', 'mo_%d_%d' % (fast, slow),
                       {'fast': fast, 'slow': slow, 'tp': 0.005, 'sl': 0.003}))
    return gs


def entries_for(fam, pars, bars):
    closes = [b[4] for b in bars]
    ents = []
    if fam == 'mean_rev':
        zs = roll_z(closes, pars['win'])
        for i in range(pars['win'] + 1, len(bars) - 1):
            if zs[i] >= pars['z_in']:
                ents.append((i, 'SHORT'))
            elif zs[i] <= -pars['z_in']:
                ents.append((i, 'LONG'))
    elif fam == 'breakout':
        n = pars['n']
        for i in range(n, len(bars) - 1):
            hh = max(b[2] for b in bars[i - n:i])
            ll = min(b[3] for b in bars[i - n:i])
            if bars[i][4] > hh:
                ents.append((i, 'LONG'))
            elif bars[i][4] < ll:
                ents.append((i, 'SHORT'))
    else:
        fe = ema_series(closes, pars['fast'])
        se = ema_series(closes, pars['slow'])
        for i in range(pars['slow'], len(bars) - 1):
            if fe[i - 1] <= se[i - 1] and fe[i] > se[i]:
                ents.append((i, 'LONG'))
            elif fe[i - 1] >= se[i - 1] and fe[i] < se[i]:
                ents.append((i, 'SHORT'))
    return ents


def main():
    pairs = universe()
    gs = genomes()
    total = len(pairs)
    log('конвейер: %d пар x %d геномов' % (total, len(gs)))
    results = []
    for pi, sym in enumerate(pairs):
        progress('scan', 'качаю историю %s (%d/%d)' % (sym, pi + 1, total), int(100.0 * pi / max(1, total)), {'l1': len(results)})
        try:
            bars = hist_5m(sym)
            if len(bars) < 700:
                log('%s: мало баров (%d)' % (sym, len(bars)))
                continue
            is_end = int(len(bars) * IS_FRAC)
            for fam, name, pars in gs:
                ents = entries_for(fam, pars, bars)
                if len(ents) < 4:
                    results.append({'symbol': sym, 'strategy': name, 'n_is': 0, 'n_oos': 0,
                                    'wr': 0, 'pnl_is': 0, 'pnl_oos': 0, 'score': -1})
                    continue
                ti, to = sim_generic(bars, ents, pars['tp'], pars['sl'], is_end)
                n_oos = len(to)
                wr = 100.0 * sum(1 for v in to if v > 0) / n_oos if n_oos else 0
                pnl_is = round(sum(ti), 3)
                pnl_oos = round(sum(to), 3)
                score = pnl_oos * math.sqrt(n_oos) if n_oos else -1
                results.append({'symbol': sym, 'strategy': name, 'n_is': len(ti), 'n_oos': n_oos,
                                'wr': round(wr, 1), 'pnl_is': pnl_is, 'pnl_oos': pnl_oos,
                                'score': round(score, 2)})
            log('%s: %d баров, геномов %d' % (sym, len(bars), len(gs)))
        except Exception as e:
            log('%s crash: %s' % (sym, e))
        progress('scan', 'обработано %d/%d пар' % (pi + 1, total), int(100.0 * (pi + 1) / max(1, total)), {'l1': len(results)})

    l1 = [r for r in results if r['n_oos'] > 0]
    l2 = [r for r in l1 if r['n_oos'] >= 6 and r['pnl_oos'] > 0 and r['wr'] >= 45 and r['pnl_is'] > 0]
    l2.sort(key=lambda r: -r['score'])
    l3 = l2[:20]
    top = [{'symbol': r['symbol'], 'strategy': r['strategy'], 'wr': r['wr'], 'n': r['n_oos'],
            'expectancy': round((r['pnl_oos'] / r['n_oos']) / 100.0, 5), 'score': r['score']} for r in l3]
    out = {'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'), 'L1': len(l1), 'L2': len(l2),
           'L3': len(l3), 'top': top}
    try:
        os.makedirs(os.path.join(BASE, 'data'), exist_ok=True)
        with open(os.path.join(BASE, 'data/evolution.json'), 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    push_github('evolution.json', out)
    progress('done', 'конвейер завершён: L1 %d → L2 %d → L3 %d' % (len(l1), len(l2), len(l3)), 100,
             {'l1': len(l1), 'l2': len(l2), 'l3': len(l3)})
    log('ГЕНЕРАЦИЯ: L1=%d L2=%d L3=%d' % (len(l1), len(l2), len(l3)))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        log('CRASH: %s' % e)
        log(traceback.format_exc()[-1000:])
        progress('error', 'сбой конвейера: %s' % e)
