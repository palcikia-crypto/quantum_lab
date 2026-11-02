#!/bin/bash
cd ~/quantum_lab_sandbox
SCRIPT=${1:-core/okx_bot_paper_v4.py}

echo "📦 Собираю архив..."
tar -czf code.tar.gz --exclude='__pycache__' --exclude='*.log' --exclude='*.bak' --exclude='*.db' --exclude='*.db-*' --exclude='god_backups' --exclude='infra_backups' --exclude='*.tar.gz' *.py core/ tools/ data/ fixed/ fixed_v2/ new_modules/ agents/ web/ 2>/dev/null

echo "📤 Пушу ВСЁ на GitHub..."
git add -A
git commit -m "Update: $SCRIPT $(date +%H:%M:%S)" || true
git push -f origin master || true

echo "🛑 Отменяю старые запуски..."
gh run list --workflow=persistent_worker.yml --json databaseId --jq '.[].databaseId' | xargs -r -n 1 gh run cancel 2>/dev/null || true

echo "🚀 Запускаю воркер в облаке..."
gh workflow run persistent_worker.yml -f script_name="$SCRIPT"

echo "⏳ Ждем 40 секунд (сервер разворачивается)..."
sleep 40

while true; do
  clear
  echo "=== 🟢 ЖИВЫЕ ЛОГИ С GITHUB (Ctrl+C для выхода) ==="
  
  # Берем лог напрямую через API GitHub из ветки logs
  LOG_B64=$(gh api repos/palcikia-crypto/quantum_lab/contents/live.log?ref=logs --jq '.content' 2>/dev/null || echo "")
  
  if [ -n "$LOG_B64" ]; then
    echo "$LOG_B64" | base64 -d 2>/dev/null | tail -n 30
  else
    echo "⏳ Ожидание логов (сервер запускает бота, файл еще не создан)..."
  fi
  
  sleep 5
done
