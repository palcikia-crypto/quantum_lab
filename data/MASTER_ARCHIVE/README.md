# MASTER ARCHIVE — Quantum Lab v2.0 (Бог-автомат)

## Восстановление
1. Код: `cp 01_code/*.py core/`, `cp 01_code/okx_panel*.py web/`
2. Конфиги: `cp 02_configs/*.json data/`, `cp 02_configs/lab.json config/`
3. `chmod 444 data/okx_tpsl_by_regime.json`
4. Стратегии: `cp 05_strategies/*.py core/`
5. Запуск: `bash 06_restore.sh`

## Автомат (P18–P24)
- **P18:** auto_evolve (6ч) — саморазвитие
- **P19:** auto_filter (2ч) — автонастройка
- **P20:** auto_compare (1ч) — сравнение
- **P21:** auto_data (1ч) — автодокачка
- **P22:** auto_apply_graals (6ч) — автоподключение
- **P23:** auto_stop_losers (1ч) — автостоп
- **P24:** auto_compare2 (2ч) — сравнение + переключение

## Важно
- **by_regime** — 444, manual_optimize, НЕ ТРОГАТЬ (автомат не трогает)
- **strategy_mutations** — 109 мутантов
- **v4** — OBI SHORT + funding
- **Funding rate** — работает
