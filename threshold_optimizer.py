import subprocess, time, json, sqlite3, os, random, re
from pathlib import Path

SANDBOX = Path.home() / "quantum_lab_sandbox"
GOLDEN = SANDBOX / "GOLDEN_AI.json"
THRESH_BEST = SANDBOX / "THRESH_BEST.json"
LOG = SANDBOX / ".threshold.log"

TEMPLATE = '''import sqlite3

FEE = 0.001
LIMIT = 1000

def my_indicator(prices):
    result = [None] * len(prices)
    n = 14
    if len(prices) < n: return result
    for i in range(n - 1, len(prices)):
        window = prices[i - n + 1:i + 1]
        hh = max(window)
        ll = min(window)
        if hh == ll: result[i] = -50.0
        else: result[i] = (hh - prices[i]) / (hh - ll) * -100
    return result

def fetch(conn, sym):
    cur = conn.cursor()
    cur.execute("SELECT ts, o, h, l, c, v FROM candles WHERE symbol=? AND tf=? ORDER BY ts DESC LIMIT ?", (sym, "4h", LIMIT))
    return cur.fetchall()[::-1]

def bt(conn, sym):
    cs = fetch(conn, sym)
    if len(cs) < 30: return 0.0
    closes = [r[4] for r in cs]
    ind = my_indicator(closes)
    pos = 0
    entry = 0.0
    trades = []
    for i in range(1, len(cs)):
        if ind[i] is None or ind[i-1] is None: continue
        ind_cur = ind[i]
        cur_c = closes[i]
        high = cs[i][2]
        low = cs[i][3]
        if pos == 0 and ind_cur < LONG_THR:
            pos = 1; entry = cur_c
        elif pos == 0 and ind_cur > SHORT_THR:
            pos = -1; entry = cur_c
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
'''

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = "[" + ts + "] " + msg
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + chr(10))
    except: pass

def get_pnl(out):
    for line in out.split(chr(10)):
        if "ИТОГО" in line:
            nums = re.findall(r"-?\d+\.?\d*", line)
            if nums:
                try: return float(nums[-1])
                except: pass
    return -99999.0

def test_thresholds(long_thr, short_thr):
    code = TEMPLATE.replace("LONG_THR", str(long_thr)).replace("SHORT_THR", str(short_thr))
    test_file = SANDBOX / "tools" / "_thresh_test.py"
    test_file.write_text(code)
    try:
        r = subprocess.run(["python3", str(test_file)], cwd=SANDBOX, capture_output=True, text=True, timeout=60)
        out = r.stdout + r.stderr
        return get_pnl(out)
    except: return -99999.0

def main():
    log("=== THRESHOLD OPTIMIZER v2 (бесконечный) ===")
    
    best_pnl = 0.582
    if GOLDEN.exists():
        try:
            d = json.loads(GOLDEN.read_text())
            best_pnl = d.get("pnl", best_pnl)
        except: pass
    log("baseline=" + str(best_pnl))
    
    history = {}
    if THRESH_BEST.exists():
        try:
            history = json.loads(THRESH_BEST.read_text())
        except: pass
    
    best_result = history.get("best", {"pnl": best_pnl, "long": -80, "short": -20})
    total_tested = len(history.get("tested", []))
    
    iteration = 0
    while True:
        iteration += 1
        log("--- раунд " + str(iteration) + " (всего протестировано: " + str(total_tested) + ") ---")
        
        # 20 случайных комбинаций за раунд
        for _ in range(20):
            lt = random.randint(-95, -50)
            st = random.randint(-45, -5)
            if lt >= st: continue
            
            key = str(lt) + "_" + str(st)
            if "tested" not in history: history["tested"] = []
            if key in history["tested"]: continue
            
            log("test L=" + str(lt) + " S=" + str(st))
            pnl = test_thresholds(lt, st)
            history["tested"].append(key)
            total_tested += 1
            
            if pnl > best_result["pnl"]:
                log("NEW_BEST " + str(pnl) + " L=" + str(lt) + " S=" + str(st))
                best_result = {"pnl": pnl, "long": lt, "short": st}
                history["best"] = best_result
                THRESH_BEST.write_text(json.dumps(history, indent=2))
                
                # Обновляем GOLDEN_AI.json если лучше
                if pnl > best_pnl:
                    final_code = TEMPLATE.replace("LONG_THR", str(lt)).replace("SHORT_THR", str(st))
                    GOLDEN.write_text(json.dumps({
                        "iter": 0, "pnl": pnl, "indicator": "WILLIAMS_OPT",
                        "long_thr": lt, "short_thr": st,
                        "full_code": final_code
                    }, indent=2))
                    best_pnl = pnl
                    log("SAVED_TO_GOLDEN")
            else:
                log("  worse " + str(round(pnl, 3)))
            
            time.sleep(1)
        
        history["best"] = best_result
        THRESH_BEST.write_text(json.dumps(history, indent=2))
        
        log("раунд " + str(iteration) + " завершён. best=" + str(best_result["pnl"]) + " L=" + str(best_result["long"]) + " S=" + str(best_result["short"]))
        time.sleep(10)

if __name__ == "__main__":
    main()
