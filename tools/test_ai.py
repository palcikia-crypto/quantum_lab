import sqlite3

FEE = 0.001
LIMIT = 1000

def my_indicator(prices):
    def calculate_obv(prices):
        obv = [None] * len(prices)
        for i in range(1, len(prices)):
            if prices[i] > prices[i - 1]:
                obv[i] = obv[i - 1] + prices[i]
            elif prices[i] < prices[i - 1]:
                obv[i] = obv[i - 1] - prices[i]
            else:
                obv[i] = obv[i - 1]
        return obv

    return calculate_obv(prices)

def normalize_ind(raw, length):
    if raw is None: return [None] * length
    if not isinstance(raw, (list, tuple)):
        try: return [float(raw)] * length
        except: return [None] * length
    cleaned = []
    for x in raw:
        if x is None: cleaned.append(None)
        elif isinstance(x, (int, float)): cleaned.append(float(x))
        elif isinstance(x, (list, tuple)) and len(x) > 0:
            try:
                nums = [float(v) for v in x if isinstance(v, (int, float))]
                cleaned.append(sum(nums)/len(nums) if nums else None)
            except: cleaned.append(None)
        else: cleaned.append(None)
    if len(cleaned) < length: cleaned = [None] * (length - len(cleaned)) + cleaned
    elif len(cleaned) > length: cleaned = cleaned[-length:]
    return cleaned

def fetch(conn, sym):
    cur = conn.cursor()
    cur.execute("SELECT ts, o, h, l, c, v FROM candles WHERE symbol=? AND tf=? ORDER BY ts DESC LIMIT ?", (sym, "4h", LIMIT))
    return cur.fetchall()[::-1]

def bt(conn, sym):
    cs = fetch(conn, sym)
    if len(cs) < 30: return 0.0
    closes = [r[4] for r in cs]
    ind = normalize_ind(my_indicator(closes), len(cs))
    pos = 0
    entry = 0.0
    trades = []
    for i in range(1, len(cs)):
        if ind[i] is None or ind[i-1] is None: continue
        ind_cur, ind_prev = ind[i], ind[i-1]
        prev_c, cur_c = closes[i-1], closes[i]
        high, low = cs[i][2], cs[i][3]
        if pos == 0 and (ind_cur > ind_prev) and (cur_c > prev_c):
            pos = 1
            entry = cur_c
        elif pos == 0 and (ind_cur < ind_prev) and (cur_c < prev_c):
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
    for s in ["BTCUSDT","ETHUSDT","SOLUSDT","DOGEUSDT","XRPUSDT"]:
        total += bt(conn, s)
    print(f"ИТОГО: {total}")
    conn.close()

if __name__ == "__main__":
    main()
