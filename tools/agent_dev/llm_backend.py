import requests, time
from pathlib import Path

POLL_URL = "https://text.pollinations.ai/openai"
LAST_REQUEST_TIME = 0
MIN_INTERVAL = 10  # Увеличили паузу для надежности

def ask(prompt: str, system_prompt: str = "Ты — эксперт по Python.") -> str:
    global LAST_REQUEST_TIME
    elapsed = time.time() - LAST_REQUEST_TIME
    if elapsed < MIN_INTERVAL:
        print(f"   ⏳ Пауза {MIN_INTERVAL - elapsed:.1f} сек...")
        time.sleep(MIN_INTERVAL - elapsed)

    headers = {"Content-Type": "application/json"}
    data = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2000
    }
    
    try:
        r = requests.post(POLL_URL, headers=headers, json=data, timeout=90)
        LAST_REQUEST_TIME = time.time()
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            if not content:
                return "ОШИБКА: ИИ вернул пустой ответ."
            return content
        return f"ОШИБКА API {r.status_code}: {r.text}"
    except Exception as e:
        return f"ОШИБКА СЕТИ: {e}"
