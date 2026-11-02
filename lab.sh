#!/bin/bash
cd ~/quantum_lab_sandbox
SCRIPT=${1:-core/okx_bot_paper_v4.py}
TOPIC="palcikia-qlab-2026"

echo "📦 Собираю архив..."
tar -czf code.tar.gz --exclude='__pycache__' --exclude='*.log' --exclude='*.bak' --exclude='*.db' --exclude='*.db-*' --exclude='god_backups' --exclude='infra_backups' --exclude='*.tar.gz' *.py core/ tools/ data/ fixed/ fixed_v2/ new_modules/ agents/ web/ 2>/dev/null

echo "📤 Пушу ВСЁ на GitHub (и код, и конфиги)..."
git add -A
git commit -m "Update: $SCRIPT $(date +%H:%M:%S)" || true
git push -f origin master || true

echo "🛑 Отменяю старые запуски..."
gh run list --workflow=persistent_worker.yml --json databaseId --jq '.[].databaseId' | xargs -r -n 1 gh run cancel 2>/dev/null || true

echo "🚀 Запускаю воркер в облаке..."
gh workflow run persistent_worker.yml -f script_name="$SCRIPT"

echo "⏳ Ждем 40 секунд, пока сервер развернется..."
sleep 40

echo ""
echo "=== 🟢 ЖИВЫЕ ЛОГИ С GITHUB (Ctrl+C для выхода) ==="
echo ""

# Стрим с ntfy
curl -sN "https://ntfy.sh/$TOPIC/json" | while IFS= read -r line; do
  msg=$(echo "$line" | jq -r '.message // empty' 2>/dev/null)
  [ -n "$msg" ] && echo "$msg"
done
