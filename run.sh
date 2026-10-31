#!/data/data/com.termux/files/usr/bin/bash
# run.sh — запуск Quantum Lab (оркестратор + панель)
cd ~/quantum_lab
termux-wake-lock 2>/dev/null
if ! pgrep -f "orchestrator.py" > /dev/null; then
    setsid python3 core/orchestrator.py > logs/orchestrator.log 2>&1 < /dev/null &
fi
if [ -f web/app.py ] && ! pgrep -f "quantum_lab/web/app.py" > /dev/null; then
    setsid python3 web/app.py > logs/web.log 2>&1 < /dev/null &
fi
echo "Quantum Lab запущен"
