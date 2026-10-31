#!/usr/bin/env python3
"""Дашборд агента: HTML с памятью, действиями, весами."""
import os, json, sqlite3
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
MEM = os.path.join(BASE, 'tools/agent/memory.db')
OUT = os.path.join(BASE, 'data/agent_dashboard.html')

def main():
    c = sqlite3.connect(MEM)
    facts = c.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    actions = c.execute("SELECT action, target, success, ts FROM actions ORDER BY ts DESC LIMIT 20").fetchall()
    weights = c.execute("SELECT rule, weight, fires, success FROM weights ORDER BY weight DESC").fetchall()
    exp = c.execute("SELECT action, outcome, score FROM experience ORDER BY ts DESC LIMIT 10").fetchall()
    c.close()

    rows_actions = ''.join(
        f'<tr><td>{a}</td><td>{t}</td><td>{"✅" if s else "❌"}</td><td>{datetime.fromtimestamp(ts):%H:%M:%S}</td></tr>'
        for a, t, s, ts in actions)
    rows_weights = ''.join(
        f'<tr><td>{r}</td><td>{w:.2f}</td><td>{f}</td><td>{s}</td></tr>'
        for r, w, f, s in weights)
    rows_exp = ''.join(
        f'<tr><td>{a}</td><td>{o}</td><td>{sc:.2f}</td></tr>' for a, o, sc in exp)

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Agent Dashboard</title>
<style>body{{font-family:sans-serif;background:#111;color:#eee;padding:20px}}
table{{border-collapse:collapse;width:100%;margin:10px 0}}
th,td{{border:1px solid #333;padding:8px;text-align:left}}
th{{background:#222}}h1,h2{{color:#0f0}}h3{{color:#0ff}}</style></head><body>
<h1>🤖 Agent Dashboard</h1>
<p>Обновлено: {datetime.now():%Y-%m-%d %H:%M:%S}</p>
<h2>📊 Статистика</h2>
<p>Facts: <b>{facts}</b> | Actions: <b>{len(actions)}</b> | Weights: <b>{len(weights)}</b></p>
<h2>🎯 Действия (последние 20)</h2>
<table><tr><th>Action</th><th>Target</th><th>Success</th><th>Time</th></tr>{rows_actions}</table>
<h2>⚖️ Веса правил</h2>
<table><tr><th>Rule</th><th>Weight</th><th>Fires</th><th>Success</th></tr>{rows_weights}</table>
<h2>🧠 Опыт</h2>
<table><tr><th>Action</th><th>Outcome</th><th>Score</th></tr>{rows_exp}</table>
</body></html>"""

    open(OUT, 'w').write(html)
    print(f'✅ dashboard: {OUT}')

if __name__ == '__main__':
    main()
