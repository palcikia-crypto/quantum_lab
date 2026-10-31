#!/usr/bin/env python3
import json
MAP = {
    'core': {'okx_bot_paper_v4.py':'Торговый бот v4','brain_loop.py':'Цикл мозга','brain.py':'Мозг','ml_online_simple.py':'Обучение ML','ml_predict_online.py':'Предсказание ML','oracle.py':'Режим рынка','orderbook_oracle.py':'OBI+funding','data_manager.py':'Свечи','evolution.py':'Эволюция','auto_apply_regime.py':'TP/SL по режиму','auto_obi_tuner.py':'TP/SL по OBI'},
    'data': {'market.db':'Свечи','orderbook.db':'OBI','oracle.db':'Режимы','okx_paper_v4.db':'Сделки v4','ml_online.pkl':'Модель ML','ml_predictions_online.json':'Предсказания','knowledge.db':'База знаний','agent_dashboard.html':'Дашборд'},
    'config': {'lab.json':'Общий конфиг'},
    'tools/agent': {'agent_v3.py':'Агент v3','agent_v5.py':'Агент v5','memory.db':'Память','rules.json':'Правила','knowledge_agent.py':'Сбор знаний'},
}
if __name__ == '__main__':
    print(json.dumps(MAP, indent=2, ensure_ascii=False))
