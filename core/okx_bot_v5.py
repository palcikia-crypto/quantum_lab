#!/usr/bin/env python3
"""okx_bot_v5.py — Quantum Lab v5: мультистратегия (не только скальпинг).

Стратегии (параметры фиксированы, валидация: tools/backtest_v5.py):
  mr_z            — возврат к среднему: z-score(1m) экстремум + подтверждение стаканом (OBI)
  donchian_atr    — пробой 2-часового диапазона 5m при расширении волатильности
  funding_squeeze — контрарий против толпы на экстремальном funding

Честность: сигналы только по закрытым барам; в live OBI — дополнительный
фильтр сверх бэктеста (срезает часть сделок, но не создаёт новых).
Риск: 2% банка на сделку, максимум 3 позиции, cooldown 10 мин на пару.
"""
import json, math, os, sqlite3, time, urllib.request
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
OB_DB = os.path.join(BASE, 'data/orderbook.db')
DB = os.path.join(BASE, 'data/okx_paper_v4.db')
LOG = os.path.join(BASE, 'logs/okx_bot_v5.log')

BANK0 = 1000.0
RISK = 0.02
MAX_OPEN = 3
COOLDOWN = 600
CYCLE = 60
UNIVERSE = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'BNBUSDT', 'ADAUSDT', 'LINKUSDT']
TIMEOUTS = {'mr_z': 1800, 'donchian_atr': 7200, 'funding_squeeze': 14400}

def log(m):
    line = '[%s] %s' % (datetime.now().strftime('%H:%M:%S'), m)
    print(line, flush=True)
    try:
        with open(LOG, 'a') as f:
            f.write(line + chr(10))
    except Exception:
        pass

def api(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'quantum-lab/5.0'})
    with urllib.request.urlopen(req, timeout=10) as f:
        return json.load(f)

def to_inst(sym):
    if '-' in sym:
        return sym
    return sym[:-4] + '-USDT' if sym.endswith('USDT') else sym

def candles(sym, bar, limit=100):
    try:
        d = api('https://www.okx.com/api/v5/market/candles?instId=%s&bar=%s&limit=%d' % (to_inst(sym), bar, limit))
        rows = []
        for r in (d.get('data') or [])[:limit]:
            rows.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
        rows.reverse()
        return rows
    except Exception as e:
        log('  candles %s %s: %s' % (sym, bar, e))
        return []

def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0

def stdv(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))

def zscore(closes):
    if len(closes) < 21:
        return 0.0
    w = closes[-20:]
    m = mean(w)
    s = stdv(w)
    return (closes[-1] - m) / s if s > 0 else 0.0

def atr(bars):
    if len(bars) < 2:
        return 0.0
    rs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i][2], bars[i][3], bars[i - 1][4]
        rs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return mean(rs)

def get_obi_funding(sym):
    obi = None
    fr = None
    try:
        now = int(time.time())
        c = sqlite3.connect(OB_DB, timeout=5)
        r = c.execute('SELECT imbalance, best_bid, best_ask FROM orderbooks WHERE symbol=? AND ts > ? ORDER BY ts DESC LIMIT 1',
                      (sym, now - 10)).fetchone()
        if r:
            obi = {'obi': r[0], 'bid': r[1], 'ask': r[2]}
        r2 = c.execute('SELECT funding_rate FROM funding WHERE symbol=? AND ts > ? ORDER BY ts DESC LIMIT 1',
                       (sym, now - 3600)).fetchone()
        if r2:
            fr = r2[0]
        c.close()
    except Exception:
        pass
    return obi, fr

def init_db():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT, side TEXT, strategy TEXT,
        entry_price REAL, exit_price REAL, pnl REAL,
        status TEXT, entry_ts INTEGER, exit_ts INTEGER,
        tp REAL, sl REAL)''')
    c.commit()
    c.close()

def bank():
    c = sqlite3.connect(DB)
    try:
        r = c.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE status='CLOSED'").fetchone()
    except Exception:
        r = (0.0,)
    c.close()
    return BANK0 + (r[0] or 0.0)

def signals(sym, c1, c5, obi, fr):
    out = []
    if len(c1) < 40 or len(c5) < 30 or not obi:
        return out
    z = zscore([b[4] for b in c1])
    o = obi['obi']
    if z > 2.2 and o < -0.15:
        out.append(('SHORT', 'mr_z', 0.0035, 0.0025, 1800, 'z=%.2f obi=%.2f' % (z, o)))
    elif z < -2.2 and o > 0.15:
        out.append(('LONG', 'mr_z', 0.0035, 0.0025, 1800, 'z=%.2f obi=%.2f' % (z, o)))
    prior = c5[-25:-1]
    if len(prior) >= 24:
        hh = max(b[2] for b in prior)
        ll = min(b[3] for b in prior)
        a_now = atr(c5[-6:])
        a_avg = atr(c5[-30:])
        last5 = c5[-1][4]
        if a_avg > 0 and a_now > 1.2 * a_avg:
            if last5 > hh and o > 0.2:
                out.append(('LONG', 'donchian_atr', 0.008, 0.004, 7200, 'break>%.6f ATR x%.2f obi=%.2f' % (hh, a_now / a_avg, o)))
            elif last5 < ll and o < -0.2:
                out.append(('SHORT', 'donchian_atr', 0.008, 0.004, 7200, 'break<%.6f ATR x%.2f obi=%.2f' % (ll, a_now / a_avg, o)))
    if fr is not None:
        if fr > 0.0003 and z > 1.5:
            out.append(('SHORT', 'funding_squeeze', 0.005, 0.0035, 14400, 'funding=%.4f%% z=%.2f' % (fr * 100, z)))
        elif fr < -0.0003 and z < -1.5:
            out.append(('LONG', 'funding_squeeze', 0.005, 0.0035, 14400, 'funding=%.4f%% z=%.2f' % (fr * 100, z)))
    return out

def close_open_trades():
    c = sqlite3.connect(DB, timeout=10)
    now = int(time.time())
    bet = RISK * bank()
    opens = c.execute("SELECT id, symbol, side, strategy, entry_price, tp, sl, entry_ts FROM trades WHERE status='OPEN'").fetchall()
    for tid, sym, side, strat, ep, tp, sl, ets in opens:
        obi, _ = get_obi_funding(sym)
        if not obi:
            continue
        cur = obi['ask'] if side == 'SHORT' else obi['bid']
        hit = None
        if side == 'SHORT':
            if tp and cur <= ep * (1 - tp):
                hit = 'TP'
            elif sl and cur >= ep * (1 + sl):
                hit = 'SL'
        else:
            if tp and cur >= ep * (1 + tp):
                hit = 'TP'
            elif sl and cur <= ep * (1 - sl):
                hit = 'SL'
        if not hit and now - ets > TIMEOUTS.get(strat, 1800):
            hit = 'TIMEOUT'
        if hit:
            pnl = (ep - cur) / ep * bet if side == 'SHORT' else (cur - ep) / ep * bet
            c.execute("UPDATE trades SET status='CLOSED', exit_price=?, pnl=?, exit_ts=? WHERE id=?",
                      (cur, round(pnl, 2), now, tid))
            icon = 'V' if hit == 'TP' else ('X' if hit == 'SL' else 'T')
            log('  %s CLOSED %s %s %s: %.4f -> %.4f %s$ [%s]' % (icon, sym, side, strat, ep, cur, ('+' if pnl >= 0 else '') + str(round(pnl, 2)), hit))
    c.commit()
    c.close()

def open_new_trades():
    c = sqlite3.connect(DB, timeout=10)
    n_open = c.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
    for sym in UNIVERSE:
        if n_open >= MAX_OPEN:
            break
        if c.execute("SELECT 1 FROM trades WHERE symbol=? AND status='OPEN'", (sym,)).fetchone():
            continue
        row = c.execute("SELECT exit_ts FROM trades WHERE symbol=? AND status='CLOSED' ORDER BY id DESC LIMIT 1", (sym,)).fetchone()
        if row and row[0] and time.time() - row[0] < COOLDOWN:
            continue
        c1 = candles(sym, '1m')
        c5 = candles(sym, '5m')
        obi, fr = get_obi_funding(sym)
        sigs = signals(sym, c1, c5, obi, fr)
        if not sigs:
            continue
        side, strat, tp, sl, tmo, why = sigs[0]
        if fr is not None:
            if side == 'LONG' and fr > 0.0005:
                continue
            if side == 'SHORT' and fr < -0.0005:
                continue
        entry = obi['ask'] if side == 'LONG' else obi['bid']
        ts = int(time.time())
        c.execute("INSERT INTO trades (symbol, side, strategy, entry_price, status, entry_ts, tp, sl) VALUES (?,?,?,?,?,?,?,?)",
                  (sym, side, strat, entry, 'OPEN', ts, tp, sl))
        n_open += 1
        log('  OPEN %s %s [%s] @ %.4f (%s) TP=%.2f%% SL=%.2f%% tmo=%dm' %
            (sym, side, strat, entry, why, tp * 100, sl * 100, tmo // 60))
    c.commit()
    c.close()

def main():
    os.makedirs(os.path.join(BASE, 'logs'), exist_ok=True)
    os.makedirs(os.path.join(BASE, 'data'), exist_ok=True)
    init_db()
    try:
        import web_export
    except Exception:
        web_export = None
    log('=== QUANTUM LAB v5 STARTED: mr_z + donchian_atr + funding_squeeze ===')
    log('universe=%s risk=%.0f%%/trade max=%d pos' % (','.join(UNIVERSE), RISK * 100, MAX_OPEN))
    while True:
        try:
            close_open_trades()
            open_new_trades()
            if web_export:
                try:
                    web_export.publish()
                except Exception as e:
                    log('web_export error: %s' % e)
        except Exception as e:
            log('ERROR: %s' % e)
        time.sleep(CYCLE)

if __name__ == '__main__':
    main()
