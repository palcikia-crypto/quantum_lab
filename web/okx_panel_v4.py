#!/usr/bin/env python3
"""okx_panel_v4.py — мобильная панель для v4 скальпера (порт 8104)."""
import os, sys, json, sqlite3
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser('~/quantum_lab')
DB_V4 = os.path.join(BASE, 'data/okx_paper_v4.db')
DB_OB = os.path.join(BASE, 'data/orderbook.db')
PORT = 8104

def q(db, sql, args=()):
    try:
        c = sqlite3.connect(db, timeout=5)
        rows = c.execute(sql, args).fetchall()
        c.close()
        return rows
    except Exception:
        return []

def build_data():
    total = q(DB_V4, "SELECT COUNT(*) FROM trades WHERE status='CLOSED'")
    wins = q(DB_V4, "SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0")
    pnl = q(DB_V4, "SELECT ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED'")
    total_n = total[0][0] if total else 0
    wins_n = wins[0][0] if wins else 0
    pnl_v = pnl[0][0] if pnl and pnl[0][0] else 0
    wr = round(100.0 * wins_n / total_n, 1) if total_n else 0

    opens = q(DB_V4, """SELECT id, symbol, side, strategy, ROUND(entry_price,6) ep,
                        datetime(entry_ts,'unixepoch','localtime') t
                        FROM trades WHERE status='OPEN' ORDER BY id DESC""")
    open_trades = [{'id': r[0], 'symbol': r[1], 'side': r[2],
                    'strategy': r[3], 'entry': r[4], 'time': r[5]} for r in opens]

    recent = q(DB_V4, """SELECT id, symbol, side, strategy, ROUND(pnl,2) pnl,
                         datetime(exit_ts,'unixepoch','localtime') t
                         FROM trades WHERE status='CLOSED'
                         ORDER BY id DESC LIMIT 20""")
    recent_trades = [{'id': r[0], 'symbol': r[1], 'side': r[2],
                      'strategy': r[3], 'pnl': r[4], 'time': r[5]} for r in recent]

    # funding
    funding = q(DB_OB, """SELECT symbol, funding_rate, datetime(ts,'unixepoch','localtime') t
                         FROM funding WHERE ts > strftime('%s','now') - 600
                         ORDER BY ts DESC LIMIT 10""")
    funding_list = [{'symbol': r[0], 'funding': r[1], 'time': r[2]} for r in funding]

    # chart
    pnl_hist = q(DB_V4, """SELECT datetime(exit_ts,'unixepoch','localtime') t, pnl
                          FROM trades WHERE status='CLOSED' ORDER BY exit_ts ASC""")
    cum = 0; chart = []
    for r in pnl_hist:
        cum += r[1] if r[1] else 0
        chart.append({'t': r[0], 'v': round(cum, 2)})

    return {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total': total_n, 'wins': wins_n, 'wr': wr, 'pnl': pnl_v,
        'open_count': len(open_trades),
        'open_trades': open_trades, 'recent': recent_trades,
        'funding': funding_list,
        'chart': chart[-100:],
    }

HTML = r'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#0a0e1a">
<title>⚡ OKX v4 Scalper — OBI SHORT</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root { --bg:#0a0e1a;--bg2:#121829;--card:#1a2138;--accent:#00d9ff;--accent2:#7c3aed;--green:#10b981;--red:#ef4444;--text:#e5e7eb;--muted:#6b7280;--border:rgba(255,255,255,0.05); }
* { margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
html, body { overflow-x:hidden; }
body { font-family:-apple-system,'Segoe UI',Roboto,sans-serif; background:var(--bg); color:var(--text); min-height:100vh; padding:10px; font-size:14px; }
.header { background:linear-gradient(135deg,var(--bg2),#1a2138); border:1px solid rgba(0,217,255,0.2); border-radius:14px; padding:14px; margin-bottom:10px; box-shadow:0 4px 20px rgba(0,217,255,0.1); }
.header h1 { font-size:18px; display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600; background:rgba(0,217,255,0.15); color:var(--accent); }
.badge.live { background:rgba(16,185,129,0.15); color:var(--green); }
.ts { color:var(--muted); font-size:11px; margin-top:4px; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:10px; }
.card { background:var(--card); border-radius:12px; padding:12px; border:1px solid var(--border); }
.card .label { color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:0.3px; }
.card .value { font-size:18px; font-weight:700; margin-top:4px; }
.value.green { color:var(--green); }
.value.red { color:var(--red); }
.value.accent { color:var(--accent); }
.section { background:var(--card); border-radius:12px; margin-bottom:8px; border:1px solid var(--border); overflow:hidden; }
.section h2 { font-size:13px; padding:12px; color:var(--accent); cursor:pointer; user-select:none; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid transparent; }
.section.open h2 { border-bottom-color:var(--border); }
.section h2::after { content:'▼'; font-size:10px; color:var(--muted); transition:transform 0.2s; }
.section.open h2::after { transform:rotate(180deg); }
.section .body { display:none; }
.section.open .body { display:block; }
.table-wrap { overflow-x:auto; -webkit-overflow-scrolling:touch; }
table { width:100%; border-collapse:collapse; font-size:11px; min-width:320px; }
th { text-align:left; padding:8px 10px; color:var(--muted); border-bottom:1px solid rgba(255,255,255,0.1); font-weight:600; text-transform:uppercase; font-size:9px; white-space:nowrap; }
td { padding:8px 10px; border-bottom:1px solid rgba(255,255,255,0.03); white-space:nowrap; }
.pill { display:inline-block; padding:2px 7px; border-radius:6px; font-size:9px; font-weight:600; }
.pill.short { background:rgba(239,68,68,0.15); color:var(--red); }
.pill.long { background:rgba(16,185,129,0.15); color:var(--green); }
.empty { color:var(--muted); font-style:italic; padding:14px; text-align:center; font-size:12px; }
.chart-wrap { position:relative; height:160px; padding:8px; }
.footer { text-align:center; color:var(--muted); font-size:10px; padding:12px; }
@media (min-width:640px) { .grid { grid-template-columns:repeat(4,1fr); gap:12px; } .card .value { font-size:24px; } .header h1 { font-size:24px; } .section h2 { font-size:16px; } .chart-wrap { height:220px; } }
</style>
</head>
<body>
<div class="header">
  <h1>⚡ OKX v4 Scalper <span class="badge live">OBI SHORT</span> <span class="badge">FUNDING</span></h1>
  <div class="ts">Автообновление 5 сек · <span id="ts">—</span></div>
</div>
<div class="grid">
  <div class="card"><div class="label">Всего</div><div class="value accent" id="total">—</div></div>
  <div class="card"><div class="label">WR</div><div class="value" id="wr">—</div></div>
  <div class="card"><div class="label">PnL</div><div class="value" id="pnl">—</div></div>
  <div class="card"><div class="label">Открыто</div><div class="value accent" id="open">—</div></div>
</div>
<div class="section open"><h2>📈 Кумулятивный PnL</h2><div class="body"><div class="chart-wrap"><canvas id="chart"></canvas></div></div></div>
<div class="section open"><h2>💼 Открытые сделки</h2><div class="body"><div class="table-wrap"><table><thead><tr><th>ID</th><th>Пара</th><th>Сторона</th><th>Entry</th><th>Время</th></tr></thead><tbody id="opens"><tr><td colspan="5" class="empty">нет открытых</td></tr></tbody></table></div></div></div>
<div class="section"><h2>💰 Funding Rate (SWAP)</h2><div class="body"><div class="table-wrap"><table><thead><tr><th>Пара</th><th>Funding</th><th>Время</th></tr></thead><tbody id="funding"><tr><td colspan="3" class="empty">—</td></tr></tbody></table></div></div></div>
<div class="section"><h2>📉 Последние 20 сделок</h2><div class="body"><div class="table-wrap"><table><thead><tr><th>ID</th><th>Пара</th><th>Сторона</th><th>PnL</th><th>Время</th></tr></thead><tbody id="recent"><tr><td colspan="5" class="empty">—</td></tr></tbody></table></div></div></div>
<div class="footer">OKX v4 Scalper · OBI SHORT · Funding · порт 8104</div>
<script>
let chart = null;
document.querySelectorAll('.section h2').forEach(h => h.addEventListener('click', () => h.parentElement.classList.toggle('open')));
async function load() {
  try {
    const r = await fetch('/api');
    const d = await r.json();
    document.getElementById('ts').textContent = d.ts;
    document.getElementById('total').textContent = d.total;
    document.getElementById('wr').textContent = d.wr + '%';
    document.getElementById('wr').className = 'value ' + (d.wr >= 50 ? 'green' : 'red');
    document.getElementById('pnl').textContent = '$' + (d.pnl >= 0 ? '+' : '') + d.pnl.toFixed(2);
    document.getElementById('pnl').className = 'value ' + (d.pnl >= 0 ? 'green' : 'red');
    document.getElementById('open').textContent = d.open_count;
    const op = document.getElementById('opens');
    op.innerHTML = d.open_trades.length ? d.open_trades.map(x =>
      '<tr><td>'+x.id+'</td><td>'+x.symbol+'</td><td><span class="pill short">'+x.side+'</span></td><td>'+x.entry+'</td><td>'+x.time+'</td></tr>'
    ).join('') : '<tr><td colspan="5" class="empty">нет открытых</td></tr>';
    const fu = document.getElementById('funding');
    fu.innerHTML = d.funding.length ? d.funding.map(x =>
      '<tr><td>'+x.symbol+'</td><td style="color:'+(x.funding>=0?'var(--green)':'var(--red)')+'">'+x.funding.toFixed(6)+'</td><td>'+x.time+'</td></tr>'
    ).join('') : '<tr><td colspan="3" class="empty">—</td></tr>';
    const rc = document.getElementById('recent');
    rc.innerHTML = d.recent.length ? d.recent.map(x =>
      '<tr><td>'+x.id+'</td><td>'+x.symbol+'</td><td><span class="pill short">'+x.side+'</span></td><td style="color:'+(x.pnl>=0?'var(--green)':'var(--red)')+'">$'+(x.pnl>=0?'+':'')+x.pnl+'</td><td>'+x.time+'</td></tr>'
    ).join('') : '<tr><td colspan="5" class="empty">—</td></tr>';
    if (chart) chart.destroy();
    const ctx = document.getElementById('chart').getContext('2d');
    chart = new Chart(ctx, { type:'line', data:{ labels:d.chart.map(x=>x.t), datasets:[{ label:'PnL $', data:d.chart.map(x=>x.v), borderColor:'#00d9ff', backgroundColor:'rgba(0,217,255,0.1)', fill:true, tension:0.3, pointRadius:0, borderWidth:2 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{display:false} }, scales:{ x:{display:false}, y:{ grid:{color:'rgba(255,255,255,0.05)'}, ticks:{color:'#6b7280'} } } } });
  } catch(e) { console.error(e); }
}
load();
setInterval(load, 5000);
</script>
</body>
</html>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api':
            body = json.dumps(build_data(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == '__main__':
    print(f'⚡ OKX Panel v4: http://127.0.0.1:{PORT}/')
    HTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
