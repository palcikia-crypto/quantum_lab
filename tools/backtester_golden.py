import sqlite3
import json
import os

def load_config():
    # Берем okx_active.json, так как там структура проще (pairs)
    if os.path.exists('data/okx_active.json'):
        with open('data/okx_active.json', 'r') as f:
            return json.load(f)
    return {}

def fetch_candles(conn, symbol, tf, limit=1000):
    cur = conn.cursor()
    cur.execute("SELECT ts, o, h, l, c, v FROM candles WHERE symbol = ? AND tf = ? ORDER BY ts DESC LIMIT ?", (symbol, tf, limit))
    return cur.fetchall()[::-1]

def sma_series(prices, window):
    out = [None] * len(prices)
    for i in range(window - 1, len(prices)):
        out[i] = sum(prices[i - window + 1:i + 1]) / window
    return out

def run_backtest(symbol_db, strat, tp, sl, tf='15m'):
    conn = sqlite3.connect('data/market.db')
    candles = fetch_candles(conn, symbol_db, tf)
    conn.close()
    
    if len(candles) < 30:
        return None

    closes = [row[4] for row in candles]
    trades = []
    position = 0
    entry_price = 0.0

    if 'sma' in strat:
        try:
            period = int(strat.split('_')[-1])
        except:
            period = 13
        indicator = sma_series(closes, period)
    else:
        return None

    for i in range(1, len(candles)):
        if indicator[i] is None or indicator[i-1] is None:
            continue

        high, low, close = candles[i][2], candles[i][3], candles[i][4]
        prev_c, cur_c = closes[i-1], closes[i]
        ind = indicator[i]

        # Выход по TP/SL
        if position == 1:
            if high >= entry_price * (1 + tp):
                trades.append(tp - 0.001) # минус комиссия
                position = 0
            elif low <= entry_price * (1 - sl):
                trades.append(-sl - 0.001)
                position = 0
        elif position == -1:
            if low <= entry_price * (1 - tp):
                trades.append(tp - 0.001)
                position = 0
            elif high >= entry_price * (1 + sl):
                trades.append(-sl - 0.001)
                position = 0

        # Вход (Grid SMA: если цена ниже SMA - лонг, если выше - шорт)
        if position == 0:
            if cur_c < ind * 0.995: # отклонилась вниз на 0.5%
                position = 1; entry_price = cur_c
            elif cur_c > ind * 1.005: # отклонилась вверх на 0.5%
                position = -1; entry_price = cur_c

    if not trades:
        return None

    wins = sum(1 for t in trades if t > 0)
    total_pnl = sum(trades) * 100
    
    return {
        "symbol": symbol_db, "strategy": strat,
        "trades": len(trades), "wins": wins, "wr": (wins/len(trades))*100,
        "pnl_pct": total_pnl
    }

def main():
    config = load_config()
    pairs = config.get('pairs', {})
    
    if not pairs:
        print("❌ Конфиг пуст или не найден (okx_active.json)")
        return

    print(f"{'Символ':<12} {'Стратегия':<18} {'Сделок':>6} {'WR':>7} {'PnL%':>9}")
    print("-" * 60)
    
    total_pnl = 0
    count = 0
    for key, data in pairs.items():
        sym_dash = data.get('symbol', '')
        strat = data.get('strategy', 'okx_grid_sma_13')
        tp = data.get('tp', 0.005)
        sl = data.get('sl', 0.003)
        tf = data.get('tf', '15m')
        
        # Убираем дефис для базы данных (SOL-USDT -> SOLUSDT)
        sym_db = sym_dash.replace('-', '')
        
        res = run_backtest(sym_db, strat, tp, sl, tf)
        if res:
            print(f"{res['symbol']:<12} {res['strategy']:<18} {res['trades']:>6} {res['wr']:>6.1f}% {res['pnl_pct']:>8.2f}%")
            total_pnl += res['pnl_pct']
            count += 1

    print("-" * 60)
    if count > 0:
        print(f"ИТОГО PnL: {round(total_pnl, 2)}% (средний по {count} парам)")
    else:
        print("❌ Ни одна пара не дала сделок (проверь данные в БД)")

if __name__ == "__main__":
    main()
