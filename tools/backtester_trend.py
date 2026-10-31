import sqlite3

def fetch_candles(conn, symbol, tf, limit=2000):
    cur = conn.cursor()
    cur.execute("SELECT ts, o, h, l, c, v FROM candles WHERE symbol = ? AND tf = ? ORDER BY ts DESC LIMIT ?", (symbol, tf, limit))
    return cur.fetchall()[::-1]

def sma_series(prices, window):
    out = [None] * len(prices)
    for i in range(window - 1, len(prices)):
        out[i] = sum(prices[i - window + 1:i + 1]) / window
    return out

def run(symbol, fast_w, slow_w, tp, sl):
    conn = sqlite3.connect('data/market.db')
    candles = fetch_candles(conn, symbol, '15m')
    conn.close()
    
    if len(candles) < slow_w + 2: return None

    closes = [row[4] for row in candles]
    fast = sma_series(closes, fast_w)
    slow = sma_series(closes, slow_w)

    trades = []
    pos = 0
    entry = 0.0
    FEE = 0.001

    for i in range(1, len(candles)):
        # ВОТ ЗДЕСЬ ИСПРАВЛЕНИЕ: проверяем и текущие, и предыдущие значения
        if fast[i] is None or slow[i] is None or fast[i-1] is None or slow[i-1] is None:
            continue
            
        high, low, cur_c = candles[i][2], candles[i][3], candles[i][4]

        # Выход
        if pos == 1:
            if high >= entry * (1 + tp): trades.append(tp - FEE*2); pos = 0
            elif low <= entry * (1 - sl): trades.append(-sl - FEE*2); pos = 0
        elif pos == -1:
            if low <= entry * (1 - tp): trades.append(tp - FEE*2); pos = 0
            elif high >= entry * (1 + sl): trades.append(-sl - FEE*2); pos = 0

        # Вход (Тренд: fast crosses slow)
        if pos == 0:
            if fast[i-1] <= slow[i-1] and fast[i] > slow[i]: # бычий тренд
                pos = 1; entry = cur_c
            elif fast[i-1] >= slow[i-1] and fast[i] < slow[i]: # медвежий
                pos = -1; entry = cur_c

    if not trades: return None
    wins = sum(1 for t in trades if t > 0)
    return {"sym": symbol, "n": len(trades), "wr": (wins/len(trades))*100, "pnl": sum(trades)*100}

print(f"{'Символ':<10} {'SMA':<8} {'Сделок':>6} {'WR':>7} {'PnL%':>9}")
print("-" * 50)
for sym in ['BTCUSDT', 'SOLUSDT', 'DOGEUSDT', 'ETHUSDT', 'XRPUSDT']:
    # Пробуем классический тренд: SMA 9 и SMA 21, TP 1%, SL 0.5%
    r = run(sym, 9, 21, 0.01, 0.005)
    if r: print(f"{r['sym']:<10} 9/21 {r['n']:>6} {r['wr']:>6.1f}% {r['pnl']:>8.2f}%")
