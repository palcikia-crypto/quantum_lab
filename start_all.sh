#!/data/data/com.termux/files/usr/bin/bash
# start_all.sh — запускает ВСЁ после перезагрузки телефона
cd ~/quantum_lab || exit 1

LOG="logs/start_all.log"
echo "[$(date '+%F %T')] === START ALL ===" >> "$LOG"

# 1. DATA: oracle + orderbook_oracle
if ! pgrep -f "core/oracle.py" >/dev/null; then
  setsid python3 -u core/oracle.py loop > logs/oracle.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ oracle.py" >> "$LOG"
fi
if ! pgrep -f "orderbook_oracle" >/dev/null; then
  setsid python3 -u core/orderbook_oracle.py > logs/orderbook_oracle.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ orderbook_oracle" >> "$LOG"
fi
if ! pgrep -f "data_manager" >/dev/null; then
  setsid python3 -u core/data_manager.py > logs/data_manager.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ data_manager" >> "$LOG"
fi

# 2. BRAIN
if ! pgrep -f "brain_loop" >/dev/null; then
  setsid python3 -u core/brain_loop.py > logs/brain_loop.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ brain_loop" >> "$LOG"
fi

# 3. OKX v4
if ! pgrep -f "okx_bot_paper_v4" >/dev/null; then
  setsid python3 -u core/okx_bot_paper_v4.py > logs/okx_bot_paper_v4.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ okx_bot_paper_v4" >> "$LOG"
fi

# 4. STRATEGY BOT (грааль)
if ! pgrep -f "strategy_bot" >/dev/null; then
  setsid python3 -u core/strategy_bot.py > logs/strategy_bot.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ strategy_bot" >> "$LOG"
fi

# 5. EVOLUTION
if ! pgrep -f "evolve_agent" >/dev/null; then
  setsid python3 -u agents/evolve_agent.py > logs/evolve_agent.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ evolve_agent" >> "$LOG"
fi

# 6. POLYMARKET (в ~/rsbot)
cd ~/rsbot 2>/dev/null && {
  for bot in pm_bot pm_bot_v4 pm_bot_v5 pm_bot_v6; do
    if ! pgrep -f "$bot.py" >/dev/null; then
      setsid python3 -u $bot.py > logs/$bot.log 2>&1 < /dev/null &
      echo "[$(date '+%T')] ✅ $bot" >> ~/quantum_lab/logs/start_all.log
    fi
  done
}
cd ~/quantum_lab || exit 1

# 7. ДАШБОРДЫ
if ! pgrep -f "web/dashboard.py" >/dev/null; then
  setsid python3 -u web/dashboard.py > logs/dashboard.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ dashboard (5000)" >> "$LOG"
fi
if ! pgrep -f "web/strategy_panel.py" >/dev/null; then
  setsid python3 -u web/strategy_panel.py > logs/strategy_panel.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ strategy_panel (5001)" >> "$LOG"
fi

# 8. CRON
if ! pgrep -f crond >/dev/null; then
  crond 2>/dev/null
  echo "[$(date '+%T')] ✅ crond" >> "$LOG"
fi

# 9. АГЕНТ — пусть проверит через 30 сек
sleep 30
if ! pgrep -f "tools/agent/agent_v6.py" >/dev/null; then
  setsid python3 -u tools/agent/agent_v6.py > logs/agent.log 2>&1 < /dev/null &
  echo "[$(date '+%T')] ✅ agent_v6" >> "$LOG"
fi

echo "[$(date '+%F %T')] === START ALL DONE ===" >> "$LOG"
