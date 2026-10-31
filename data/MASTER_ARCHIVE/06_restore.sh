#!/data/data/com.termux/files/usr/bin/bash
cd ~/quantum_lab
cp data/MASTER_ARCHIVE/01_code/okx_bot_paper_v2.py core/
cp data/MASTER_ARCHIVE/01_code/okx_bot_paper_v3.py core/
cp data/MASTER_ARCHIVE/01_code/brain.py core/
cp data/MASTER_ARCHIVE/01_code/brain_loop.py core/
cp data/MASTER_ARCHIVE/01_code/oracle.py core/
cp data/MASTER_ARCHIVE/01_code/orderbook_oracle.py core/
cp data/MASTER_ARCHIVE/01_code/scalp_backtest.py core/
cp data/MASTER_ARCHIVE/01_code/okx_scalp_strategies.py core/
cp data/MASTER_ARCHIVE/01_code/multi_backtest.py .
cp data/MASTER_ARCHIVE/01_code/data_manager.py core/
cp data/MASTER_ARCHIVE/01_code/okx_panel.py web/
cp data/MASTER_ARCHIVE/01_code/okx_panel_v3.py web/
cp data/MASTER_ARCHIVE/02_configs/*.json data/
cp data/MASTER_ARCHIVE/02_configs/lab.json config/
chmod 444 data/okx_tpsl_by_regime.json
cp data/MASTER_ARCHIVE/05_strategies/*.py core/
mkdir -p data/graals data/scalp_graals
cp data/MASTER_ARCHIVE/03_reports/*.json data/graals/ 2>/dev/null
cp data/MASTER_ARCHIVE/03_reports/scalp_*.json data/scalp_graals/ 2>/dev/null
setsid python3 -u core/okx_bot_paper_v2.py > logs/okx_bot_paper.log 2>&1 & disown
setsid python3 -u core/okx_bot_paper_v3.py > logs/okx_bot_paper_v3.log 2>&1 & disown
setsid python3 -u core/brain_loop.py > logs/brain_loop.log 2>&1 & disown
setsid python3 -u core/oracle.py loop > logs/oracle.log 2>&1 & disown
setsid python3 -u core/orderbook_oracle.py > logs/orderbook_oracle.log 2>&1 & disown
setsid python3 -u web/okx_panel.py > logs/okx_panel.log 2>&1 & disown
setsid python3 -u web/okx_panel_v3.py > logs/okx_panel_v3.log 2>&1 & disown
echo "=== ГОТОВО ==="
pgrep -af "okx_bot_paper|brain_loop|oracle|orderbook_oracle|okx_panel" | grep -v grep
