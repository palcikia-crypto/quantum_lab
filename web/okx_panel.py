#!/usr/bin/env python3
"""web/okx_panel.py — веб-панель OKX-бота (порт 8102)."""
import os, json, sqlite3, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/okx_paper.db')
TPSL = os.path.join(BASE, 'data/okx_tpsl_by_regime.json')
POL = os.path.join(BASE, 'data/okx_policy.json')
ORACLE = os.path.join(BASE, 'data/oracle.db')

def state():
    s = {'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    # сделки
    c = sqlite3.connect(DB)
    s['trades'] = c.execute("SELECT status, COUNT(*) FROM trades GROUP BY status").fetchall()
    s['open'] = c.execute("SELECT id,symbol,side,strategy,entry_price,tp,sl,entry_ts FROM trades WHERE status='OPEN' ORDER BY id DESC").fetchall()
    s['closed'] = c.execute("SELECT id,symbol,side,strategy,entry_price,exit_price,pnl,win_flag,entry_ts,exit_ts FROM trades WHERE status='CLOSED' ORDER BY id DESC LIMIT 50").fetchall()
    # PnL по стратегиям (все)
    s['pnl_strat'] = c.execute("SELECT strategy, COUNT(*), SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END), ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED' GROUP BY strategy ORDER BY 4 DESC").fetchall()
    # PnL только okx_vwap_rev_30 (новая, актуальная)
    s['pnl_new'] = c.execute("SELECT COUNT(*), SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END), ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED' AND strategy='okx_vwap_rev_30'").fetchone()
    # последние 20 сделок okx_vwap_rev_30
    s['new_trades'] = c.execute("SELECT id,symbol,side,strategy,entry_price,exit_price,pnl,win_flag,entry_ts,exit_ts FROM trades WHERE strategy='okx_vwap_rev_30' ORDER BY id DESC LIMIT 20").fetchall()
    # PnL по парам
    s['pnl_pair'] = c.execute("SELECT symbol, COUNT(*), ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED' GROUP BY symbol ORDER BY 3 DESC").fetchall()
    # итого
    tot = c.execute("SELECT COUNT(*), SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END), ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED'").fetchone()
    s['total'] = {'n': tot[0] or 0, 'wins': tot[1] or 0, 'pnl': tot[2] or 0}
    c.close()
    # by_regime
    try:
        d = json.load(open(TPSL))
        s['by_regime'] = d
    except: s['by_regime'] = {}
    # policy
    try:
        s['policy'] = json.load(open(POL))
    except: s['policy'] = {}
    # режимы
    try:
        c = sqlite3.connect(ORACLE)
        s['regimes'] = c.execute("SELECT symbol, regime, adx FROM regime WHERE ts=(SELECT MAX(ts) FROM regime) ORDER BY symbol").fetchall()
        c.close()
    except: s['regimes'] = []
    return s

HTML = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>OKX Bot v2</title>
<meta http-equiv="refresh" content="30">
<style>
body { font-family: -apple-system, Arial, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
h1 { color: #58a6ff; }
h2 { color: #7ee787; border-bottom: 1px solid #30363d; padding-bottom: 5px; margin-top: 30px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; }
th, td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #21262d; }
th { color: #8b949e; font-weight: 600; }
.win { color: #3fb950; }
.loss { color: #f85149; }
.green { color: #3fb950; }
.red { color: #f85149; }
.gold { color: #d29922; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; margin: 10px 0; }
.big { font-size: 24px; font-weight: bold; }
.row { display: flex; gap: 15px; flex-wrap: wrap; }
.row .card { flex: 1; min-width: 200px; }
</style></head><body>
<h1>⚡ OKX BOT v2</h1>
<p style="color:#8b949e">Paper-торговля · автообновление 30 сек · <span id="ts">__TS__</span></p>

<div class="row">
<div class="card"><div style="color:#8b949e">Всего сделок</div><div class="big">__N__</div></div>
<div class="card"><div style="color:#8b949e">Побед / WR</div><div class="big">__WINS__ / __WR__%</div></div>
<div class="card"><div style="color:#8b949e">PnL</div><div class="big __PNL_CLASS__">$__PNL__</div></div>
<div class="card"><div style="color:#8b949e">Открыто</div><div class="big">__OPEN__</div></div>
</div>

<h2>🏆 НОВЫЕ (okx_vwap_rev_30) — актуальная стратегия</h2>
<div class="row">
<div class="card"><div style="color:#8b949e">Сделок</div><div class="big">__NEW_N__</div></div>
<div class="card"><div style="color:#8b949e">Побед / WR</div><div class="big">__NEW_WINS__ / __NEW_WR__%</div></div>
<div class="card"><div style="color:#8b949e">PnL</div><div class="big __NEW_PNL_CLASS__">$__NEW_PNL__</div></div>
</div>
<table><tr><th>ID</th><th>Пара</th><th>Сторона</th><th>Entry</th><th>Exit</th><th>PnL</th><th>W</th><th>Мин</th></tr>
__NEW_ROWS__
</table>

<h2>📊 По стратегиям (все)</h2>
<table><tr><th>Стратегия</th><th>Сделок</th><th>Побед</th><th>WR</th><th>PnL</th></tr>
__PNL_STRAT__
</table>

<h2>💰 По парам</h2>
<table><tr><th>Пара</th><th>Сделок</th><th>PnL</th></tr>
__PNL_PAIR__
</table>

<h2>📈 Открытые сделки</h2>
<table><tr><th>ID</th><th>Пара</th><th>Сторона</th><th>Стратегия</th><th>Entry</th><th>TP</th><th>SL</th><th>Мин</th></tr>
__OPEN_ROWS__
</table>

<h2>📉 Последние 50 закрытых</h2>
<table><tr><th>ID</th><th>Пара</th><th>Сторона</th><th>Стратегия</th><th>Entry</th><th>Exit</th><th>PnL</th><th>W</th><th>Мин</th></tr>
__CLOSED_ROWS__
</table>

<h2>🎯 by_regime (что торгует)</h2>
<table><tr><th>Пара</th><th>Режим</th><th>Стратегия</th><th>TP</th><th>SL</th><th>Timeout</th></tr>
__BY_REGIME__
</table>

<h2>⚙️ Policy (фильтр)</h2>
<pre>__POLICY__</pre>

<h2>🌊 Режимы рынка</h2>
<table><tr><th>Пара</th><th>Режим</th><th>ADX</th></tr>
__REGIMES__
</table>

</body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        s = state()
        n = s['total']['n']
        wins = s['total']['wins']
        pnl = s['total']['pnl']
        wr = (100.0*wins/n) if n else 0
        pnl_class = 'green' if pnl >= 0 else 'red'
        open_rows = ''.join(
            f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]:.6f}</td>"
            f"<td>{(r[5] or 0)*100:.2f}%</td><td>{(r[6] or 0)*100:.2f}%</td>"
            f"<td>{(time.time()-r[7])/60:.0f}</td></tr>"
            for r in s['open']) or '<tr><td colspan="8">нет открытых</td></tr>'
        closed_rows = ''.join(
            f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]:.6f}</td>"
            f"<td>{r[5]:.6f}</td><td class=\"{'win' if (r[6] or 0)>0 else 'loss'}\">{r[6]:+.2f}</td>"
            f"<td>{'✅' if r[7] else '❌'}</td>"
            f"<td>{(r[9]-r[8])/60:.0f}</td></tr>"
            for r in s['closed']) or '<tr><td colspan="9">нет</td></tr>'
        pnl_strat = ''.join(
            f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{100.0*r[2]/r[1]:.1f}%</td>"
            f"<td class=\"{'win' if r[3]>=0 else 'loss'}\">${r[3]:+.2f}</td></tr>"
            for r in s['pnl_strat']) or '<tr><td colspan="5">нет</td></tr>'
        pnl_pair = ''.join(
            f"<tr><td>{r[0]}</td><td>{r[1]}</td><td class=\"{'win' if r[2]>=0 else 'loss'}\">${r[2]:+.2f}</td></tr>"
            for r in s['pnl_pair']) or '<tr><td colspan="3">нет</td></tr>'
        by_regime = ''.join(
            f"<tr><td>{p}</td><td>{reg}</td><td>{b.get('strategy','?')}</td>"
            f"<td>{(b.get('tp',0) or 0)*100:.2f}%</td><td>{(b.get('sl',0) or 0)*100:.2f}%</td>"
            f"<td>{b.get('timeout_bars',2)}</td></tr>"
            for p, regs in s['by_regime'].get('per_pair', {}).items()
            for reg, b in regs.items()) or '<tr><td colspan="6">нет</td></tr>'
        regimes = ''.join(
            f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]:.1f}</td></tr>"
            for r in s['regimes']) or '<tr><td colspan="3">нет</td></tr>'
        policy = json.dumps(s['policy'], indent=2, ensure_ascii=False)
        # новые (okx_vwap_rev_30)
        nn = s.get('pnl_new') or (0, 0, 0)
        new_n = nn[0] or 0; new_wins = nn[1] or 0; new_pnl = nn[2] or 0
        new_wr = (100.0*new_wins/new_n) if new_n else 0
        new_pnl_class = 'green' if new_pnl >= 0 else 'red'
        new_rows = ''.join(
            f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[4]:.6f}</td>"
            f"<td>{r[5]:.6f}</td><td class=\"{'win' if (r[6] or 0)>0 else 'loss'}\">{r[6]:+.2f}</td>"
            f"<td>{'✅' if r[7] else '❌'}</td>"
            f"<td>{(r[9]-r[8])/60:.0f}</td></tr>"
            for r in s.get('new_trades', []) if r[5]) or '<tr><td colspan=\"8\">нет</td></tr>'
        html = (HTML
                .replace('__TS__', s['ts'])
                .replace('__NEW_N__', str(new_n))
                .replace('__NEW_WINS__', str(new_wins))
                .replace('__NEW_WR__', f'{new_wr:.1f}')
                .replace('__NEW_PNL__', f'{new_pnl:+.2f}')
                .replace('__NEW_PNL_CLASS__', new_pnl_class)
                .replace('__NEW_ROWS__', new_rows)
                .replace('__N__', str(n))
                .replace('__WINS__', str(wins))
                .replace('__WR__', f'{wr:.1f}')
                .replace('__PNL__', f'{pnl:+.2f}')
                .replace('__PNL_CLASS__', pnl_class)
                .replace('__OPEN__', str(len(s['open'])))
                .replace('__PNL_STRAT__', pnl_strat)
                .replace('__PNL_PAIR__', pnl_pair)
                .replace('__OPEN_ROWS__', open_rows)
                .replace('__CLOSED_ROWS__', closed_rows)
                .replace('__BY_REGIME__', by_regime)
                .replace('__POLICY__', policy)
                .replace('__REGIMES__', regimes))
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

if __name__ == '__main__':
    port = 8102
    print(f'OKX panel: http://127.0.0.1:{port}/')
    HTTPServer(('0.0.0.0', port), H).serve_forever()
