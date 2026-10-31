#!/usr/bin/env python3
"""pm_bot_v7.py — торгующий V7. Оптимизирован: кеш рынков, сигнал до ask."""
import os, json, time, sqlite3, urllib.request
import numpy as np
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

HOME = os.path.expanduser('~')
ACTIVE = '/data/data/com.termux/files/home/quantum_lab/data/active_strategies.json'
DB = os.path.join(HOME, 'rsbot/pm_v7.db')
PORT = 8101
BET = 5.0
WINDOW_SEC = 300
LOOP_SEC = 20
TIMEOUT = 4

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    try:
        with open(os.path.join(HOME, 'rsbot/pm_v7.log'), 'a') as f: f.write(line+'\n')
    except: pass

def fetch_json(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def load_active():
    try:
        with open(ACTIVE) as f: return json.load(f)
    except: return {'pairs': {}}

def init_db():
    c = sqlite3.connect(DB)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT, side TEXT, strategy TEXT, entry_price REAL, exit_price REAL,
        entry_ts INTEGER, exit_ts INTEGER, pnl REAL, status TEXT, win_flag INTEGER);
    CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
    ''')
    c.execute("INSERT OR IGNORE INTO state VALUES ('equity','1000.0')")
    c.commit(); c.close()

def get_equity():
    c = sqlite3.connect(DB); r = c.execute("SELECT value FROM state WHERE key='equity'").fetchone(); c.close()
    return float(r[0]) if r else 1000.0

_MARKET_CACHE = {}
def get_market(asset, slot):
    key = (asset, slot)
    if key in _MARKET_CACHE: return _MARKET_CACHE[key]
    slug = f'{asset.lower()}-updown-5m-{slot}'
    try:
        r = fetch_json(f'https://gamma-api.polymarket.com/events?slug={slug}')
        if not r or not r[0].get('markets'): return None
        clob = r[0]['markets'][0].get('clobTokenIds')
        if isinstance(clob, str): clob = json.loads(clob)
        if not clob or len(clob) != 2: return None
        m = {'up': clob[0], 'down': clob[1]}
        _MARKET_CACHE[key] = m
        # чистим старые слоты
        for k in list(_MARKET_CACHE):
            if k[1] < slot - 600: del _MARKET_CACHE[k]
        return m
    except: return None

def get_ask(token):
    try:
        ob = fetch_json(f'https://clob.polymarket.com/book?token_id={token}')
        asks = sorted(ob.get('asks', []), key=lambda x: float(x['price']))
        return (float(asks[0]['price']), float(asks[0]['size'])) if asks else None
    except: return None

def get_binance(symbol, limit=100):
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit={limit}'
        d = fetch_json(url, timeout=5)
        return tuple(np.array([float(x[i]) for x in d]) for i in [1,2,3,4,5])
    except: return None

def calc_stoch(h,l,c,p=14):
    n = len(c); st = np.full(n, 50.0)
    for i in range(p, n):
        hh = h[i-p+1:i+1].max(); ll = l[i-p+1:i+1].min()
        if hh > ll: st[i] = (c[i]-ll)/(hh-ll)*100
    return st

def calc_rsi(c, p=14):
    n = len(c); rsi = np.full(n, 50.0)
    for i in range(p, n):
        gains = sum(max(0, c[j]-c[j-1]) for j in range(i-p+1, i+1))
        losses = sum(max(0, c[j-1]-c[j]) for j in range(i-p+1, i+1))
        if losses == 0: rsi[i] = 100
        else: rsi[i] = 100 - 100/(1 + gains/losses)
    return rsi

def sig_stoch_20(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'stoch' not in ind: ind['stoch'] = calc_stoch(h,l,c,14)
    st = ind['stoch']
    for i in range(1, len(c)):
        if st[i-1] < 20 and st[i] >= 20: up[i] = True
        if st[i-1] > 80 and st[i] <= 80: dn[i] = True
    return up, dn

def sig_stoch_30(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'stoch' not in ind: ind['stoch'] = calc_stoch(h,l,c,14)
    st = ind['stoch']
    for i in range(1, len(c)):
        if st[i-1] < 30 and st[i] >= 30: up[i] = True
        if st[i-1] > 70 and st[i] <= 70: dn[i] = True
    return up, dn

def sig_rsi_30_up(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'rsi' not in ind: ind['rsi'] = calc_rsi(c,14)
    r = ind['rsi']
    for i in range(1, len(c)):
        if r[i-1] < 30 and r[i] >= 30: up[i] = True
    return up, dn

STRATEGIES = {'stoch_20': sig_stoch_20, 'stoch_30': sig_stoch_30, 'rsi_30_up': sig_rsi_30_up}
# mean_rev_3 (из strategy_pool)
def sig_mean_rev_3(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool)
    dn = np.zeros(len(c), dtype=bool)
    for i in range(3, len(c)):
        if c[i-1] < c[i-3] and c[i] > c[i-1]: up[i] = True
        if c[i-1] > c[i-3] and c[i] < c[i-1]: dn[i] = True
    return up, dn
STRATEGIES['mean_rev_3'] = sig_mean_rev_3

def open_trade(conn, symbol, side, market, strat_name):
    token = market['up'] if side == 'UP' else market['down']
    book = get_ask(token)
    if not book: return False
    ba, asz = book
    if ba > 0.55 or ba < 0.05:
        log(f'  {symbol}: ask={ba:.3f} вне [0.05, 0.55]'); return False
    if asz < BET / ba:
        log(f'  {symbol}: size={asz:.0f} < {BET/ba:.0f}'); return False
    now = int(time.time())
    cur = conn.cursor()
    if cur.execute("SELECT COUNT(*) FROM trades WHERE symbol=? AND status='OPEN'", (symbol,)).fetchone()[0]:
        return False
    cur.execute("INSERT INTO trades (symbol, side, strategy, entry_price, entry_ts, status) VALUES (?,?,?,?,?,'OPEN')",
                (symbol, side, strat_name, ba, now))
    conn.commit()
    log(f'  🎯 {symbol} {side} @ {ba:.3f} ({strat_name}, BET=${BET})')
    return True

def close_expired(conn):
    cur = conn.cursor(); now = int(time.time())
    for t_id, sym, side, ep, ets in cur.execute("SELECT id, symbol, side, entry_price, entry_ts FROM trades WHERE status='OPEN'").fetchall():
        if now < ets + WINDOW_SEC - 10: continue
        if now > ets + 1800:
            try:
                pd = fetch_json(f'https://api.binance.com/api/v3/ticker/price?symbol={sym}', timeout=5)
                current = float(pd['price']); pnl = -BET
                cur.execute("UPDATE trades SET status='CLOSED', exit_price=?, exit_ts=?, pnl=?, win_flag=0 WHERE id=?",
                            (current, now, pnl, t_id))
                eq = get_equity(); cur.execute("UPDATE state SET value=? WHERE key='equity'", (str(eq+pnl),))
                conn.commit(); log(f'  ⚠️ {sym} {side} FORCED @ {current:.4f} PnL=${pnl:+.2f}')
            except Exception as e: log(f'  forced error {sym}: {e}')
            continue
        try:
            data = fetch_json(f'https://api.binance.com/api/v3/klines?symbol={sym}&interval=5m&limit=100', timeout=10)
            target = (ets // WINDOW_SEC) * WINDOW_SEC
            candle = next((r for r in data if int(r[0])//1000 == target), None)
            if not candle: continue
            wo, wc = float(candle[1]), float(candle[4])
            win = (wc > wo) if side == 'UP' else (wc < wo)
            shares = BET / ep; fee = 0.07 * min(ep, 1-ep) * BET
            pnl = (shares - BET - fee) if win else -BET
            cur.execute("UPDATE trades SET status='CLOSED', exit_price=?, exit_ts=?, pnl=?, win_flag=? WHERE id=?",
                        (wc, now, pnl, int(win), t_id))
            eq = get_equity(); cur.execute("UPDATE state SET value=? WHERE key='equity'", (str(eq+pnl),))
            conn.commit(); log(f'  {"✅" if win else "❌"} {sym} {side} CLOSED @ {wc:.4f} PnL=${pnl:+.2f}')
        except Exception as e: log(f'  close error: {e}')

def scan_and_trade(conn):
    active = load_active(); pairs = active.get('pairs', {})
    if not pairs: log('active пуст'); return
    slot = (int(time.time()) // WINDOW_SEC) * WINDOW_SEC
    ind = {}; signals = 0; checked = 0
    for key, cfg in pairs.items():
        if not cfg.get('trade'): continue
        sym = cfg.get('symbol', key.split('_')[0])
        tf = cfg.get('tf', '15m')
        strat_name = cfg.get('strategy')
        if strat_name not in STRATEGIES: continue
        asset = sym.replace('USDT', '')
        data = get_binance(sym, 100)
        if not data: log(f'{sym}: свечи недоступны'); continue
        checked += 1
        o,h,l,c,v = data
        up, dn = STRATEGIES[strat_name](o,h,l,c,v,ind)
        if not (up[-1] or dn[-1]):
            log(f'{sym}: сигнала нет ({strat_name})'); continue
        signals += 1
        side = 'UP' if up[-1] else 'DOWN'
        log(f'{sym}: 🟢 сигнал {side} ({strat_name})')
        market = get_market(asset, slot)
        if not market: log(f'{sym}: рынок не найден (slot={slot})'); continue
        open_trade(conn, sym, side, market, strat_name)
    log(f'цикл: проверено {checked}, сигналов {signals}')

HTML_PANEL = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V7 QUANTUM LAB</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
body{background:linear-gradient(135deg,#0a0a1a 0%,#1a1a2e 50%,#16213e 100%);min-height:100vh;color:#e0e0e0;padding:20px}
.container{max-width:1200px;margin:0 auto}
h1{font-size:1.8rem;font-weight:700;background:linear-gradient(90deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
.subtitle{color:#888;font-size:.85rem;margin-bottom:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}
.card{background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:20px;transition:transform .2s,box-shadow .2s}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,212,255,0.1)}
.card-label{font-size:.75rem;text-transform:uppercase;letter-spacing:.5px;color:#888;margin-bottom:8px}
.card-value{font-size:1.6rem;font-weight:700;color:#fff}
.card-value.green{color:#00e676}
.card-value.red{color:#ff5252}
.card-value.blue{color:#00d4ff}
.section-title{font-size:1rem;font-weight:600;margin-bottom:12px;color:#ccc}
.table-wrap{background:rgba(255,255,255,0.03);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;overflow:hidden;margin-bottom:24px}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:12px 16px;font-size:.7rem;text-transform:uppercase;letter-spacing:.5px;color:#888;border-bottom:1px solid rgba(255,255,255,0.06);background:rgba(0,0,0,0.2)}
td{padding:12px 16px;font-size:.85rem;border-bottom:1px solid rgba(255,255,255,0.04)}
tr:last-child td{border-bottom:none}
.badge{padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;display:inline-block}
.badge.golden{background:rgba(0,230,118,0.15);color:#00e676}
.badge.watch{background:rgba(255,193,7,0.15);color:#ffc107}
.badge.trade{background:rgba(0,212,255,0.15);color:#00d4ff}
.badge.notrade{background:rgba(255,255,255,0.05);color:#666}
.updated{text-align:center;color:#555;font-size:.7rem;margin-top:20px}
.refresh-btn{background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.3);color:#00d4ff;padding:8px 20px;border-radius:8px;cursor:pointer;font-size:.8rem;margin-top:12px;transition:all .2s}
.refresh-btn:hover{background:rgba(0,212,255,0.2)}
@media(max-width:600px){body{padding:12px}h1{font-size:1.3rem}.grid{grid-template-columns:1fr 1fr}.card{padding:14px}.card-value{font-size:1.2rem}td,th{padding:8px 10px;font-size:.75rem}}
</style>
</head>
<body>
<div class="container">
<h1>⚡ V7 QUANTUM LAB</h1>
<p class="subtitle">Торговая панель · автообновление</p>
<div class="grid">
<div class="card"><div class="card-label">Equity</div><div class="card-value blue" id="equity">—</div></div>
<div class="card"><div class="card-label">PnL</div><div class="card-value green" id="pnl">—</div></div>
<div class="card"><div class="card-label">Сделок</div><div class="card-value" id="trades">—</div></div>
<div class="card"><div class="card-label">Открыто</div><div class="card-value" id="open">—</div></div>
</div>
<div class="section-title">📊 Активные стратегии</div>
<div class="table-wrap">
<table>
<thead><tr><th>Пара</th><th>Стратегия</th><th>WR</th><th>Вердикт</th><th>Торгует</th></tr></thead>
<tbody id="strategy-body"><tr><td colspan="5" style="text-align:center;color:#666">Загрузка...</td></tr></tbody>
</table>
</div>
<p class="updated" id="updated">—</p>
<button class="refresh-btn" onclick="loadData()">🔄 Обновить</button>
</div>
<script>
async function loadData(){
  try{
    const r=await fetch('/api');const d=await r.json();
    document.getElementById('equity').textContent='$'+d.equity.toFixed(2);
    const pnlEl=document.getElementById('pnl');pnlEl.textContent='$'+d.pnl.toFixed(2);pnlEl.className='card-value '+(d.pnl>=0?'green':'red');
    document.getElementById('trades').textContent=d.trades;
    document.getElementById('open').textContent=d.open;
    document.getElementById('updated').textContent='Обновлено: '+new Date(d.updated).toLocaleString('ru-RU');
    const tbody=document.getElementById('strategy-body');
    if(d.active&&Object.keys(d.active).length){
      tbody.innerHTML=Object.values(d.active).map(s=>`<tr>
        <td><strong>${s.symbol}</strong> <span style="color:#666">${s.tf}</span></td>
        <td>${s.strategy}</td>
        <td>${s.wr}%</td>
        <td><span class="badge ${s.verdict==='GOLDEN'?'golden':'watch'}">${s.verdict}</span></td>
        <td><span class="badge ${s.trade?'trade':'notrade'}">${s.trade?'ДА':'НЕТ'}</span></td>
      </tr>`).join('');
    }else{tbody.innerHTML='<tr><td colspan="5" style="text-align:center;color:#666">Нет активных стратегий</td></tr>'}
  }catch(e){document.getElementById('updated').textContent='Ошибка загрузки: '+e.message}
}
loadData();setInterval(loadData,5000);
</script>
</body>
</html>"""

class StatusHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == '/api':
            try:
                c = sqlite3.connect(DB)
                n = c.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2) FROM trades").fetchone()
                op = c.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
                c.close(); active = load_active()
                body = json.dumps({'equity': round(get_equity(),2), 'trades': n[0], 'pnl': n[1],
                                   'open': op, 'active': active.get('pairs', {}),
                                   'updated': active.get('updated_at')}, ensure_ascii=False, indent=2)
                self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8')
                self.end_headers(); self.wfile.write(body.encode())
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        else:
            html = HTML_PANEL.encode()
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers(); self.wfile.write(html)


def main():
    init_db()
    log(f'🚀 V7 TRADING | BET=${BET} | WINDOW={WINDOW_SEC}s | порт {PORT}')
    threading.Thread(target=lambda: HTTPServer(('127.0.0.1', PORT), StatusHandler).serve_forever(), daemon=True).start()
    log(f'🌐 панель: http://127.0.0.1:{PORT}')
    conn = sqlite3.connect(DB)
    while True:
        try:
            close_expired(conn)
            scan_and_trade(conn)
        except Exception as e: log(f'ERROR: {e}')
        time.sleep(LOOP_SEC)

if __name__ == '__main__': main()
