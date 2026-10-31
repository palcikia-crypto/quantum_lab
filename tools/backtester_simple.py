import sqlite3

FEE = 0.001  # 0.1% комиссия
SMA_WINDOW = 20
LIMIT_CANDLES = 1000  # Берем последние 1000 свечей

def fetch_candles(conn, symbol, tf):
    cur = conn.cursor()
    # Берем ПОСЛЕДНИЕ свечи (ORDER BY ts DESC)
    cur.execute("""
        SELECT ts, o, h, l, c, v
        FROM candles
        WHERE symbol = ? AND tf = ?
        ORDER BY ts DESC
        LIMIT ?
    """, (symbol, tf, LIMIT_CANDLES))
    rows = cur.fetchall()
    return rows[::-1]  # Переворачиваем обратно (от старых к новым)

def sma_series(prices, window):
    out = [None] * len(prices)
    for i in range(window - 1, len(prices)):
        out[i] = sum(prices[i - window + 1:i + 1]) / window
    return out

def backtest_symbol(conn, symbol, tf):
    candles = fetch_candles(conn, symbol, tf)
    if len(candles) < SMA_WINDOW + 2:
        return {"symbol": symbol, "trades": 0, "wins": 0, "pnl": 0.0, "wr": 0.0}

    closes = [row[4] for row in candles]
    smas = sma_series(closes, SMA_WINDOW)

    position = 0
    entry = 0.0
    trades = []
    wins = 0

    for i in range(1, len(candles)):
        if smas[i] is None or smas[i-1] is None:
            continue

        prev_c, cur_c = closes[i-1], closes[i]
        prev_s, cur_s = smas[i-1], smas[i]

        if position == 0 and prev_c <= prev_s and cur_c > cur_s:
            position = 1
            entry = cur_c
        elif position == 1 and prev_c >= prev_s and cur_c < cur_s:
            position = 0
            gross = cur_c - entry
            fee = (entry + cur_c) * FEE
            pnl = gross - fee
            trades.append(pnl)
            if pnl > 0:
                wins += 1

    total_pnl = sum(trades)
    n = len(trades)
    wr = (wins / n * 100) if n else 0.0
    return {"symbol": symbol, "trades": n, "wins": wins,
            "pnl": round(total_pnl, 2), "wr": round(wr, 2)}

def main():
    conn = sqlite3.connect('data/market.db')
    tf = '15m'
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT']

    print(f"{'Символ':<12} {'Сделок':>8} {'Побед':>7} {'WinRate':>9} {'PnL (USDT)':>14}")
    print("-" * 56)

    total_trades = 0
    total_pnl = 0.0

    for sym in symbols:
        r = backtest_symbol(conn, sym, tf)
        print(f"{r['symbol']:<12} {r['trades']:>8} {r['wins']:>7} {r['wr']:>8.2f}% {r['pnl']:>14.2f}")
        total_trades += r['trades']
        total_pnl += r['pnl']

    print("-" * 56)
    print(f"{'ИТОГО':<12} {total_trades:>8} {'':>7} {'':>9} {round(total_pnl, 2):>14.2f}")

    conn.close()

if __name__ == "__main__":
    main()
