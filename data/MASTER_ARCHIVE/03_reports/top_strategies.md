# 🏆 ЗОЛОТАЯ БИБЛИОТЕКА ГРААЛЕЙ

Дата: 2026-10-28T22:07:25.229814
Прогон A (11 пар × 87 стратегий): устойчивых 61
Прогон B (5 пар × 12 стратегий): устойчивых 18

## 📊 ТОП-20 по min_pnl (прогон A)

| # | Пара | Стратегия | 2d | 7d | 30d | min_pnl |
|---|---|---|---|---|---|---|
| 1 | LINK-USDT | `okx_vwap_rev_20` | — | — | — | +4.28 |
| 2 | ARB-USDT | `okx_vwap_rev_10` | — | — | — | +3.58 |
| 3 | AVAX-USDT | `okx_vwap_rev_10` | — | — | — | +3.30 |
| 4 | DOT-USDT | `okx_ema_6_18` | — | — | — | +3.25 |
| 5 | DOGE-USDT | `okx_ema_8_24` | — | — | — | +2.16 |
| 6 | SOL-USDT | `okx_ema_5_20` | — | — | — | +2.16 |
| 7 | XRP-USDT | `okx_ema_7_25` | — | — | — | +2.00 |
| 8 | ADA-USDT | `okx_vwap_rev_10` | — | — | — | +1.94 |
| 9 | ETH-USDT | `okx_ema_5_20` | — | — | — | +1.42 |
| 10 | BNB-USDT | `okx_vwap_rev_30` | — | — | — | +0.66 |

## 📋 ПО ПАРАМ (что предлагает A)

| Пара | Стратегия (A) | min_pnl | alt_strategy |
|---|---|---|---|
| ADA-USDT | `okx_vwap_rev_10` | +1.94 | `okx_vwap_rev_20` |
| ARB-USDT | `okx_vwap_rev_10` | +3.58 | `okx_grid_sma_10` |
| AVAX-USDT | `okx_vwap_rev_10` | +3.30 | `okx_vwap_rev_30` |
| BNB-USDT | `okx_vwap_rev_30` | +0.66 | `—` |
| DOGE-USDT | `okx_ema_8_24` | +2.16 | `okx_ema_5_20` |
| DOT-USDT | `okx_ema_6_18` | +3.25 | `okx_vwap_rev_10` |
| ETH-USDT | `okx_ema_5_20` | +1.42 | `okx_vwap_rev_30` |
| LINK-USDT | `okx_vwap_rev_20` | +4.28 | `okx_vwap_rev_10` |
| SOL-USDT | `okx_ema_5_20` | +2.16 | `okx_vwap_rev_30` |
| XRP-USDT | `okx_ema_7_25` | +2.00 | `okx_vwap_rev_30` |

## 🎯 КАК ВСТРОИТЬ (пошагово)

1. **Бэкап:** `cp data/okx_tpsl_by_regime.json data/okx_tpsl_by_regime.json.bak.$(date +%s)`
2. **Снять защиту:** `chmod 644 data/okx_tpsl_by_regime.json`
3. **Отредактировать вручную** (или через Python): добавить пары/стратегии из таблицы выше.
4. **Вернуть защиту:** `chmod 444 data/okx_tpsl_by_regime.json`
5. **Проверить:** бот читает конфиг (`python3 -c "import json; print(json.load(open('data/okx_tpsl_by_regime.json')))"`)
6. **Наблюдать 24–48ч:** PnL, WR, открытые сделки.
7. **Если плохо — откат:** `cp data/okx_tpsl_by_regime.json.bak.* data/okx_tpsl_by_regime.json`

## ⚠️ ВАЖНО

- **`vwap_rev_30` (XRP/ETH) — проверен live** (89% WR). НЕ менять без теста.
- **Новые пары/стратегии — НЕ проверены live.** Бэктест ≠ live.
- **Рекомендация:** сначала paper-тест, потом — обновление.
- **Бэкапы:** в `data/backup_*` и `data/graals/*.bak.*`