#!/usr/bin/env python3
"""okx_bot_scalp.py — СКАЛЬПИНГ: okx_vwap_rev_7, TP 0.3%, SL 0.2%, timeout 30 мин."""
import os, sys, json, sqlite3, time, re
from datetime import datetime
import numpy as np

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))

DB = os.path.join(BASE, 'data/okx_paper_scalp.db')
ACTIVE = os.path.join(BASE, 'data/okx_active_scalp.json')
MARKET = os.path.join(BASE, 'data/market.db')
LOG = os.path.join(BASE, 'logs/okx_bot_scalp.log')

FEE = 0.0015
SLIP = 0.0005
BET = 100
LEVERAGE = 1
COOLDOWN_SEC = 600
TP_DEFAULT = 0.003
SL_DEFAULT = 0.002
TIMEOUT_DEFAULT = 2

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def init_db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT, side TEXT, strategy TEXT,
        entry_price REAL, exit_price REAL, pnl REAL,
        entry_ts INTEGER, exit_ts INTEGER,
        status TEXT DEFAULT 'OPEN', win_flag INTEGER DEFAULT 0,
        tp REAL, sl REAL, timeout_bars INTEGER DEFAULT 2
    )""")
    c.commit(); c.close()

def get_candles(sym, tf='15m', limit=200):
    sym_db = sym.replace('-', '')
    c = sqlite3.connect(MARKET, timeout=10)
    rows = c.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf=? ORDER BY ts DESC LIMIT ?",
                     (sym_db, tf, limit)).fetchall()
    c.close()
    if not rows: return None
    rows = rows[::-1]
    return {
        'ts': np.array([r[0] for r in rows]),
        'o': np.array([r[1] for r in rows]),
        'h': np.array([r[2] for r in rows]),
        'l': np.array([r[3] for r in rows]),
        'c': np.array([r[4] for r in rows]),
        'v': np.array([r[5] for r in rows])
    }

def get_price(sym):
    d = get_candles(sym, '15m', 2)
    return float(d['c'][-1]) if d else None

def get_fn(name):
    import re as _re
    nums = [float(x) for x in _re.findall(r'\d+\.?\d*', name)]
    if name.startswith('okx_vwap_rev_') and nums:
        from okx_mutator import okx_vwap_rev
        return okx_vwap_rev(int(nums[0]))
    if name.startswith('okx_grid_sma_') and nums:
        from okx_grid import okx_grid_sma
        return okx_grid_sma(int(nums[0]))
    return None

def check_signal(strat, sym):
    data = get_candles(sym, '15m', 200)
    if not data or len(data['c']) < 30: return None
    fn = get_fn(strat)
    if not fn: return None
    try:
        up, dn = fn(data['o'], data['h'], data['l'], data['c'], data['v'], {})
        entry = float(data['c'][-1])
        if up[-1]: return ('LONG', entry)
        if dn[-1]: return ('SHORT', entry)
    except Exception as e:
        log(f'  ⚠️ check_signal {strat} {sym}: {e}')
    return None

def close_open_trades():
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT id, symbol, side, entry_price, entry_ts, strategy, tp, sl, timeout_bars FROM trades WHERE status='OPEN'").fetchall()
    now = int(time.time())
    for t_id, sym, side, ep, ets, strat, tp, sl, tb in rows:
        tp = tp or TP_DEFAULT; sl = sl or SL_DEFAULT; tb = int(tb or TIMEOUT_DEFAULT)
        data = get_candles(sym, '15m', 50)
        exit_p = None; reason = None
        if data:
            for j in range(len(data['ts'])):
                if data['ts'][j] < ets: continue
                hi, lo = data['h'][j], data['l'][j]
                if side == 'LONG':
                    if lo <= ep * (1 - sl): exit_p = ep * (1 - sl); reason = 'SL'; break
                    if hi >= ep * (1 + tp): exit_p = ep * (1 + tp); reason = 'TP'; break
                else:
                    if hi >= ep * (1 + sl): exit_p = ep * (1 + sl); reason = 'SL'; break
                    if lo <= ep * (1 - tp): exit_p = ep * (1 - tp); reason = 'TP'; break
        if exit_p is None:
            if (now - ets) >= 900 * tb:
                cur = get_price(sym)
                if not cur: continue
                exit_p = cur; reason = f'timeout_{tb}b'
            else: continue
        move = (exit_p - ep)/ep if side == 'LONG' else (ep - exit_p)/ep
        pnl = (move - FEE - SLIP) * BET * LEVERAGE
        win = 1 if pnl > 0 else 0
        c.execute("UPDATE trades SET exit_price=?, pnl=?, exit_ts=?, status='CLOSED', win_flag=? WHERE id=?",
                  (round(exit_p, 6), round(pnl, 4), now, win, t_id))
        log(f'  {"✅" if win else "❌"} {sym} {side} CLOSED @ {exit_p:.6f} PnL=${pnl:+.2f} ({reason})')
    c.commit(); c.close()

def main():
    init_db()
    log('=== OKX BOT SCALP STARTED ===')
    while True:
        try:
            close_open_trades()
            if not os.path.exists(ACTIVE):
                log('  ⚠️ нет okx_active_scalp.json'); time.sleep(30); continue
            active = json.load(open(ACTIVE)).get('pairs', {})
            log(f'active: {len(active)} пар')
            for key, cfg in active.items():
                sym = cfg.get('symbol')
                strat = cfg.get('strategy')
                tp = cfg.get('tp', TP_DEFAULT)
                sl = cfg.get('sl', SL_DEFAULT)
                tb = cfg.get('timeout', TIMEOUT_DEFAULT)
                if not sym or not strat: continue
                sig = check_signal(strat, sym)
                if not sig: continue
                side, entry = sig
                if not entry: continue
                c = sqlite3.connect(DB)
                exists = c.execute("SELECT 1 FROM trades WHERE symbol=? AND strategy=? AND entry_ts > ? LIMIT 1",
                                   (sym, strat, int(time.time()) - COOLDOWN_SEC)).fetchone()
                if exists: c.close(); continue
                c.close()
                c = sqlite3.connect(DB)
                c.execute("INSERT INTO trades (symbol, side, strategy, entry_price, entry_ts, tp, sl, timeout_bars) VALUES (?,?,?,?,?,?,?,?)",
                          (sym, side, strat, entry, int(time.time()), tp, sl, tb))
                c.commit(); c.close()
                log(f'  🎯 {sym} {side} @ {entry:.6f} ({strat} TP={tp*100:.2f}% SL={sl*100:.2f}% timeout={tb}b)')
        except Exception as e:
            log(f'  ⚠️ {e}')
        time.sleep(18)

if __name__ == '__main__':
    main()
