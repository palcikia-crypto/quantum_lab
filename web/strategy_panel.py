#!/usr/bin/env python3
"""strategy_panel.py — панель ТОЛЬКО для strategy_bot (грааль)."""
import os, json, sqlite3, subprocess
from datetime import datetime
from flask import Flask, render_template_string

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/strategy_paper.db')
app = Flask(__name__)

def get_stats():
    try:
        c = sqlite3.connect(DB)
        r = c.execute("""SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2),
                         ROUND(100.0*SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END)/COUNT(*),1)
                         FROM trades WHERE status='CLOSED'""").fetchone()
        open_n = c.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
        c.close()
        return {'n': r[0] or 0, 'pnl': r[1] or 0, 'wr': r[2] or 0, 'open': open_n}
    except: return {'n': 0, 'pnl': 0, 'wr': 0, 'open': 0}

def get_trades(limit=20):
    try:
        c = sqlite3.connect(DB)
        rows = c.execute("""SELECT symbol, strategy, side, entry_price, exit_price, pnl,
                            status, entry_ts, exit_ts
                            FROM trades ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
        c.close()
        return rows
    except: return []

def get_gold():
    try:
        d = json.load(open(os.path.join(BASE, 'data/evolution.json')))
        gold = [s for s in d.get('top', []) if s.get('wr', 0) >= 55 and s.get('n', 0) >= 100]
        return sorted(gold, key=lambda x: x.get('wr', 0), reverse=True)[:10]
    except: return []

def get_bot_alive():
    r = subprocess.run(['pgrep', '-f', 'strategy_bot'], capture_output=True, text=True)
    return bool(r.stdout.strip())

HTML = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Strategy Bot</title><style>
:root{--bg:#0a0a0f;--surface:#12121a;--border:#1e1e2e;--text:#e4e4ec;--muted:#71717a;--green:#10b981;--red:#ef4444;--amber:#f59e0b;--blue:#3b82f6}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;padding:20px;line-height:1.5}
h1{font-size:24px;font-weight:700;margin-bottom:4px}
.subtitle{color:var(--muted);font-size:13px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:20px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px}
.card-label{font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:4px}
.card-value{font-size:28px;font-weight:700;font-variant-numeric:tabular-nums}
.card-value.green{color:var(--green)}.card-value.red{color:var(--red)}.card-value.amber{color:var(--amber)}
.card-sub{font-size:11px;color:var(--muted);margin-top:2px}
.section{margin-bottom:20px}
.section-title{font-size:15px;font-weight:600;margin-bottom:10px;display:flex;align-items:center;gap:8px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);padding:8px 10px;border-bottom:1px solid var(--border)}
td{padding:8px 10px;font-size:13px;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
.badge{display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:600;text-transform:uppercase}
.badge.green{background:rgba(16,185,129,0.12);color:var(--green);border:1px solid rgba(16,185,129,0.2)}
.badge.red{background:rgba(239,68,68,0.12);color:var(--red);border:1px solid rgba(239,68,68,0.2)}
.badge.amber{background:rgba(245,158,11,0.12);color:var(--amber);border:1px solid rgba(245,158,11,0.2)}
.badge.blue{background:rgba(59,130,246,0.12);color:var(--blue);border:1px solid rgba(59,130,246,0.2)}
.dot{width:6px;height:6px;border-radius:50%;display:inline-block}.dot.green{background:var(--green)}.dot.red{background:var(--red)}
.footer{color:var(--muted);font-size:11px;margin-top:20px;text-align:center}
.live{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
</style></head><body>
<h1>🎯 Strategy Bot</h1>
<div class="subtitle">Торгует по граалю из evolution.json · <span class="live">{{ '🟢 LIVE' if alive else '🔴 STOPPED' }}</span> · {{ now }}</div>

<div class="grid">
<div class="card"><div class="card-label">PnL</div><div class="card-value {{ 'green' if stats.pnl >= 0 else 'red' }}">{{ '%+.2f'|format(stats.pnl) }}</div><div class="card-sub">$ за всё время</div></div>
<div class="card"><div class="card-label">Закрыто</div><div class="card-value">{{ stats.n }}</div><div class="card-sub">сделок</div></div>
<div class="card"><div class="card-label">Win Rate</div><div class="card-value {{ 'green' if stats.wr >= 50 else 'amber' if stats.wr >= 40 else 'red' }}">{{ stats.wr }}%</div><div class="card-sub">процент побед</div></div>
<div class="card"><div class="card-label">Открыто</div><div class="card-value amber">{{ stats.open }}</div><div class="card-sub">сейчас в позиции</div></div>
</div>

<div class="section"><div class="section-title">📊 Последние сделки</div><table>
<thead><tr><th>Время</th><th>Символ</th><th>Сторона</th><th>Вход</th><th>Выход</th><th>PnL</th><th>Статус</th></tr></thead><tbody>
{% for t in trades %}
<tr>
<td>{{ t[7]|int|timestamp if t[7] else '-' }}</td>
<td>{{ t[0] }}</td>
<td><span class="badge {{ 'blue' if t[2]=='LONG' else 'amber' }}">{{ t[2] }}</span></td>
<td>{{ '%.2f'|format(t[3]) }}</td>
<td>{{ '%.2f'|format(t[4]) if t[4] else '-' }}</td>
<td class="{{ 'green' if t[5] and t[5] > 0 else 'red' if t[5] and t[5] < 0 else '' }}">{{ '%+.2f'|format(t[5]) if t[5] else '-' }}</td>
<td>{% if t[6]=='OPEN' %}<span class="badge amber">OPEN</span>{% else %}<span class="badge green">CLOSED</span>{% endif %}</td>
</tr>
{% endfor %}
</tbody></table></div>

<div class="section"><div class="section-title">🏆 Все граали (кандидаты)</div><table>
<thead><tr><th>Символ</th><th>Стратегия</th><th>WR</th><th>n</th><th>Exp</th></tr></thead><tbody>
{% for g in gold %}
<tr><td>{{ g.symbol }}</td><td>{{ g.strategy }}</td><td><span class="badge green">{{ g.wr }}%</span></td><td>{{ g.n }}</td><td>{{ '%.5f'|format(g.get('expectancy', 0)) }}</td></tr>
{% endfor %}
</tbody></table></div>

<div class="footer">Strategy Bot · {{ now }}</div>
</body></html>"""

# Фильтр для timestamp
def _fmt_ts(ts):
    if not ts: return '-'
    return datetime.fromtimestamp(int(ts)).strftime('%H:%M')

@app.template_filter('timestamp')
def timestamp_filter(ts):
    return _fmt_ts(ts)

@app.route('/')
def index():
    return render_template_string(HTML,
        now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        stats=get_stats(),
        trades=get_trades(20),
        gold=get_gold(),
        alive=get_bot_alive()
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
