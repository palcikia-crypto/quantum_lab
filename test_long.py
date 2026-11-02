import sqlite3

FEE = 0.001
LIMIT = 30000

def my_indicator(prices):
    # Рассчитываем RSI (Relative Strength Index)
    result_list = [None] * len(prices)
    period = 14

    if len(prices) < period:
        return result_list

    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            losses.append(-change)
            gains.append(0)

        if i >= period:
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            result_list[i] = rsi

    return result_list

def fetch(conn, sym):
    cur = conn.cursor()
    cur.execute("SELECT ts, o, h, l, c, v FROM candles WHERE symbol=? AND tf=? ORDER BY ts DESC LIMIT ?", (sym, "4h", LIMIT))
    return cur.fetchall()[::-1]

def bt(conn, sym):
    cs = fetch(conn, sym)
    if len(cs) < 30: return 0.0
    closes = [r[4] for r in cs]
    ind = my_indicator(closes)
    
    if not isinstance(ind, (list, tuple)):
        ind = [ind] * len(closes)
    
    if len(ind) < len(cs):
        ind = [None] * (len(cs) - len(ind)) + list(ind)
    elif len(ind) > len(cs):
        ind = list(ind)[-len(cs):]
    
    pos = 0
    entry = 0.0
    trades = []
    
    for i in range(1, len(cs)):
        if ind[i] is None or ind[i-1] is None: continue
        ind_cur, ind_prev = ind[i], ind[i-1]
        prev_c, cur_c = closes[i-1], closes[i]
        high, low = cs[i][2], cs[i][3]
        
        if ind_cur < 30 and prev_c > cur_c:
            pos = 1
            entry = cur_c
        elif ind_cur > 70 and prev_c < cur_c:
            pos = -1
            entry = cur_c
        
        if pos == 1:
            if high >= entry * 1.02: trades.append(0.02 - FEE*2); pos = 0
            elif low <= entry * 0.99: trades.append(-0.01 - FEE*2); pos = 0
        elif pos == -1:
            if low <= entry * 0.98: trades.append(0.02 - FEE*2); pos = 0
            elif high >= entry * 1.01: trades.append(-0.01 - FEE*2); pos = 0
    
    return sum(trades)

def main():
    conn = sqlite3.connect("data/market.db")
    total = 0.0
    for s in ["BTCUSDT","ETHUSDT","SOLUSDT","DOGEUSDT","XRPUSDT","ADAUSDT","ARBUSDT","AVAXUSDT","BNBUSDT","DOTUSDT","LINKUSDT"]:
        total += bt(conn, s)
    print(f"ИТОГО: {total}")
    conn.close()

if __name__ == "__main__":
    main()
