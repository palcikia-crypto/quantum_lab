import sys, os, subprocess, time, re, json, ast, textwrap
from pathlib import Path
sys.path.append(str(Path.home() / "quantum_lab_sandbox" / "tools" / "agent_dev"))
from llm_backend import ask

SANDBOX = Path.home() / "quantum_lab_sandbox"
TEST_FILE = SANDBOX / "tools" / "scalp_test.py"
GOLDEN_FILE = SANDBOX / "GOLDEN_SCALP.json"
HISTORY_FILE = SANDBOX / "scalp_history.json"
LOG = SANDBOX / ".scalp_lab.log"

INDICATORS = ["RSI", "MACD", "STOCHASTIC", "BOLLINGER", "CCI", "WILLIAMS", "OBV", "ROC"]

TEMPLATE = """import sqlite3

FEE = 0.001
LIMIT = 3000

{INDICATOR}

def fetch(conn, sym):
    cur = conn.cursor()
    cur.execute("SELECT ts, o, h, l, c, v FROM candles WHERE symbol=? AND tf=? ORDER BY ts DESC LIMIT ?", (sym, "15m", LIMIT))
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
    bars = 0
    trades = []
    
    for i in range(1, len(cs)):
        if ind[i] is None or ind[i-1] is None: continue
        ind_cur, ind_prev = ind[i], ind[i-1]
        prev_c, cur_c = closes[i-1], closes[i]
        high, low = cs[i][2], cs[i][3]
        
{SIGNAL}
        
        if pos == 1:
            bars += 1
            if high >= entry * 1.005: trades.append(0.005 - FEE*2); pos = 0
            elif low <= entry * 0.997: trades.append(-0.003 - FEE*2); pos = 0
            elif bars >= 8:
                pnl = (cur_c - entry) / entry - FEE*2; trades.append(pnl); pos = 0
        elif pos == -1:
            bars += 1
            if low <= entry * 0.995: trades.append(0.005 - FEE*2); pos = 0
            elif high >= entry * 1.003: trades.append(-0.003 - FEE*2); pos = 0
            elif bars >= 8:
                pnl = (entry - cur_c) / entry - FEE*2; trades.append(pnl); pos = 0
    
    return sum(trades)

def main():
    conn = sqlite3.connect("data/market.db")
    total = 0.0
    for s in ["BTCUSDT","ETHUSDT","SOLUSDT","DOGEUSDT"]:
        total += bt(conn, s)
    print(f"ИТОГО: {total}")
    conn.close()

if __name__ == "__main__":
    main()
"""

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def load_history():
    if HISTORY_FILE.exists():
        try: return json.loads(HISTORY_FILE.read_text())
        except: pass
    return []

def save_history(h):
    HISTORY_FILE.write_text(json.dumps(h, indent=2))

def detect_indicator(code):
    c = code.lower()
    for kw, name in [("rsi", "RSI"), ("macd", "MACD"), ("stoch", "STOCHASTIC"),
                     ("bollinger", "BOLLINGER"), ("cci", "CCI"), ("williams", "WILLIAMS"),
                     ("obv", "OBV"), ("roc", "ROC")]:
        if kw in c: return name
    return "UNKNOWN"

def build_prompt(history):
    tried = ", ".join(history) if history else "ничего"
    return f"""Напиши функцию my_indicator(prices) для СКАЛЬПИНГА на 15m свечах.
Доступны ТОЛЬКО цены закрытия (prices). Нет high/low/volume.

УЖЕ ПРОБОВАЛ: {tried}
ВЫБЕРИ НОВЫЙ из: RSI, MACD, Stochastic, Bollinger, CCI, Williams, OBV, ROC.

Вспомогательные функции (SMA, EMA) ОПРЕДЕЛЯЙ ВНУТРИ my_indicator.
Первые N элементов = None. Длина = len(prices).

ТОЛЬКО код функции."""

def is_valid(code):
    try:
        ast.parse(code); return True, ""
    except Exception as e:
        return False, str(e)

def ask_clean(prompt, error_ctx=None, prev_code=None):
    full = prompt
    if error_ctx:
        full += "\n\n"
        if prev_code: full += "ТВОЙ СЛОМАННЫЙ КОД:\n" + prev_code + "\n\n"
        full += "ОШИБКА:\n" + error_ctx + "\n\nИСПРАВЬ."
    for a in range(2):
        try:
            r = ask(full, system_prompt="Пиши ТОЛЬКО код на чистом Python. Без numpy, pandas.").strip()
            r = r.replace("```python", "").replace("```", "").strip()
            if not r: continue
            if any(x in r for x in ["numpy", "pandas", "talib"]): continue
            r = textwrap.dedent(r).strip()
            ok, err = is_valid(r)
            if ok: return r
            log("   AST: " + err[:60])
        except Exception as e:
            log("   " + str(e))
        time.sleep(3)
    return None

def get_pnl(out):
    for line in out.split("\n"):
        if "ИТОГО" in line:
            nums = re.findall(r"-?\d+\.?\d*", line)
            if nums:
                try: return float(nums[-1])
                except: pass
    return -99999.0

def main():
    log("🎯 SCALP LAB: Поиск скальпинг-стратегий (15m, TP 0.5%, SL 0.3%)")
    
    best_pnl = -99999.0
    if GOLDEN_FILE.exists():
        try:
            d = json.loads(GOLDEN_FILE.read_text())
            best_pnl = d.get("pnl", best_pnl)
        except: pass
    log(f"📊 Стартовый PnL: {best_pnl}")
    
    history = load_history()
    log(f"📚 История: {', '.join(history) if history else 'пусто'}")
    
    iteration = 0
    while True:
        iteration += 1
        log(f"\n--- ИТЕРАЦИЯ {iteration} ---")
        
        if len(history) >= len(INDICATORS):
            log("📚 Все индикаторы попробованы. Сброс.")
            history = []
            save_history(history)
        
        log("🤖 Генерирую индикатор...")
        ind_func = ask_clean(build_prompt(history))
        if not ind_func or "def my_indicator" not in ind_func:
            time.sleep(30); continue
        
        detected = detect_indicator(ind_func)
        log(f"🎯 ИИ выбрал: {detected}")
        if detected not in history and detected != "UNKNOWN":
            history.append(detected)
            save_history(history)
        
        log(f"🤖 Генерирую сигнал для {detected}...")
        signal_prompt = f"""Напиши ТОЛЬКО условие входа (if/elif), 3-5 строк.
Переменные: i, prev_c, cur_c, ind_cur, ind_prev, pos, entry.
Индикатор: {detected}

КРИТИЧЕСКИ ВАЖНО: Вход ТОЛЬКО если pos == 0!
Для скальпинга нужны ТОЧНЫЕ сигналы (RSI<25 для LONG, RSI>75 для SHORT).

if pos == 0 and <условие LONG>:
    pos = 1
    entry = cur_c
elif pos == 0 and <условие SHORT>:
    pos = -1
    entry = cur_c

ТОЛЬКО эти строки."""
        
        signal = ask_clean(signal_prompt)
        if not signal:
            time.sleep(30); continue
        
        signal_indented = textwrap.indent(signal, "        ")
        code = TEMPLATE.replace("{INDICATOR}", ind_func).replace("{SIGNAL}", signal_indented)
        
        ok, err = is_valid(code)
        if not ok:
            log(f"❌ AST: {err[:80]}")
            time.sleep(30); continue
        
        TEST_FILE.write_text(code)
        log("🧪 Тестирую на 15m...")
        r = subprocess.run(["python3", str(TEST_FILE)], cwd=SANDBOX, capture_output=True, text=True, timeout=90)
        out = r.stdout + r.stderr
        pnl = get_pnl(out)
        
        if pnl == -99999.0:
            log(f"❌ Ошибка: {out[-120:]}")
        elif pnl > best_pnl:
            log(f"🏆 РЕКОРД! PnL: {pnl:.4f} [{detected}]")
            best_pnl = pnl
            GOLDEN_FILE.write_text(json.dumps({"iter": iteration, "pnl": pnl, "indicator": detected, "history": history, "full_code": code}, indent=2))
            log("💾 Сохранено в GOLDEN_SCALP.json")
        else:
            log(f"📉 PnL {pnl:.4f} <= {best_pnl:.4f}. Откат.")
        
        log("💤 Пауза 30с...")
        time.sleep(30)

if __name__ == "__main__":
    main()
