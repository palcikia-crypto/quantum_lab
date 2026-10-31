#!/usr/bin/env python3
"""ai_generator.py — автономный AI-генератор стратегий.
Безопасно: только ai_strategies.py, только rslab2, ботов НЕ трогает."""
import os, sys, json, time, subprocess, re, ast, shutil
from datetime import datetime

BASE = os.path.expanduser('~/rsbot')
AI_FILE = os.path.join(BASE, 'ai_strategies.py')
LOG_FILE = os.path.join(BASE, 'ai_generator.log')
RESULTS_FILE = os.path.join(BASE, 'ai_generator_results.json')
BEST_FILE = os.path.join(BASE, 'ai_best_strategies.json')

GENERATE_EVERY_HOURS = 2
MAX_STRATEGIES_PER_DAY = 8
MIN_WR_KEEP = 54.0
MIN_N_KEEP = 200
MIN_P_KEEP = 0.001
TEST_TIMEOUT = 600

def log(m):
    t = datetime.now().strftime('%H:%M:%S')
    line = f"[{t}] {m}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f: f.write(line + '\n')
    except: pass

def strategies_today():
    try:
        d = json.load(open(RESULTS_FILE))
        today = datetime.now().strftime('%Y-%m-%d')
        return sum(1 for r in d.get('history', []) if r.get('date') == today)
    except: return 0

BANNED_FILE = os.path.join(BASE, 'ai_banned_names.json')

def get_existing_names():
    names = set()
    try:
        src = open(AI_FILE).read()
        names.update(re.findall(r'def (sig_\w+)', src))
    except: pass
    try:
        d = json.load(open(BANNED_FILE))
        names.update(d.get('names', []))
    except: pass
    return names

def ban_name(name):
    try: d = json.load(open(BANNED_FILE))
    except: d = {'names': []}
    if name not in d['names']:
        d['names'].append(name)
        json.dump(d, open(BANNED_FILE, 'w'), indent=2)

def get_recent_winners(n=3):
    try:
        d = json.load(open(BEST_FILE))
        return [f"{r['name']} (WR={r['wr']}% {r['pair']})" for r in d.get('winners', [])[-n:]]
    except: return []

def get_failure_hint():
    try:
        d = json.load(open(RESULTS_FILE))
        recent = d.get('history', [])[-5:]
    except: return ""
    if not recent: return ""
    hints = []
    no_trades = sum(1 for r in recent if r.get('verdict') == 'NO_TRADES')
    rejects = [r for r in recent if r.get('verdict') == 'REJECT']
    lookahead = sum(1 for r in recent if r.get('verdict') == 'LOOKAHEAD')
    if lookahead >= 1: hints.append("STOP using c[i+1]/c[i+2] — only c[i-1], c[i]")
    if no_trades >= 2: hints.append("Last strategies gave 0 trades — make conditions LESS rare")
    if len(rejects) >= 3:
        small_n = sum(1 for r in rejects if r.get('best', {}).get('n', 0) < 100)
        if small_n >= 2: hints.append("Too few trades (n<100) — loosen conditions")
    return " | ".join(hints) if hints else ""

def build_prompt():
    existing = list(get_existing_names())[:10]
    winners = get_recent_winners(3)
    hint = get_failure_hint()
    return f"""Senior Quant Developer — write ONLY a Python strategy function for 5-minute candles.

DATA (numpy arrays): o, h, l, c, v (open/high/low/close/volume), ind (dict: 'rsi','sma20','sma50','atr','adx')

RULES:
1. def sig_rsi_volume_pulse(o, h, l, c, v, ind):
2. return (up_mask, dn_mask) — two numpy bool arrays len(c)
3. up_mask[i]=True → bet UP on candle i, dn_mask[i]=True → bet DOWN
4. import numpy as np inside function
5. FORBIDDEN: c[i+1], c[i+2] (look-ahead). ONLY c[i], c[i-1], c[i-2] allowed.
6. FORBIDDEN: modify o,h,l,c,v in-place (e.g. c[0]=...)
7. Must produce MANY signals (not 1 per week), but selective (not 50% of candles)

ALREADY TESTED (do NOT repeat): {', '.join(existing) or 'none'}
BEST SO FAR: {'; '.join(winners) or 'none yet'}
FEEDBACK: {hint or 'none'}

Combine indicators creatively: RSI+volume, ATR regime, mean reversion with confirmation, etc.
Write ONLY code in ```python block. Nothing else."""

def call_llm(prompt, retries=2):
    for attempt in range(retries):
        try:
            r = subprocess.run(['tgpt','--provider','pollinations','--quiet', prompt],
                              capture_output=True, text=True, timeout=90)
            out = r.stdout.strip()
            out = re.sub(r'[\u2800-\u28FF]+\s*Loading\s*', '', out).strip()
            if out and len(out) > 50:  # осмысленный ответ
                return out
            if attempt < retries - 1:
                log(f"  empty/short response, retry {attempt+2}/{retries} in 30s")
                time.sleep(30)
        except Exception as e:
            log(f"  LLM error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(30)
    return ""

def extract_code(resp):
    m = re.search(r'```python\s*\n(.*?)```', resp, re.DOTALL)
    if not m:
        m = re.search(r'(def sig_\w+\(.*?)(?:\n\n\n|\Z)', resp, re.DOTALL)
    if not m: return None
    code = m.group(1).strip()
    return code.replace('\\n', '\n').replace('\\t', '    ')

def validate(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e: return None, f"syntax: {e}"
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if not funcs: return None, "no function"
    fn = funcs[0]
    if not fn.name.startswith('sig_'): return None, f"name not sig_: {fn.name}"
    if len(fn.args.args) != 6: return None, f"need 6 args, got {len(fn.args.args)}"
    # Санити: имя должно быть осмысленным, не placeholder
    BAD_NAMES = {'sig_YOURNAME', 'sig_YOUR_NAME', 'sig_name', 'sig_xxx', 'sig_test', 'sig_my_strategy', 'sig_strategy'}
    if fn.name in BAD_NAMES:
        return None, f"placeholder name: {fn.name}"
    if len(fn.name) < 8:  # sig_ + минимум 4 буквы
        return None, f"name too short: {fn.name}"
    return fn.name, None

def check_safety(code):
    if re.search(r'\[\s*i\s*\+\s*\d+\s*\]', code): return "uses [i+N] look-ahead"
    if re.search(r'shift\(\s*-\d+\s*\)', code): return "uses shift(-N)"
    if re.search(r'\b[coh lv]\s*\[[^\]]+\]\s*=', code.replace(' ','')): return "modifies input arrays"
    if re.search(r'\bc\s*\[[^\]]+\]\s*=\s*', code): return "modifies c array"
    return None

def add_strategy(name, code):
    if os.path.exists(AI_FILE): shutil.copy(AI_FILE, AI_FILE + '.bak_gen')
    with open(AI_FILE, 'a') as f:
        f.write(f"\n\n# === AI Generated: {name} ({datetime.now():%Y-%m-%d %H:%M}) ===\n{code}\n")

def remove_strategy(name):
    try:
        src = open(AI_FILE).read()
        pat = rf'# === AI Generated: {re.escape(name)}.*?(?=# === AI Generated|\Z)'
        open(AI_FILE, 'w').write(re.sub(pat, '', src, flags=re.DOTALL))
    except Exception as e: log(f"  remove failed: {e}")

def run_test(name):
    try:
        r = subprocess.run(['python3','rslab2.py','screen','--strat',name,'--model','open'],
                          capture_output=True, text=True, timeout=TEST_TIMEOUT, cwd=BASE)
        return r.stdout
    except Exception as e:
        log(f"  test error: {e}"); return ""

def parse_res(output):
    res = []; cur = None
    for line in output.split('\n'):
        for p in ['BTCUSDT','ETHUSDT','DOGEUSDT','SOLUSDT','XRPUSDT','BNBUSDT']:
            if line.strip().startswith(p): cur = p
        if cur and '%' in line and '|' in line:
            m = re.search(r'(\d+\.\d)%\s*\|\s*(\d+)\s*\|\s*(\d+\.\d)\s*\|\s*([\d\.]+)', line)
            if m: res.append({'pair':cur,'wr':float(m.group(1)),'n':int(m.group(2)),
                             'ci_lo':float(m.group(3)),'p':float(m.group(4))})
    return res

def evaluate(res):
    best = None
    for r in res:
        if r['n'] >= MIN_N_KEEP and r['wr'] >= MIN_WR_KEEP and r['p'] < MIN_P_KEEP:
            if best is None or r['wr'] > best['wr']: best = r
    if best: return 'KEEP', best
    for r in res:
        if r['n'] >= 200 and r['wr'] >= 52 and r['ci_lo'] >= 50:
            return 'CANDIDATE', r
    return 'REJECT', res[0] if res else None

def save_result(name, verdict, best, code_snippet=''):
    try: d = json.load(open(RESULTS_FILE))
    except: d = {'history': [], 'winners': []}
    d['history'].append({'name':name,'date':datetime.now().strftime('%Y-%m-%d'),
                        'time':datetime.now().strftime('%H:%M'),'verdict':verdict,
                        'best':best,'code':code_snippet[:500]})
    if verdict == 'KEEP' and best:
        d.setdefault('winners', []).append({'name':name,'pair':best['pair'],'wr':best['wr'],
                                           'n':best['n'],'p':best['p'],
                                           'date':datetime.now().strftime('%Y-%m-%d')})
        json.dump({'winners':d['winners']}, open(BEST_FILE,'w'), indent=2)
    json.dump(d, open(RESULTS_FILE,'w'), indent=2)

def cycle():
    log("=" * 60)
    n_today = strategies_today()
    log(f"Cycle: {n_today + 1}/{MAX_STRATEGIES_PER_DAY} today")
    if n_today >= MAX_STRATEGIES_PER_DAY:
        log("  Daily limit reached, skip"); return
    
    log("  Asking LLM...")
    resp = call_llm(build_prompt())
    if not resp:
        log("  empty LLM response (rate-limit или timeout)")
        save_result('attempt_failed', 'EMPTY', None, '')
        return
    
    code = extract_code(resp)
    if not code:
        log("  no code in response")
        save_result('attempt_failed', 'NO_CODE', None, resp[:300])
        return
    
    name, err = validate(code)
    if err: log(f"  INVALID: {err}"); return
    
    if name in get_existing_names():
        # Автопереименование вместо skip
        ts = int(time.time()) % 100000
        new_name = f'sig_gen_{ts}'
        log(f"  {name} exists → auto-rename to {new_name}")
        # Заменяем имя функции в коде
        code = code.replace(f'def {name}(', f'def {new_name}(')
        name = new_name
    
    safety = check_safety(code)
    if safety:
        log(f"  {name}: DANGER ({safety}) — reject")
        ban_name(name); save_result(name, 'LOOKAHEAD', {'reason': safety}, code); return
    
    log(f"  {name}: valid, no look-ahead, testing...")
    add_strategy(name, code)
    time.sleep(1)
    
    output = run_test(name)
    res = parse_res(output)
    if not res:
        log(f"  no trades → reject"); remove_strategy(name)
        ban_name(name); save_result(name, 'NO_TRADES', None, code); return
    
    verdict, best = evaluate(res)
    if verdict == 'REJECT':
        log(f"  REJECT (best: {best['pair']} WR={best['wr']}% n={best['n']})")
        remove_strategy(name); ban_name(name)
    elif verdict == 'CANDIDATE':
        log(f"  CANDIDATE: {best['pair']} WR={best['wr']}% n={best['n']} — kept for review")
    else:
        log(f"  🎯 WINNER: {best['pair']} WR={best['wr']}% n={best['n']} p={best['p']:.4f}")
    
    save_result(name, verdict, best, code)

def main():
    log("=" * 60)
    log(f"AI Generator starting | {GENERATE_EVERY_HOURS}h interval | {MAX_STRATEGIES_PER_DAY}/day")
    log(f"Threshold: WR>={MIN_WR_KEEP}% AND n>={MIN_N_KEEP} AND p<{MIN_P_KEEP}")
    log(f"Current strategies: {list(get_existing_names())}")
    log("=" * 60)
    
    # УМНЫЙ polling: просыпаемся каждые 60 сек, проверяем время
    # Это устойчиво к Doze mode на Android
    last_run = 0
    interval_sec = GENERATE_EVERY_HOURS * 3600
    log(f"Polling mode: check every 60s, run every {GENERATE_EVERY_HOURS}h")
    
    while True:
        try:
            now = time.time()
            elapsed = now - last_run
            if elapsed >= interval_sec:
                log(f"Time to run cycle (elapsed {elapsed/3600:.1f}h)")
                try:
                    cycle()
                except Exception as e:
                    log(f"cycle error: {e}")
                last_run = time.time()
                n_today = strategies_today()
                if n_today >= MAX_STRATEGIES_PER_DAY:
                    log(f"Daily limit reached, next cycle at midnight (or manual restart)")
            time.sleep(60)  # проверка раз в минуту
        except KeyboardInterrupt:
            log("stopped"); return
        except Exception as e:
            log(f"loop error: {e}")
            time.sleep(30)

if __name__ == '__main__':
    main()
