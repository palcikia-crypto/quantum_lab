import sys, os, subprocess, time, re, json, ast, textwrap
from pathlib import Path

sys.path.append(str(Path.home() / "quantum_lab_sandbox" / "tools" / "agent_dev"))
from llm_backend import ask

SANDBOX = Path.home() / "quantum_lab_sandbox"
TEST_FILE = SANDBOX / "tools" / "test_ai.py"
GOLDEN_FILE = SANDBOX / "GOLDEN_AI.json"
LOG = SANDBOX / ".strategy_lab.log"

INDICATORS = ['RSI', 'WILLIAMS', 'MACD', 'BOLLINGER', 'ROC', 'OBV']

TEMPLATE = '''import sqlite3

FEE = 0.001
LIMIT = 1000

{INDICATOR}

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
{SIGNAL}
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
    with open(LOG, "a") as f: f.write(line + chr(10))

def has_bad_calls(code):
    for fn in ["SMA", "EMA", "CCI", "ATR", "STOCHASTIC"]:
        if fn + "(" in code and "def " + fn not in code:
            return fn
    return None

def is_valid(code):
    try:
        ast.parse(code)
        return True, ""
    except Exception as e:
        return False, str(e)

def get_pnl(out):
    for line in out.split(chr(10)):
        if "ИТОГО" in line:
            nums = re.findall(r"-?\d+\.?\d*", line)
            if nums:
                try: return float(nums[-1])
                except: pass
    return -99999.0

def ask_safe(prompt, error=None):
    for a in range(3):
        try:
            p = prompt
            if error:
                p = p + chr(10) + chr(10) + "ОШИБКА:" + chr(10) + error + chr(10) + chr(10) + "ИСПРАВЬ."
            r = ask(p, system_prompt="Пиши ТОЛЬКО код. Без markdown, без numpy, pandas.")
            if not r: continue
            r = r.replace("```python", "").replace("```", "").strip()
            if not r: continue
            if "numpy" in r or "pandas" in r or "talib" in r:
                log("   bad_lib")
                continue
            r = textwrap.dedent(r).strip()
            bad = has_bad_calls(r)
            if bad:
                log("   bad_call " + bad)
                continue
            ok, err = is_valid(r)
            if ok: return r
            log("   ast " + err[:60])
        except Exception as e:
            log("   err " + str(e))
        time.sleep(3)
    return None

def main():
    log("=== QUANT LAB ===")
    best = -99999.0
    if GOLDEN_FILE.exists():
        try:
            d = json.loads(GOLDEN_FILE.read_text())
            best = d.get("pnl", best)
        except: pass
    log("base_pnl=" + str(best))
    
    iteration = 0
    while True:
        iteration += 1
        indicator = INDICATORS[(iteration - 1) % len(INDICATORS)]
        log("--- iter " + str(iteration) + " | " + indicator + " ---")
        
        ind_prompt = (
            "Напиши my_indicator(prices) для " + indicator + "." + chr(10) +
            "ТОЛЬКО стандартный Python (без numpy, pandas)." + chr(10) +
            "Вспомогательные функции определяй ВНУТРИ через def." + chr(10) +
            "Не используй SMA(), EMA(), CCI() без def." + chr(10) +
            "Первые N элементов = None. Длина = len(prices)." + chr(10) +
            chr(10) + "Выведи ТОЛЬКО код функции."
        )
        ind = ask_safe(ind_prompt)
        if not ind or "def my_indicator" not in ind:
            log("no_indicator")
            time.sleep(20); continue
        
        sig_prompt = (
            "Напиши ТОЛЬКО условие входа для " + indicator + "." + chr(10) +
            "Переменные: pos, ind_cur, ind_prev, prev_c, cur_c, entry." + chr(10) +
            "pos == 0 обязательное условие входа." + chr(10) +
            chr(10) + "if pos == 0 and <LONG>:" + chr(10) +
            "    pos = 1" + chr(10) +
            "    entry = cur_c" + chr(10) +
            "elif pos == 0 and <SHORT>:" + chr(10) +
            "    pos = -1" + chr(10) +
            "    entry = cur_c" + chr(10) +
            chr(10) + "ТОЛЬКО эти строки."
        )
        sig = ask_safe(sig_prompt)
        if not sig:
            log("no_signal")
            time.sleep(20); continue
        
        sig_indented = textwrap.indent(sig, "        ")
        code = TEMPLATE.replace("{INDICATOR}", ind).replace("{SIGNAL}", sig_indented)
        
        ok, err = is_valid(code)
        if not ok:
            log("ast_full " + err[:60])
            time.sleep(20); continue
        
        TEST_FILE.write_text(code)
        log("testing...")
        try:
            r = subprocess.run(["python3", str(TEST_FILE)], cwd=SANDBOX, capture_output=True, text=True, timeout=60)
            out = r.stdout + r.stderr
            pnl = get_pnl(out)
        except Exception as e:
            log("run_err " + str(e))
            time.sleep(20); continue
        
        if pnl == -99999.0:
            log("fail " + out[-100:])
            ind2 = ask_safe(ind_prompt, error=out[-300:])
            if ind2 and "def my_indicator" in ind2:
                bad = has_bad_calls(ind2)
                if not bad:
                    code2 = TEMPLATE.replace("{INDICATOR}", ind2).replace("{SIGNAL}", sig_indented)
                    if is_valid(code2)[0]:
                        TEST_FILE.write_text(code2)
                        try:
                            r = subprocess.run(["python3", str(TEST_FILE)], cwd=SANDBOX, capture_output=True, text=True, timeout=60)
                            out = r.stdout + r.stderr
                            pnl = get_pnl(out)
                        except: pass
        if pnl != -99999.0:
            if pnl > best:
                log("NEW_RECORD " + str(pnl) + " > " + str(best) + " [" + indicator + "]")
                best = pnl
                GOLDEN_FILE.write_text(json.dumps({"iter": iteration, "pnl": pnl, "indicator": indicator, "full_code": code}, indent=2))
            else:
                log("worse " + str(pnl) + " <= " + str(best))
        
        time.sleep(20)

if __name__ == "__main__":
    main()
