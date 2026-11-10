#!/usr/bin/env python3
"""web_export.py — экспорт сделок paper-бота в реальном времени.

Каждый цикл бота публикует свежие сделки, агрегаты по монетам/стратегиям
и общий PnL в data/web_dashboard.json (локально + через GitHub API),
откуда их читает веб-панель на GitHub Pages.
"""
import base64, json, os, sqlite3, time, urllib.request

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/okx_paper_v4.db')
OUT = os.path.join(BASE, 'data/web_dashboard.json')
REPO = 'palcikia-crypto/quantum_lab'
API_URL = 'https://api.github.com/repos/%s/contents/data/web_dashboard.json' % REPO
MIN_INTERVAL = 45  # минимум секунд между публикациями

_state = {'ts': 0, 'sig': None}


def _collect():
    if not os.path.exists(DB):
        return None
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in c.execute('SELECT * FROM trades ORDER BY id DESC LIMIT 300')]
    finally:
        c.close()
    closed = [r for r in rows if str(r.get('status') or '').upper() != 'OPEN']
    pnls = [r['pnl'] for r in closed if isinstance(r.get('pnl'), (int, float))]
    wins = sum(1 for v in pnls if v > 0)

    def agg(key):
        out = {}
        for r in closed:
            k = str(r.get(key) or '-')
            a = out.setdefault(k, {'trades': 0, 'wins': 0, 'pnl': 0.0})
            p = r.get('pnl') or 0
            a['trades'] += 1
            a['pnl'] += p
            if p > 0:
                a['wins'] += 1
        for a in out.values():
            a['pnl'] = round(a['pnl'], 2)
            a['wr'] = round(100.0 * a['wins'] / a['trades'], 1)
        return out

    return {
        'updated_at': int(time.time()),
        'bot': 'okx_bot_v5',
        'totals': {
            'pnl': round(sum(pnls), 2),
            'trades': len(closed),
            'open': len(rows) - len(closed),
            'wr': round(100.0 * wins / len(pnls), 1) if pnls else None,
        },
        'by_symbol': agg('symbol'),
        'by_strategy': agg('strategy'),
        'trades': rows,
    }


def _push_to_github(b64):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        return False
    try:
        sha = None
        req = urllib.request.Request(API_URL)
        req.add_header('Authorization', 'Bearer ' + token)
        req.add_header('Accept', 'application/vnd.github+json')
        try:
            with urllib.request.urlopen(req, timeout=15) as f:
                sha = json.load(f).get('sha')
        except Exception:
            pass
        payload = {'message': 'Live trades update', 'content': b64, 'branch': 'master'}
        if sha:
            payload['sha'] = sha
        req2 = urllib.request.Request(API_URL, data=json.dumps(payload).encode(), method='PUT')
        req2.add_header('Authorization', 'Bearer ' + token)
        req2.add_header('Content-Type', 'application/json')
        urllib.request.urlopen(req2, timeout=15).read()
        return True
    except Exception:
        return False


def publish():
    """Вызывать из цикла бота: публикует данные, если они изменились."""
    data = _collect()
    if not data:
        return
    now = time.time()
    if now - _state['ts'] < MIN_INTERVAL:
        return
    sig = (len(data['trades']), data['totals']['pnl'], data['totals']['open'])
    if sig == _state['sig'] and now - _state['ts'] < 120:
        return
    _state['ts'] = now
    _state['sig'] = sig
    try:
        with open(OUT, 'w') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass
    try:
        b64 = base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()
        _push_to_github(b64)
    except Exception:
        pass


if __name__ == '__main__':
    d = _collect()
    print(json.dumps(d, ensure_ascii=False)[:500] if d else 'no db')
