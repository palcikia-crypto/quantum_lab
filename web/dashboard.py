#!/usr/bin/env python3
"""dashboard.py — полный мобильный дашборд всей системы."""
import os, json, sqlite3, subprocess
from datetime import datetime
from flask import Flask, render_template_string

BASE = os.path.expanduser('~/quantum_lab')
RSBOT = os.path.expanduser('~/rsbot')
app = Flask(__name__)

# ============ СБОР ДАННЫХ ============

def q(db, sql, params=()):
    """Безопасный запрос."""
    try:
        c = sqlite3.connect(db, timeout=5)
        r = c.execute(sql, params).fetchone()
        c.close()
        return r
    except: return None

def get_okx():
    db = os.path.join(BASE, 'data/okx_paper_v4.db')
    r = q(db, "SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2), ROUND(100.0*SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END)/COUNT(*),1) FROM trades WHERE status='CLOSED'")
    open_n = q(db, "SELECT COUNT(*) FROM trades WHERE status='OPEN'")
    return {'n': r[0] if r else 0, 'pnl': r[1] if r else 0, 'wr': r[2] if r else 0, 'open': open_n[0] if open_n else 0}

def get_poly():
    total = 0; n = 0; bots = []
    for db_name in ['pm_bot.db', 'pm_v4.db', 'pm_v5.db', 'pm_v6.db']:
        p = os.path.join(RSBOT, db_name)
        if not os.path.exists(p): continue
        r = q(p, "SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2) FROM trades WHERE status='CLOSED'")
        if r:
            total += r[1] or 0; n += r[0] or 0
            bots.append({'name': db_name.replace('.db',''), 'pnl': r[1] or 0, 'n': r[0] or 0})
    return {'n': n, 'pnl': round(total, 2), 'bots': bots}

def get_strategy():
    db = os.path.join(BASE, 'data/strategy_paper.db')
    r = q(db, "SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2), ROUND(100.0*SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END)/COUNT(*),1) FROM trades WHERE status='CLOSED'")
    open_n = q(db, "SELECT COUNT(*) FROM trades WHERE status='OPEN'")
    gold = get_gold()
    return {'n': r[0] if r else 0, 'pnl': r[1] if r else 0, 'wr': r[2] if r else 0,
            'open': open_n[0] if open_n else 0, 'gold': gold[0] if gold else None}

def get_gold():
    try:
        d = json.load(open(os.path.join(BASE, 'data/evolution.json')))
        gold = [s for s in d.get('top', []) if s.get('wr', 0) >= 55 and s.get('n', 0) >= 100]
        return sorted(gold, key=lambda x: x.get('wr', 0), reverse=True)
    except: return []

def get_evolution_meta():
    try:
        d = json.load(open(os.path.join(BASE, 'data/evolution.json')))
        return {'ts': d.get('timestamp', '?'), 'L1': d.get('L1', 0), 'L2': d.get('L2', 0), 'L3': d.get('L3', 0)}
    except: return {'ts': '?', 'L1': 0, 'L2': 0, 'L3': 0}

def get_agent():
    db = os.path.join(BASE, 'tools/agent/memory.db')
    try:
        c = sqlite3.connect(db, timeout=5)
        facts = c.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        actions = c.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        exp = c.execute("SELECT COUNT(*) FROM experience").fetchone()[0]
        weights = c.execute("SELECT COUNT(*) FROM weights").fetchone()[0]
        pending = c.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
        top_w = c.execute("SELECT rule, weight, fires, success FROM weights ORDER BY weight DESC LIMIT 5").fetchall()
        c.close()
        return {'facts': facts, 'actions': actions, 'exp': exp, 'weights': weights, 'pending': pending, 'top_w': top_w}
    except: return {'facts': 0, 'actions': 0, 'exp': 0, 'weights': 0, 'pending': 0, 'top_w': []}

def get_rag():
    db = os.path.join(BASE, 'data/project_knowledge.db')
    try:
        c = sqlite3.connect(db, timeout=5)
        rows = c.execute("SELECT category, COUNT(*) FROM docs GROUP BY category").fetchall()
        total = c.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        c.close()
        return {'total': total, 'by_cat': dict(rows)}
    except: return {'total': 0, 'by_cat': {}}

def get_knowledge():
    db = os.path.join(BASE, 'data/knowledge.db')
    try:
        c = sqlite3.connect(db, timeout=5)
        rows = c.execute("SELECT source, category, COUNT(*) FROM knowledge GROUP BY source, category").fetchall()
        total = c.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
        c.close()
        return {'total': total, 'rows': rows}
    except: return {'total': 0, 'rows': []}

def get_freshness():
    res = {}
    for db, table in [('oracle.db','regime'),('market.db','candles'),('orderbook.db','orderbooks')]:
        p = os.path.join(BASE, 'data', db)
        r = q(p, f"SELECT (strftime('%s','now') - MAX(ts)) FROM {table}")
        res[db] = r[0] if r else None
    return res

def get_procs():
    procs = []
    for name in ['okx_bot_paper_v4', 'brain_loop', 'oracle.py', 'orderbook_oracle', 'data_manager', 'strategy_bot', 'evolve_agent', 'evolution']:
        r = subprocess.run(['pgrep', '-f', name], capture_output=True, text=True)
        procs.append({'name': name, 'alive': bool(r.stdout.strip())})
    return procs

def get_strategy_trades(limit=10):
    db = os.path.join(BASE, 'data/strategy_paper.db')
    try:
        c = sqlite3.connect(db, timeout=5)
        rows = c.execute("""SELECT symbol, strategy, side, entry_price, exit_price, pnl, status, entry_ts
                            FROM trades ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
        c.close()
        return rows
    except: return []

def get_ml():
    try:
        d = json.load(open(os.path.join(BASE, 'data/ml_predictions_online.json')))
        return d.get('predictions', {})
    except: return {}

def get_auto_tuners():
    """Последние изменения auto_obi_tuner и auto_tpsl_tuner."""
    res = {}
    for name in ['okx_tpsl_v3.json', 'okx_tpsl_v4.json']:
        p = os.path.join(BASE, 'data', name)
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                res[name] = {'source': d.get('source', '?'), 'updated': d.get('updated_at', '?')}
            except: pass
    return res

# ============ ШАБЛОН ============

HTML = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="theme-color" content="#0a0a0f">
<title>Quantum Lab</title>
<style>
:root{--bg:#0a0a0f;--surface:#12121a;--border:#1e1e2e;--text:#e4e4ec;--muted:#71717a;--green:#10b981;--red:#ef4444;--amber:#f59e0b;--blue:#3b82f6;--purple:#8b5cf6}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;padding:14px;line-height:1.5;font-size:14px;max-width:100vw;overflow-x:hidden}
h1{font-size:20px;font-weight:700;margin-bottom:2px;letter-spacing:-0.02em}
.subtitle{color:var(--muted);font-size:12px;margin-bottom:16px}
.section{margin-bottom:20px}
.section-title{font-size:13px;font-weight:600;margin-bottom:8px;color:var(--text);display:flex;align-items:center;gap:6px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:16px}
@media(min-width:480px){.grid{grid-template-columns:repeat(2,1fr)}}
@media(min-width:720px){.grid{grid-template-columns:repeat(4,1fr)}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px}
.card-label{font-size:9px;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:3px}
.card-value{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-0.02em}
.card-value.green{color:var(--green)}.card-value.red{color:var(--red)}.card-value.amber{color:var(--amber)}.card-value.blue{color:var(--blue)}.card-value.purple{color:var(--purple)}
.card-sub{font-size:10px;color:var(--muted);margin-top:1px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;font-size:9px;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);padding:6px 4px;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:6px 4px;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums;white-space:nowrap}
tr:last-child td{border-bottom:none}
.badge{display:inline-flex;align-items:center;gap:3px;padding:1px 6px;border-radius:999px;font-size:9px;font-weight:600;text-transform:uppercase;white-space:nowrap}
.badge.green{background:rgba(16,185,129,0.12);color:var(--green);border:1px solid rgba(16,185,129,0.2)}
.badge.red{background:rgba(239,68,68,0.12);color:var(--red);border:1px solid rgba(239,68,68,0.2)}
.badge.amber{background:rgba(245,158,11,0.12);color:var(--amber);border:1px solid rgba(245,158,11,0.2)}
.badge.blue{background:rgba(59,130,246,0.12);color:var(--blue);border:1px solid rgba(59,130,246,0.2)}
.dot{width:5px;height:5px;border-radius:50%;display:inline-block}.dot.green{background:var(--green)}.dot.red{background:var(--red)}
.footer{color:var(--muted);font-size:10px;margin-top:16px;text-align:center}
.row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);font-size:12px}
.row:last-child{border-bottom:none}
.row-label{color:var(--muted)}
.row-value{font-weight:600;font-variant-numeric:tabular-nums}
.progress{height:4px;background:var(--border);border-radius:2px;overflow:hidden;margin-top:4px}
.progress-bar{height:100%;background:var(--green);transition:width 0.3s}
.scroll-x{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px;padding:0 4px}
</style></head><body>

<h1>⚡ Quantum Lab</h1>
<div class="subtitle">{{ now }} · <span style="color:var(--green)">LIVE</span></div>

<!-- ГЛАВНЫЕ KPI -->
<div class="grid">
<div class="card"><div class="card-label">OKX v4</div><div class="card-value {{ 'green' if okx.pnl >= 0 else 'red' }}">{{ '%+.2f'|format(okx.pnl) }}</div><div class="card-sub">{{ okx.n }} · WR {{ okx.wr }}%</div></div>
<div class="card"><div class="card-label">Polymarket</div><div class="card-value {{ 'green' if poly.pnl >= 0 else 'red' }}">{{ '%+.2f'|format(poly.pnl) }}</div><div class="card-sub">{{ poly.n }} · 4 бота</div></div>
<div class="card"><div class="card-label">Strategy</div><div class="card-value {{ 'green' if strategy.pnl >= 0 else 'red' }}">{{ '%+.2f'|format(strategy.pnl) }}</div><div class="card-sub">{{ strategy.n }} · {{ strategy.open }} откр</div></div>
<div class="card"><div class="card-label">Всего</div><div class="card-value green">{{ '%+.2f'|format(okx.pnl + poly.pnl + strategy.pnl) }}</div><div class="card-sub">сумма</div></div>
</div>

<!-- ГРААЛИ -->
<div class="section">
<div class="section-title">🏆 Граали · {{ gold|length }}</div>
<div class="card"><div class="scroll-x"><table>
<thead><tr><th>Символ</th><th>Стратегия</th><th>WR</th><th>n</th><th>Exp</th></tr></thead><tbody>
{% for g in gold %}<tr><td>{{ g.symbol.replace('USDT','') }}</td><td>{{ g.strategy }}</td><td><span class="badge green">{{ g.wr }}%</span></td><td>{{ g.n }}</td><td>{{ '%.4f'|format(g.get('expectancy',0)) }}</td></tr>{% endfor %}
</tbody></table></div></div>
</div>

<!-- ЭВОЛЮЦИЯ -->
<div class="section">
<div class="section-title">🧬 Эволюция</div>
<div class="card">
<div class="row"><span class="row-label">Последний запуск</span><span class="row-value">{{ evo.ts[:19] if evo.ts else '?' }}</span></div>
<div class="row"><span class="row-label">L1 / L2 / L3</span><span class="row-value">{{ evo.L1 }} → {{ evo.L2 }} → {{ evo.L3 }}</span></div>
<div class="row"><span class="row-label">Найдено граалей</span><span class="row-value green">{{ gold|length }}</span></div>
</div>
</div>

<!-- STRATEGY BOT: последние сделки -->
<div class="section">
<div class="section-title">🎯 Strategy Bot сделки</div>
<div class="card"><div class="scroll-x"><table>
<thead><tr><th>Время</th><th>Символ</th><th>Сторона</th><th>Вход</th><th>Выход</th><th>PnL</th><th>Статус</th></tr></thead><tbody>
{% for t in strades %}<tr>
<td>{{ t[7]|int|ts }}</td><td>{{ t[0].replace('USDT','') }}</td>
<td><span class="badge {{ 'blue' if t[2]=='LONG' else 'amber' }}">{{ t[2] }}</span></td>
<td>{{ '%.2f'|format(t[3]) }}</td><td>{{ '%.2f'|format(t[4]) if t[4] else '-' }}</td>
<td class="{{ 'green' if t[5] and t[5]>0 else 'red' if t[5] and t[5]<0 else '' }}">{{ '%+.2f'|format(t[5]) if t[5] else '-' }}</td>
<td>{% if t[6]=='OPEN' %}<span class="badge amber">OPEN</span>{% else %}<span class="badge green">✓</span>{% endif %}</td>
</tr>{% endfor %}
</tbody></table></div></div>
</div>

<!-- POLYMARKET -->
<div class="section">
<div class="section-title">🤖 Polymarket · 4 бота</div>
<div class="card">
{% for b in poly.bots %}<div class="row"><span class="row-label">{{ b.name }}</span><span class="row-value {{ 'green' if b.pnl>=0 else 'red' }}">{{ '%+.2f'|format(b.pnl) }}</span></div>{% endfor %}
</div>
</div>

<!-- АГЕНТ -->
<div class="section">
<div class="section-title">🧠 Агент v6</div>
<div class="card">
<div class="grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:8px">
<div><div class="card-label">Facts</div><div class="card-value blue" style="font-size:18px">{{ agent.facts }}</div></div>
<div><div class="card-label">Actions</div><div class="card-value blue" style="font-size:18px">{{ agent.actions }}</div></div>
<div><div class="card-label">Experience</div><div class="card-value purple" style="font-size:18px">{{ agent.exp }}</div></div>
</div>
<div class="row"><span class="row-label">Веса правил</span><span class="row-value">{{ agent.weights }}</span></div>
<div class="row"><span class="row-label">В очереди (pending)</span><span class="row-value amber">{{ agent.pending }}</span></div>
{% for w in agent.top_w %}<div class="row"><span class="row-label">{{ w[0][:30] }}</span><span class="row-value">{{ '%.1f'|format(w[1]) }} ({{ w[3] }}/{{ w[2] }})</span></div>{% endfor %}
</div>
</div>

<!-- ML -->
<div class="section">
<div class="section-title">🤖 ML предсказания</div>
<div class="card"><div class="scroll-x"><table>
<thead><tr><th>Символ</th><th>Proba</th><th>Side</th></tr></thead><tbody>
{% for sym, p in ml.items() %}<tr><td>{{ sym.replace('USDT','') }}</td><td>{{ '%.3f'|format(p.get('proba_long', 0.5)) }}</td><td><span class="badge {{ 'blue' if p.get('side')=='LONG' else 'amber' if p.get('side')=='SHORT' else 'green' }}">{{ p.get('side','WAIT') }}</span></td></tr>{% endfor %}
</tbody></table></div></div>
</div>

<!-- RAG + KNOWLEDGE -->
<div class="section">
<div class="section-title">📚 RAG · Знания</div>
<div class="card">
<div class="row"><span class="row-label">RAG (файлов проекта)</span><span class="row-value green">{{ rag.total }}</span></div>
{% for cat, cnt in rag.by_cat.items() %}<div class="row"><span class="row-label">  {{ cat }}</span><span class="row-value">{{ cnt }}</span></div>{% endfor %}
<div class="row"><span class="row-label">Knowledge (интернет)</span><span class="row-value green">{{ know.total }}</span></div>
{% for r in know.rows %}<div class="row"><span class="row-label">  {{ r[0] }} / {{ r[1] }}</span><span class="row-value">{{ r[2] }}</span></div>{% endfor %}
</div>
</div>

<!-- ТЮНЕРЫ -->
<div class="section">
<div class="section-title">⚙️ Авто-тюнеры</div>
<div class="card">
{% for name, t in tuners.items() %}<div class="row"><span class="row-label">{{ name }}</span><span class="row-value">{{ t.source }}</span></div>{% endfor %}
</div>
</div>

<!-- СВЕЖЕСТЬ -->
<div class="section">
<div class="section-title">📊 Свежесть данных</div>
<div class="card">
{% for name, age in fresh.items() %}<div class="row"><span class="row-label">{{ name }}</span><span class="row-value {{ 'green' if age and age < 120 else 'amber' if age and age < 600 else 'red' }}">{{ age }}с</span></div>{% endfor %}
</div>
</div>

<!-- ПРОЦЕССЫ -->
<div class="section">
<div class="section-title">🔧 Процессы</div>
<div class="card">
{% for p in procs %}<div class="row"><span class="row-label">{{ p.name }}</span><span class="row-value">{% if p.alive %}<span class="badge green"><span class="dot green"></span> OK</span>{% else %}<span class="badge red"><span class="dot red"></span> DOWN</span>{% endif %}</span></div>{% endfor %}
</div>
</div>

<div class="footer">Quantum Lab · {{ now }}</div>
</body></html>"""

@app.template_filter('ts')
def ts_filter(t):
    if not t: return '-'
    try: return datetime.fromtimestamp(int(t)).strftime('%H:%M')
    except: return '-'

@app.route('/')
def index():
    return render_template_string(HTML,
        now=datetime.now().strftime('%Y-%m-%d %H:%M'),
        okx=get_okx(),
        poly=get_poly(),
        strategy=get_strategy(),
        gold=get_gold(),
        evo=get_evolution_meta(),
        agent=get_agent(),
        rag=get_rag(),
        know=get_knowledge(),
        fresh=get_freshness(),
        procs=get_procs(),
        strades=get_strategy_trades(10),
        ml=get_ml(),
        tuners=get_auto_tuners()
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
