import llmf

def ask(prompt: str, system_prompt: str = "Ты — эксперт по Python.") -> str:
    try:
        # llmf сам выбирает живого провайдера и переключается при ошибке
        r = llmf.chat(prompt, system=system_prompt, model="best", max_tokens=1000)
        return r.text
    except Exception as e:
        return f"ОШИБКА_LLMF: {e}"
