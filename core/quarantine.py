#!/usr/bin/env python3
"""quarantine.py — умный автокарантин: быстрый ответ на серии убытков
БЕЗ вырубания всей торговли.

Правила (согласованы с риском 2% банка, SL 0.25% → ~-0.05$ на сделку):
  1. Монета: 3 убытка подряд            → пауза 90 мин (повтор — пауза x2)
  2. Монета: день <= -0.35$ (>=4 сделок) → пауза до конца UTC-дня
  3. Связка монета+стратегия: 4 убытка подряд → пауза 3 ч
  4. Глобально: день <= -1.5$           → новых сделок нет до конца дня
Защита от «вырубил всё подряд»:
  - минимум 3-4 сделки до срабатывания, 1-2 минуса ничего не трогают
  - карантин ВСЕГДА временный, авто-возврат после паузы
  - одновременно в карантине не более половины юниверса
Состояние: data/quarantine.json (события + таймеры — видно в панели).
"""
import json, os, sqlite3, time

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/okx_paper_v4.db')
QF = os.path.join(BASE, 'data/quarantine.json')

LOSS_STREAK_SYM = 3
LOSS_STREAK_COMBO = 4
SYM_DAILY_CAP = -0.35
GLOBAL_DAILY_CAP = -1.5
MIN_TRADES_DAILY = 4
BASE_COOLDOWN = 90 * 60


def _now():
    return int(time.time())


def load():
    try:
        d = json.load(open(QF))
        if isinstance(d, dict):
            d.setdefault('items', {})
            d.setdefault('events', [])
            d.setdefault('global_pause_until', 0)
            return d
    except Exception:
        pass
    return {'updated_at': 0, 'items': {}, 'events': [], 'global_pause_until': 0}


def _save(d):
    d['updated_at'] = _now()
    try:
        with open(QF, 'w') as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def _event(d, msg):
    d.setdefault('events', []).insert(0, '[%s] %s' % (time.strftime('%H:%M:%S'), msg))
    del d['events'][25:]


def _is_quarantined(d, key):
    it = d['items'].get(key)
    return bool(it and it.get('until', 0) > _now())


def blocked(d, sym, strat):
    """True — новую сделку по sym/strat открывать нельзя."""
    if d.get('global_pause_until', 0) > _now():
        return True
    return _is_quarantined(d, sym) or _is_quarantined(d, '%s|%s' % (sym, strat))


def _quarantine(d, key, reason, cooldown):
    prev = d['items'].get(key) or {}
    lvl = min(5, int(prev.get('level', 0)) + 1)
    cd = cooldown * (2 ** (lvl - 1))
    d['items'][key] = {'until': _now() + cd, 'reason': reason, 'level': lvl,
                       'pnl': prev.get('pnl', 0)}
    _event(d, 'КАРАНТИН %s (ур.%d, %d мин): %s' % (key, lvl, cd // 60, reason))


def update(universe_list):
    """Анализ закрытых сделок, обновление карантина. Возвращает состояние."""
    d = load()
    now = _now()
    day0 = now - (now % 86400)
    try:
        c = sqlite3.connect(DB, timeout=10)
        rows = c.execute("SELECT symbol, strategy, pnl, exit_ts FROM trades WHERE status='CLOSED' AND exit_ts>0 ORDER BY exit_ts ASC").fetchall()
        c.close()
    except Exception:
        rows = []

    day_pnl = 0.0
    sym_day = {}
    for sym, strat, pnl, ets in rows:
        pnl = pnl or 0
        if ets >= day0:
            day_pnl += pnl
            a = sym_day.setdefault(sym, [0.0, 0])
            a[0] += pnl
            a[1] += 1

    streak_sym = {}
    streak_combo = {}
    for sym, strat, pnl, ets in rows:
        pnl = pnl or 0
        k = '%s|%s' % (sym, strat)
        if pnl < 0:
            streak_sym[sym] = streak_sym.get(sym, 0) + 1
            streak_combo[k] = streak_combo.get(k, 0) + 1
        else:
            streak_sym[sym] = 0
            streak_combo[k] = 0

    for sym, st in streak_sym.items():
        if st >= LOSS_STREAK_SYM and not _is_quarantined(d, sym):
            _quarantine(d, sym, '%d убытков подряд' % st, BASE_COOLDOWN)
    for k, st in streak_combo.items():
        if st >= LOSS_STREAK_COMBO and not _is_quarantined(d, k):
            _quarantine(d, k, '%d убытков подряд по связке' % st, 3 * 3600)
    for sym, (p, n) in sym_day.items():
        if sym in d['items']:
            d['items'][sym]['pnl'] = round(p, 2)
        if n >= MIN_TRADES_DAILY and p <= SYM_DAILY_CAP and not _is_quarantined(d, sym):
            d['items'][sym] = {'until': day0 + 86400, 'level': 5, 'pnl': round(p, 2),
                               'reason': 'дневной лимит: %.2f$ за %d сделок' % (p, n)}
            _event(d, 'КАРАНТИН %s до конца дня: %.2f$' % (sym, p))

    if day_pnl <= GLOBAL_DAILY_CAP and d.get('global_pause_until', 0) < day0 + 86400:
        d['global_pause_until'] = day0 + 86400
        _event(d, 'ГЛОБАЛЬНАЯ ПАУЗА до конца дня: %.2f$' % day_pnl)

    for k in list(d['items'].keys()):
        if d['items'][k].get('until', 0) <= now:
            _event(d, 'возврат в скан: %s (пауза закончилась)' % k)
            del d['items'][k]

    sym_quar = [s for s in d['items'] if '|' not in s]
    limit = max(1, len(universe_list or []) // 2)
    if len(sym_quar) > limit:
        for s in sorted(sym_quar, key=lambda s: d['items'].get(s, {}).get('pnl', 0))[:len(sym_quar) - limit]:
            _event(d, 'защита от массового карантина: %s возвращён в скан' % s)
            del d['items'][s]

    d['day_pnl'] = round(day_pnl, 2)
    _save(d)
    return d
