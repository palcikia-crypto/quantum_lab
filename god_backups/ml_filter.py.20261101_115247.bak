#!/usr/bin/env python3
"""ml_filter.py — фильтр ML для v3/v4 (читает ml_predictions.json)."""
import os, json, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
PREDICTIONS = os.path.join(BASE, 'data/ml_predictions.json')
LOG = os.path.join(BASE, 'logs/ml_filter.log')

# Пороги
PROBA_LONG_MIN = 0.6
PROBA_SHORT_MAX = 0.4

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def load_predictions():
    """Загружает predictions (не старше 30 мин)."""
    if not os.path.exists(PREDICTIONS):
        return {}
    try:
        d = json.load(open(PREDICTIONS))
        updated = d.get('updated_at', '')
        # Проверяем свежесть (30 мин)
        if updated:
            ts = datetime.fromisoformat(updated).timestamp()
            if time.time() - ts > 30*60:
                log(f'⚠️ predictions устарели ({int((time.time()-ts)/60)} мин)')
                return {}
        return d.get('predictions', {})
    except:
        return {}

def check(sym, side):
    """Проверяет ML-фильтр для пары/стороны.
    sym: 'XRP-USDT' (с дефисом) или 'XRPUSDT'
    side: 'LONG' / 'SHORT'
    """
    preds = load_predictions()
    if not preds:
        return True, 'ML нет данных (пропускаем)'

    # Нормализуем symbol (XRP-USDT → XRPUSDT)
    sym_norm = sym.replace('-', '')

    if sym_norm not in preds:
        return True, f'ML нет {sym_norm} (пропускаем)'

    p = preds[sym_norm]
    proba = p.get('proba_long', 0.5)
    ml_side = p.get('side', 'WAIT')

    if side == 'LONG':
        if proba >= PROBA_LONG_MIN:
            return True, f'ML LONG ok (proba={proba:.3f})'
        else:
            return False, f'ML против LONG (proba={proba:.3f} < {PROBA_LONG_MIN})'
    elif side == 'SHORT':
        if proba <= PROBA_SHORT_MAX:
            return True, f'ML SHORT ok (proba={proba:.3f})'
        else:
            return False, f'ML против SHORT (proba={proba:.3f} > {PROBA_SHORT_MAX})'

    return True, 'ML неизвестная сторона'

if __name__ == '__main__':
    log('=== ML FILTER TEST ===')
    preds = load_predictions()
    log(f'Predictions: {len(preds)}')
    for sym in ['XRP-USDT', 'ETH-USDT', 'SOL-USDT', 'DOGE-USDT', 'BTC-USDT']:
        ok_long, reason_long = check(sym, 'LONG')
        ok_short, reason_short = check(sym, 'SHORT')
        log(f'{sym}:')
        log(f'  LONG:  {ok_long} ({reason_long})')
        log(f'  SHORT: {ok_short} ({reason_short})')
