#!/usr/bin/env python3
"""web/app.py — QUANTUM LAB. Полная веб-панель с real-time логами."""
import os, sys, json, sqlite3, subprocess, urllib.parse, time, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
RSBOT = os.path.expanduser('~/rsbot')
PORT = 8301

# ═══ ДАННЫЕ ═══
def q(sql, args=()):
    try:
        c = sqlite3.connect(os.path.join(RSBOT, 'pm_v7.db'), timeout=3)
        r = c.execute(sql, args).fetchall(); c.close(); return r
    except: return []

def read_json(path):
    try:
        with open(path) as f: return json.load(f)
    except: return None

def get_bots():
    bots = [('V1','pm_bot.db'),('V4','pm_v4.db'),('V5','pm_v5.db'),('V6.1','pm_v6.db'),('V7','pm_v7.db')]
    out = []
    for name, db in bots:
        p = os.path.join(RSBOT, db)
        if not os.path.exists(p): continue
        try:
            c = sqlite3.connect(p, timeout=2)
            r = c.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2), SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) FROM trades").fetchone()
            c.close()
            out.append({'name': name, 'trades': r[0], 'pnl': r[1], 'open': r[2] or 0})
        except: pass
    return out

def get_total_pnl():
    return sum(b['pnl'] or 0 for b in get_bots())

def get_golden():
    data = read_json(os.path.join(BASE, 'data/gate_all.json'))
    if not data: return []
    return [r for r in data.get('results', []) if r['verdict'] in ('GOLDEN', 'TRADE_NOW')]

def get_evolution():
    return read_json(os.path.join(BASE, 'data/evolution.json')) or {}

def get_active():
    return read_json(os.path.join(BASE, 'data/active_strategies.json')) or {}

def get_log_tail(path, n=30):
    try:
        with open(path, errors='ignore') as f:
            return ''.join(f.readlines()[-n:])
    except: return ''

# ═══ HTML ═══
HTML = '''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QUANTUM LAB — Autonomous Strategy Discovery</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{background:#050510;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;overflow-x:hidden}
.glass{background:rgba(15,23,42,0.6);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,0.08);box-shadow:0 8px 32px rgba(0,0,0,0.5)}
.glow-gold{text-shadow:0 0 20px rgba(251,191,36,0.8);color:#fbbf24}
.glow-green{text-shadow:0 0 20px rgba(52,211,153,0.6);color:#34d399}
.glow-red{text-shadow:0 0 20px rgba(248,113,113,0.6);color:#f87171}
.bg-quantum{position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:-1;background:radial-gradient(circle at 20% 0%,#1e1b4b 0%,#050510 60%)}
.log-box{background:#0a0a15;border:1px solid rgba(255,255,255,0.05);font-family:'JetBrains Mono',monospace;font-size:11px;height:300px;overflow-y:auto;padding:8px}
.log-line{color:#94a3b8;line-height:1.4}
.log-line.err{color:#f87171}.log-line.ok{color:#34d399}.log-line.warn{color:#fbbf24}
.tab{transition:all 0.2s}
.tab.active{background:rgba(251,191,36,0.15);color:#fbbf24;border-bottom:2px solid #fbbf24}
</style>
</head>
<body>
<div class="bg-quantum"></div>
<canvas id="particles" class="fixed inset-0 pointer-events-none z-[-1]"></canvas>

<div class="max-w-7xl mx-auto p-4 pb-20 relative z-10">
  <!-- HEADER -->
  <header class="glass rounded-2xl p-6 mb-6 relative overflow-hidden">
    <div class="absolute inset-0 bg-gradient-to-r from-indigo-500/10 via-transparent to-amber-500/10"></div>
    <div class="relative">
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 class="text-3xl font-bold bg-gradient-to-r from-cyan-400 via-indigo-400 to-amber-400 bg-clip-text text-transparent">⚛ QUANTUM LAB</h1>
          <p class="text-gray-400 text-sm mt-1">Autonomous Strategy Discovery · real-time</p>
        </div>
        <div class="text-right">
          <div class="text-xs text-gray-400">Суммарный заработок</div>
          <div class="text-4xl font-bold glow-green" id="total-pnl">$0.00</div>
        </div>
      </div>
    </div>
  </header>

  <!-- STATS -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
    <div class="glass rounded-xl p-4"><div class="text-xs text-gray-400">Golden Edge</div><div class="text-2xl font-bold glow-gold" id="golden-count">0</div></div>
    <div class="glass rounded-xl p-4"><div class="text-xs text-gray-400">Стратегий в active</div><div class="text-2xl font-bold text-cyan-400" id="active-count">0</div></div>
    <div class="glass rounded-xl p-4"><div class="text-xs text-gray-400">Ботов</div><div class="text-2xl font-bold text-indigo-400" id="bots-count">0</div></div>
    <div class="glass rounded-xl p-4"><div class="text-xs text-gray-400">Сделок (V7)</div><div class="text-2xl font-bold text-gray-300" id="trades-count">0</div></div>
  </div>

  <!-- TABS -->
  <div class="glass rounded-2xl overflow-hidden mb-6">
    <div class="flex border-b border-white/10 overflow-x-auto">
      <button class="tab active px-4 py-3 text-sm font-semibold whitespace-nowrap" onclick="switchTab('dashboard')">📊 Dashboard</button>
      <button class="tab px-4 py-3 text-sm font-semibold whitespace-nowrap" onclick="switchTab('golden')">🏆 Golden Edge</button>
      <button class="tab px-4 py-3 text-sm font-semibold whitespace-nowrap" onclick="switchTab('evolution')">🧬 Evolution</button>
      <button class="tab px-4 py-3 text-sm font-semibold whitespace-nowrap" onclick="switchTab('logs')">📜 Live Logs</button>
      <button class="tab px-4 py-3 text-sm font-semibold whitespace-nowrap" onclick="switchTab('bots')">🤖 Bots</button>
      <button class="tab px-4 py-3 text-sm font-semibold whitespace-nowrap" onclick="switchTab('agents')">🔬 Agents</button>
    </div>

    <!-- DASHBOARD -->
    <div id="tab-dashboard" class="p-4">
      <h2 class="text-lg font-semibold mb-3">📊 Обзор</h2>
      <div class="grid md:grid-cols-2 gap-4">
        <div class="glass rounded-xl p-4"><h3 class="text-sm text-gray-400 mb-2">PnL по ботам</h3><canvas id="pnl-chart" height="150"></canvas></div>
        <div class="glass rounded-xl p-4"><h3 class="text-sm text-gray-400 mb-2">Что торгуем (active)</h3><div id="active-list" class="text-sm space-y-1"></div></div>
      </div>
    </div>

    <!-- GOLDEN -->
    <div id="tab-golden" class="p-4 hidden">
      <h2 class="text-lg font-semibold mb-3">🏆 Golden Edge (4 GOLDEN)</h2>
      <div id="golden-list" class="space-y-2"></div>
    </div>

    <!-- EVOLUTION -->
    <div id="tab-evolution" class="p-4 hidden">
      <h2 class="text-lg font-semibold mb-3">🧬 Evolution (L1 → L2 → L3)</h2>
      <div class="grid md:grid-cols-3 gap-3 mb-4">
        <div class="glass rounded-xl p-3"><div class="text-xs text-gray-400">L1 (grid)</div><div class="text-xl font-bold text-cyan-400" id="evo-l1">0</div></div>
        <div class="glass rounded-xl p-3"><div class="text-xs text-gray-400">L2 (features)</div><div class="text-xl font-bold text-indigo-400" id="evo-l2">0</div></div>
        <div class="glass rounded-xl p-3"><div class="text-xs text-gray-400">L3 (mutations)</div><div class="text-xl font-bold text-amber-400" id="evo-l3">0</div></div>
      </div>
      <div id="evo-top" class="space-y-2"></div>
    </div>

    <!-- LOGS -->
    <div id="tab-logs" class="p-4 hidden">
      <h2 class="text-lg font-semibold mb-3">📜 Live Logs (real-time)</h2>
      <div class="grid md:grid-cols-2 gap-3">
        <div class="glass rounded-xl p-3"><h3 class="text-xs text-gray-400 mb-2">Brain</h3><div class="log-box" id="log-brain"></div></div>
        <div class="glass rounded-xl p-3"><h3 class="text-xs text-gray-400 mb-2">Evolution</h3><div class="log-box" id="log-evolution"></div></div>
        <div class="glass rounded-xl p-3"><h3 class="text-xs text-gray-400 mb-2">V7</h3><div class="log-box" id="log-v7"></div></div>
        <div class="glass rounded-xl p-3"><h3 class="text-xs text-gray-400 mb-2">Gate</h3><div class="log-box" id="log-gate"></div></div>
      </div>
    </div>

    <!-- BOTS -->
    <div id="tab-bots" class="p-4 hidden">
      <h2 class="text-lg font-semibold mb-3">🤖 Боты</h2>
      <div id="bots-list" class="space-y-2"></div>
    </div>

    <!-- AGENTS -->
    <div id="tab-agents" class="p-4 hidden">
      <h2 class="text-lg font-semibold mb-3">🔬 Отчёты агентов</h2>
      <div id="agents-list" class="space-y-2"></div>
    </div>
  </div>
</div>

<script>
// частицы
const c = document.getElementById('particles'), ctx = c.getContext('2d');
c.width = window.innerWidth; c.height = window.innerHeight;
let pts = Array(60).fill().map(()=>({x:Math.random()*c.width,y:Math.random()*c.height,vx:(Math.random()-0.5)*0.3,vy:(Math.random()-0.5)*0.3}));
function anim(){ctx.clearRect(0,0,c.width,c.height);pts.forEach(p=>{p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>c.width)p.vx*=-1;if(p.y<0||p.y>c.height)p.vy*=-1;ctx.fillStyle='rgba(99,102,241,0.4)';ctx.beginPath();ctx.arc(p.x,p.y,1.5,0,7);ctx.fill();});requestAnimationFrame(anim);}anim();

let currentTab = 'dashboard';
function switchTab(name){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('[id^="tab-"]').forEach(t=>t.classList.add('hidden'));
  document.getElementById('tab-'+name).classList.remove('hidden');
  currentTab = name;
}

async function load(){
  try {
    const r = await fetch('/api/state'); const d = await r.json();
    document.getElementById('total-pnl').textContent = '$' + (d.total_pnl||0).toFixed(2);
    document.getElementById('golden-count').textContent = (d.golden||[]).length;
    document.getElementById('active-count').textContent = Object.keys((d.active||{}).pairs||{}).length;
    document.getElementById('bots-count').textContent = (d.bots||[]).length;
    document.getElementById('trades-count').textContent = d.v7_trades||0;

    // active
    let al = '';
    for (const [k,v] of Object.entries((d.active||{}).pairs||{})) {
      if (v.trade) al += `<div class="flex justify-between"><span class="font-mono text-cyan-300">${v.symbol} ${v.tf}</span><span>${v.strategy} <span class="text-green-400">${v.wr}%</span></span></div>`;
    }
    document.getElementById('active-list').innerHTML = al || '<div class="text-gray-500">пусто</div>';

    // golden
    let gl = '';
    (d.golden||[]).forEach(g=>{
      gl += `<div class="glass rounded-xl p-4 flex justify-between items-center"><div><div class="font-mono text-cyan-300">${g.symbol} ${g.tf}</div><div class="text-xs text-gray-400">${g.strategy}</div></div><div class="text-right"><div class="text-xl glow-gold">${g.L1.wr}%</div><div class="text-xs text-gray-400">n=${g.L1.n} p=${g.L1.p}</div></div></div>`;
    });
    document.getElementById('golden-list').innerHTML = gl || '<div class="text-gray-500">пусто</div>';

    // evolution
    const evo = d.evolution||{};
    document.getElementById('evo-l1').textContent = evo.L1||0;
    document.getElementById('evo-l2').textContent = evo.L2||0;
    document.getElementById('evo-l3').textContent = evo.L3||0;
    let et = '';
    (evo.top||[]).slice(0,10).forEach(r=>{
      et += `<div class="glass rounded-xl p-3 flex justify-between"><span class="font-mono text-cyan-300">${r.symbol} ${r.strategy}</span><span>WR=<span class="text-green-400">${r.wr}%</span> n=${r.n}</span></div>`;
    });
    document.getElementById('evo-top').innerHTML = et;

    // bots
    let bl = '';
    (d.bots||[]).forEach(b=>{
      const cls = b.pnl>=0?'glow-green':'glow-red';
      bl += `<div class="glass rounded-xl p-4 flex justify-between items-center"><div><div class="font-semibold">${b.name}</div><div class="text-xs text-gray-400">${b.trades} сделок</div></div><div class="text-right"><div class="text-xl ${cls}">$${b.pnl}</div><div class="text-xs text-gray-400">open=${b.open}</div></div></div>`;
    });
    document.getElementById('bots-list').innerHTML = bl;

    // chart
    if (window.pnlChart) window.pnlChart.destroy();
    window.pnlChart = new Chart(document.getElementById('pnl-chart'), {
      type: 'bar',
      data: {labels: (d.bots||[]).map(b=>b.name), datasets:[{data:(d.bots||[]).map(b=>b.pnl), backgroundColor:(d.bots||[]).map(b=>b.pnl>=0?'rgba(52,211,153,0.7)':'rgba(248,113,113,0.7)'), borderRadius:8}]},
      options:{plugins:{legend:{display:false}},scales:{y:{ticks:{color:'#94a3b8'},grid:{color:'rgba(255,255,255,0.05)'}},x:{ticks:{color:'#94a3b8'},grid:{display:false}}}}
    });
  } catch(e) { console.error(e); }
}

async function loadLogs(){
  try {
    const r = await fetch('/api/logs'); const d = await r.json();
    for (const [k,v] of Object.entries(d)) {
      const el = document.getElementById('log-'+k);
      if (!el) continue;
      el.innerHTML = v.split('\\n').map(l=>{
        let cls='log-line'; if(/ERROR|FAIL|Traceback/.test(l)) cls+=' err'; else if(/OK|✅|GOLDEN/.test(l)) cls+=' ok'; else if(/WARN|⚠️/.test(l)) cls+=' warn';
        return `<div class="${cls}">${l.replace(/</g,'&lt;')}</div>`;
      }).join('');
      el.scrollTop = el.scrollHeight;
    }
  } catch(e) {}
}

async function loadAgents(){
  try {
    const r = await fetch('/api/agents'); const d = await r.json();
    let html = '';
    for (const [k,v] of Object.entries(d)) {
      html += `<div class="glass rounded-xl p-3"><div class="text-xs text-gray-400">${k}</div><pre class="text-xs text-gray-300 overflow-x-auto">${JSON.stringify(v,null,2).slice(0,300)}</pre></div>`;
    }
    document.getElementById('agents-list').innerHTML = html || '<div class="text-gray-500">пусто</div>';
  } catch(e) {}
}

load(); loadLogs(); loadAgents();
setInterval(load, 5000);
setInterval(loadLogs, 3000);
setInterval(loadAgents, 15000);
</script>
</body>
</html>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ct='text/html; charset=utf-8'):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header('Content-Type', ct); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == '/': self._send(200, HTML)
            elif u.path == '/api/state':
                bots = get_bots()
                v7 = [b for b in bots if b['name']=='V7']
                data = {'total_pnl': round(get_total_pnl(),2), 'bots': bots,
                        'golden': get_golden(), 'evolution': get_evolution(),
                        'active': get_active(), 'v7_trades': v7[0]['trades'] if v7 else 0}
                self._send(200, json.dumps(data, ensure_ascii=False), 'application/json')
            elif u.path == '/api/logs':
                logs = {'brain': get_log_tail(os.path.join(BASE,'logs/brain_loop.log')),
                        'evolution': get_log_tail(os.path.join(BASE,'logs/evolution.log')),
                        'v7': get_log_tail(os.path.join(RSBOT,'pm_v7.log')),
                        'gate': get_log_tail(os.path.join(BASE,'logs/gate_full.log'))}
                self._send(200, json.dumps(logs, ensure_ascii=False), 'application/json')
            elif u.path == '/api/agents':
                agents = {}
                for f in ['data_report','gate_report','evolve_report','live_report','risk_report']:
                    p = os.path.join(BASE, 'data', f+'.json')
                    if os.path.exists(p): agents[f] = read_json(p)
                self._send(200, json.dumps(agents, ensure_ascii=False), 'application/json')
            else: self._send(404, '{}')
        except Exception as e:
            self._send(500, json.dumps({'error':str(e)}))

if __name__ == '__main__':
    print(f'QUANTUM LAB: http://127.0.0.1:{PORT}')
    HTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
