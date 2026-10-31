#!/usr/bin/env python3
"""panel_scalp.py — веб-панель для скальпинг-бота."""
import os, json, sqlite3
from datetime import datetime
from flask import Flask, jsonify, render_template_string

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/okx_paper_scalp.db')
ACTIVE = os.path.join(BASE, 'data/okx_active_scalp.json')
PORT = 8103

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#0a0a0f">
<title>⚡ OKX SCALP</title>
<style>
:root{--bg:#0a0a0f;--surface:#12121a;--border:#1e1e2e;--text:#e8e8f0;--muted:#6b6b80;--green:#00e676;--red:#ff3d71;--blue:#448aff;--purple:#b388ff;--orange:#ffab40}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:14px;line-height:1.5;padding:12px;padding-bottom:80px}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)}
.header h1{font-size:18px;font-weight:700;background:linear-gradient(135deg,var(--orange),var(--red));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header .status{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:12px}
.card h2{font-size:13px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center}
.stat .num{font-size:22px;font-weight:800}
.stat .lbl{font-size:11px;color:var(--muted);margin-top:2px;text-transform:uppercase;letter-spacing:.5px}
.green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}.orange{color:var(--orange)}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:var(--muted);font-weight:600;padding:6px 4px;border-bottom:1px solid var(--border);font-size:11px;text-transform:uppercase}
td{padding:8px 4px;border-bottom:1px solid var(--border)}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600}
.badge.open{background:rgba(255,171,64,.15);color:var(--orange)}
.badge.closed{background:rgba(107,107,128,.15);color:var(--muted)}
.badge.long{background:rgba(0,230,118,.15);color:var(--green)}
.badge.short{background:rgba(255,61,113,.15);color:var(--red)}
.refresh{position:fixed;bottom:20px;right:20px;background:var(--orange);color:#fff;border:none;border-radius:50%;width:56px;height:56px;font-size:24px;cursor:pointer;box-shadow:0 4px 20px rgba(255,171,64,.4);transition:transform .2s}
.refresh:active{transform:scale(.9)}
.empty{text-align:center;color:var(--muted);padding:20px;font-size:13px}
</style>
</head>
<body>
<div class="header">
  <h1>⚡ OKX SCALP</h1>
  <div class="status"><span class="dot"></span><span id="time">live</span></div>
</div>
<div class="grid">
  <div class="stat"><div class="num" id="pnl">—</div><div class="lbl">PnL</div></div>
  <div class="stat"><div class="num" id="trades">—</div><div class="lbl">Сделок</div></div>
  <div class="stat"><div class="num" id="wr">—</div><div class="lbl">Winrate</div></div>
  <div class="stat"><div class="num" id="open">—</div><div class="lbl">Открыто</div></div>
</div>
<div class="card">
  <h2>Скальпинг-пары (4)</h2>
  <table><thead><tr><th>Пара</th><th>Стратегия</th><th>TP</th><th>SL</th></tr></thead>
  <tbody id="pairs"></tbody></table>
</div>
<div class="card">
  <h2>Открытые</h2>
  <table><thead><tr><th>Пара</th><th>Сторона</th><th>Вход</th><th>Время</th></tr></thead>
  <tbody id="openTrades"></tbody></table>
</div>
<div class="card">
  <h2>Последние 15</h2>
  <table><thead><tr><th>Пара</th><th>Сторона</th><th>PnL</th><th>Статус</th></tr></thead>
  <tbody id="history"></tbody></table>
</div>
<button class="refresh" onclick="load()">↻</button>
<script>
function fmt(n){return n==null?'—':(n>0?'+':'')+n.toFixed(2)}
function cls(n){return n>0?'green':(n<0?'red':'')}
async function load(){
  try{
    const r = await fetch('/api/data');
    const d = await r.json();
    document.getElementById('pnl').textContent = fmt(d.total_pnl);
    document.getElementById('pnl').className = 'num '+cls(d.total_pnl);
    document.getElementById('trades').textContent = d.total_trades;
    document.getElementById('wr').textContent = d.wr+'%';
    document.getElementById('wr').className = 'num '+(d.wr>=50?'green':'red');
    document.getElementById('open').textContent = d.open_count;
    document.getElementById('time').textContent = new Date().toLocaleTimeString('ru-RU');
    let ph='';
    for(const p of d.pairs){ph+=`<tr><td>${p.symbol}</td><td class="blue">${p.strategy}</td><td>${(p.tp*100).toFixed(2)}%</td><td>${(p.sl*100).toFixed(2)}%</td></tr>`}
    document.getElementById('pairs').innerHTML = ph || '<tr><td colspan="4" class="empty">нет</td></tr>';
    let oh='';
    for(const t of d.open){oh+=`<tr><td>${t.symbol}</td><td><span class="badge ${t.side.toLowerCase()}">${t.side}</span></td><td>${t.ep}</td><td>${t.dt}</td></tr>`}
    document.getElementById('openTrades').innerHTML = oh || '<tr><td colspan="4" class="empty">нет открытых</td></tr>';
    let hh='';
    for(const t of d.history){hh+=`<tr><td>${t.symbol}</td><td><span class="badge ${t.side.toLowerCase()}">${t.side}</span></td><td class="${cls(t.pnl)}">${fmt(t.pnl)}</td><td><span class="badge ${t.status.toLowerCase()}">${t.status}</span></td></tr>`}
    document.getElementById('history').innerHTML = hh || '<tr><td colspan="4" class="empty">нет сделок</td></tr>';
  }catch(e){console.error(e)}
}
load(); setInterval(load, 5000);
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/data')
def api_data():
    pairs = []
    if os.path.exists(ACTIVE):
        d = json.load(open(ACTIVE))
        for k, v in d.get('pairs', {}).items():
            pairs.append({'symbol': v.get('symbol'), 'strategy': v.get('strategy'), 'tp': v.get('tp', 0.003), 'sl': v.get('sl', 0.002)})
    total_trades = 0; total_pnl = 0.0; wr = 0.0; open_count = 0
    open_trades = []; history = []
    if os.path.exists(DB):
        c = sqlite3.connect(DB, timeout=5)
        row = c.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2), ROUND(100.0*SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END)/MAX(COUNT(*),1),1) FROM trades WHERE status='CLOSED'").fetchone()
        total_trades = row[0] or 0; total_pnl = row[1] or 0.0; wr = row[2] or 0.0
        open_count = c.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
        open_rows = c.execute("SELECT symbol, side, ROUND(entry_price,4), datetime(entry_ts,'unixepoch','localtime') FROM trades WHERE status='OPEN' ORDER BY entry_ts DESC").fetchall()
        open_trades = [{'symbol': r[0], 'side': r[1], 'ep': r[2], 'dt': r[3]} for r in open_rows]
        hist_rows = c.execute("SELECT symbol, side, ROUND(pnl,2), status FROM trades ORDER BY entry_ts DESC LIMIT 15").fetchall()
        history = [{'symbol': r[0], 'side': r[1], 'pnl': r[2], 'status': r[3]} for r in hist_rows]
        c.close()
    return jsonify({'pairs': pairs, 'total_trades': total_trades, 'total_pnl': total_pnl, 'wr': wr, 'open_count': open_count, 'open': open_trades, 'history': history})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
