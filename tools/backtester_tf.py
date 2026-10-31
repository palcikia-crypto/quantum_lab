import sqlite3

def fetch_candles(conn, symbol, tf, limit=1000):
    cur = conn.cursor()
    cur.execute("SELECT ts, o, h, l, c, v FROM candles WHERE symbol = ? AND tf = ? ORDER BY ts DESC LIMIT ?", (symbol, tf, limit))
    return cur.fetchall()[::-1]

def sma_series(prices, window):
    out = [None] * len(prices)
    for i in range(window - 1, len(prices)):
        out[i] = sum(prices[i - window + 1:i + 1]) / window
    return out

def run(symbol, tf, fast_w, slow_w, tp, sl):
    conn = sqlite3.connect('data/market.db')
    candles = fetch_candles(conn, symbol, tf)
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
        if fast[i] is None or slow[i] is None or fast[i-1] is None or slow[i-1] is None:
            continue
            
        high, low, cur_c = candles[i][2], candles[i][3], candles[i][4]

        if pos == 1:
            if high >= entry * (1 + tp): trades.append(tp - FEE*2); pos = 0
            elif low <= entry * (1 - sl): trades.append(-sl - FEE*2); pos = 0
        elif pos == -1:
            if low <= entry * (1 - tp): trades.append(tp - FEE*2); pos = 0
            elif high >= entry * (1 + sl): trades.append(-sl - FEE*2); pos = 0

        if pos == 0:
            if fast[i-1] <= slow[i-1] and fast[i] > slow[i]:
                pos = 1; entry = cur_c
            elif fast[i-1] >= slow[i-1] and fast[i] < slow[i]:
                pos = -1; entry = cur_c

    if not trades: return 0, 0, 0.0
    wins = sum(1 for t in trades if t > 0)
    return len(trades), (wins/len(trades))*100, sum(trades)*100

for tf in ['1h', '4h']:
    print(f"\n=== ТАЙМФРЕЙМ: {tf} ===")
    print(f"{'Символ':<10} {'Сделок':>6} {'WR':>7} {'PnL%':>9}")
    print("-" * 40)
    for sym in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT']:
        n, wr, pnl = run(sym, tf, 9, 21, 0.02, 0.01) # TP 2%, SL 1%
        if n > 0:
            print(f"{sym:<10} {n:>6} {wr:>6.1f}% {pnl:>8.2f}%")
