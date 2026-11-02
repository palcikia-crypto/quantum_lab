#!/bin/bash
cd ~/quantum_lab_sandbox
LAST_HASH=""

echo "👁️ Наблюдатель запущен. Любые изменения в .py файлах будут автоматически улетать на GitHub."

while true; do
    # Считаем хэш всех файлов кода (игнорируем мусор)
    HASH=$(find . -type f \( -name "*.py" -o -name "*.json" \) -not -path "*/__pycache__/*" -not -path "*/.git/*" -not -name "*.bak" -not -name "live.log" -exec md5sum {} \; 2>/dev/null | sort | md5sum | awk '{print $1}')
    
    if [ "$HASH" != "$LAST_HASH" ]; then
        LAST_HASH="$HASH"
        echo "[$(date +%H:%M:%S)] 🔄 Обнаружены изменения! Синхронизирую..."
        
        # Пересобираем архив
        tar -czf code.tar.gz --exclude='__pycache__' --exclude='*.log' --exclude='*.bak' --exclude='*.db' --exclude='*.db-*' --exclude='god_backups' --exclude='infra_backups' --exclude='*.tar.gz' *.py core/ tools/ data/ fixed/ fixed_v2/ new_modules/ agents/ web/ 2>/dev/null
        
        # Пушим
        git add -A
        git commit -m "Auto-sync: $(date +%H:%M:%S)" 2>/dev/null
        git pull --rebase origin master 2>/dev/null
        git push origin master 2>/dev/null
        echo "[$(date +%H:%M:%S)] ✅ Отправлено в облако."
    fi
    sleep 5
done
