# Первый эксперимент с OpenAI

Дата протокола: 1 ноября 2026. Оценка ответов — кодом по эталонам, без LLM-судьи.

Всего запусков: 512. Расход с отладкой: $9.3774; программный лимит $26 из выделенных $28.

Память 512, состояние 512, окно 8192, блок 2048 токенов cl100k_base. До 2048 выходных токенов API, включая размышления. Не более двух повторов при нарушении формата/размера. Все модели и методы получают одинаковые выбранные примеры.

PersonaMem: 16 разных персон, по одному вопросу на персону; вопрос раскрывается после чтения. BABILong: 20 ранее выделенных eval-примеров, вопрос известен заранее. Goal shift: 12 наших сценариев с исправлением цены и последующей сменой цели. Последняя группа не является стандартным бенчмарком.

full_context получает всё исходное сообщение и окно 65536; это контроль с большим бюджетом контекста. last_window получает только последние 4096 токенов. Сравнивать ограничения full_context с памятью 512 как равные нельзя.

| Набор | Модель / reasoning | Метод | Верно | Точность | 95% интервал Wilson | Ошибки запуска | USD | Вызовы |
|---|---|---|---:|---:|---|---:|---:|---:|
| babilong | 4.1-mini | reflexive | 14/20 | 70.0% | 48.1%–85.5% | 0 | 0.1835 | 280 |
| babilong | 4.1-mini | summary | 12/20 | 60.0% | 38.7%–78.1% | 0 | 0.0813 | 122 |
| babilong | 5.4-mini-low | reflexive | 12/20 | 60.0% | 38.7%–78.1% | 0 | 0.4618 | 291 |
| babilong | 5.4-mini-low | summary | 15/20 | 75.0% | 53.1%–88.8% | 0 | 0.1890 | 120 |
| babilong | 5.4-nano-low | reflexive | 10/20 | 50.0% | 29.9%–70.1% | 0 | 0.1165 | 291 |
| babilong | 5.4-nano-low | summary | 9/20 | 45.0% | 25.8%–65.8% | 0 | 0.0484 | 123 |
| babilong | 5.4-nano-none | reflexive | 3/20 | 15.0% | 5.2%–36.0% | 0 | 0.1062 | 292 |
| babilong | 5.4-nano-none | summary | 2/20 | 10.0% | 2.8%–30.1% | 0 | 0.0474 | 129 |
| goal_shift | 4.1-mini | reflexive | 2/12 | 16.7% | 4.7%–44.8% | 0 | 0.1321 | 228 |
| goal_shift | 4.1-mini | summary | 4/12 | 33.3% | 13.8%–60.9% | 0 | 0.0403 | 111 |
| goal_shift | 5.4-mini-low | reflexive | 8/12 | 66.7% | 39.1%–86.2% | 0 | 0.3041 | 244 |
| goal_shift | 5.4-mini-low | summary | 7/12 | 58.3% | 32.0%–80.7% | 0 | 0.1388 | 114 |
| goal_shift | 5.4-nano-low | reflexive | 3/12 | 25.0% | 8.9%–53.2% | 0 | 0.0845 | 228 |
| goal_shift | 5.4-nano-low | summary | 8/12 | 66.7% | 39.1%–86.2% | 0 | 0.0370 | 120 |
| goal_shift | 5.4-nano-none | reflexive | 2/12 | 16.7% | 4.7%–44.8% | 0 | 0.0777 | 232 |
| goal_shift | 5.4-nano-none | summary | 4/12 | 33.3% | 13.8%–60.9% | 0 | 0.0307 | 111 |
| personamem | 4.1-mini | full_context | 10/16 | 62.5% | 38.6%–81.5% | 0 | 0.1692 | 16 |
| personamem | 4.1-mini | last_window | 4/16 | 25.0% | 10.2%–49.5% | 0 | 0.0294 | 16 |
| personamem | 4.1-mini | reflexive | 7/16 | 43.8% | 23.1%–66.8% | 0 | 0.8103 | 671 |
| personamem | 4.1-mini | summary | 8/16 | 50.0% | 28.0%–72.0% | 0 | 0.3570 | 250 |
| personamem | 5.4-mini-low | full_context | 10/16 | 62.5% | 38.6%–81.5% | 0 | 0.3227 | 16 |
| personamem | 5.4-mini-low | last_window | 6/16 | 37.5% | 18.5%–61.4% | 0 | 0.0619 | 16 |
| personamem | 5.4-mini-low | reflexive | 5/16 | 31.2% | 14.2%–55.6% | 0 | 2.0572 | 685 |
| personamem | 5.4-mini-low | summary | 6/16 | 37.5% | 18.5%–61.4% | 0 | 0.8675 | 254 |
| personamem | 5.4-nano-low | full_context | 9/16 | 56.2% | 33.2%–76.9% | 0 | 0.0859 | 16 |
| personamem | 5.4-nano-low | last_window | 5/16 | 31.2% | 14.2%–55.6% | 0 | 0.0159 | 16 |
| personamem | 5.4-nano-low | reflexive | 5/16 | 31.2% | 14.2%–55.6% | 0 | 0.6050 | 679 |
| personamem | 5.4-nano-low | summary | 7/16 | 43.8% | 23.1%–66.8% | 0 | 0.2707 | 260 |
| personamem | 5.4-nano-none | full_context | 6/16 | 37.5% | 18.5%–61.4% | 0 | 0.0846 | 16 |
| personamem | 5.4-nano-none | last_window | 4/16 | 25.0% | 10.2%–49.5% | 0 | 0.0147 | 16 |
| personamem | 5.4-nano-none | reflexive | 8/16 | 50.0% | 28.0%–72.0% | 0 | 0.5533 | 674 |
| personamem | 5.4-nano-none | summary | 5/16 | 31.2% | 14.2%–55.6% | 0 | 0.2209 | 253 |

## Парное сравнение reflexive − summary

Положительная разница — в пользу reflexive. Интервалы получены парным bootstrap (10 000 повторов); p — точный McNemar без поправки на множественные сравнения. Анализ разведочный.

| Набор | Модель | Разница, п.п. | 95% bootstrap | Только reflexive верно | Только summary верно | p |
|---|---|---:|---|---:|---:|---:|
| babilong | 4.1-mini | +10.0 | -15.0…+35.0 | 5 | 3 | 0.7266 |
| babilong | 5.4-nano-low | +5.0 | -15.0…+25.0 | 3 | 2 | 1.0000 |
| babilong | 5.4-mini-low | -15.0 | -45.0…+15.0 | 3 | 6 | 0.5078 |
| babilong | 5.4-nano-none | +5.0 | +0.0…+15.0 | 1 | 0 | 1.0000 |
| goal_shift | 4.1-mini | -16.7 | -58.3…+25.0 | 2 | 4 | 0.6875 |
| goal_shift | 5.4-nano-low | -41.7 | -75.0…-8.3 | 1 | 6 | 0.1250 |
| goal_shift | 5.4-mini-low | +8.3 | -25.0…+41.7 | 3 | 2 | 1.0000 |
| goal_shift | 5.4-nano-none | -16.7 | -50.0…+16.7 | 1 | 3 | 0.6250 |
| personamem | 4.1-mini | -6.2 | -31.2…+18.8 | 2 | 3 | 1.0000 |
| personamem | 5.4-nano-low | -12.5 | -43.8…+18.8 | 2 | 4 | 0.6875 |
| personamem | 5.4-mini-low | -6.2 | -25.0…+12.5 | 1 | 2 | 1.0000 |
| personamem | 5.4-nano-none | +18.8 | +0.0…+37.5 | 3 | 0 | 0.2500 |

## Влияние размышлений: nano low − none

| Набор | Метод | Разница, п.п. | 95% bootstrap | p |
|---|---|---:|---|---:|
| babilong | reflexive | +35.0 | +10.0…+60.0 | 0.0391 |
| babilong | summary | +35.0 | +15.0…+55.0 | 0.0156 |
| goal_shift | reflexive | +8.3 | -16.7…+33.3 | 1.0000 |
| goal_shift | summary | +33.3 | +8.3…+58.3 | 0.1250 |
| personamem | full_context | +18.8 | +0.0…+37.5 | 0.2500 |
| personamem | last_window | +6.2 | -18.8…+31.2 | 1.0000 |
| personamem | reflexive | -18.8 | -37.5…+0.0 | 0.2500 |
| personamem | summary | +12.5 | -12.5…+37.5 | 0.6250 |

## Повторное чтение

| Набор | Модель | Метод | Верно до → после | Запросов повторного чтения |
|---|---|---|---:|---:|
| babilong | 4.1-mini | reflexive | 14 → 14 | 0 |
| babilong | 4.1-mini | summary | 12 → 12 | 1 |
| babilong | 5.4-mini-low | reflexive | 11 → 12 | 2 |
| babilong | 5.4-mini-low | summary | 15 → 15 | 0 |
| babilong | 5.4-nano-low | reflexive | 10 → 10 | 2 |
| babilong | 5.4-nano-low | summary | 9 → 9 | 1 |
| babilong | 5.4-nano-none | reflexive | 3 → 3 | 3 |
| babilong | 5.4-nano-none | summary | 2 → 2 | 3 |
| goal_shift | 4.1-mini | reflexive | 2 → 2 | 0 |
| goal_shift | 4.1-mini | summary | 3 → 4 | 1 |
| goal_shift | 5.4-mini-low | reflexive | 4 → 8 | 4 |
| goal_shift | 5.4-mini-low | summary | 7 → 7 | 2 |
| goal_shift | 5.4-nano-low | reflexive | 3 → 3 | 0 |
| goal_shift | 5.4-nano-low | summary | 5 → 8 | 4 |
| goal_shift | 5.4-nano-none | reflexive | 2 → 2 | 1 |
| goal_shift | 5.4-nano-none | summary | 4 → 4 | 1 |
| personamem | 4.1-mini | reflexive | 7 → 7 | 0 |
| personamem | 4.1-mini | summary | 8 → 8 | 0 |
| personamem | 5.4-mini-low | reflexive | 5 → 5 | 2 |
| personamem | 5.4-mini-low | summary | 5 → 6 | 3 |
| personamem | 5.4-nano-low | reflexive | 5 → 5 | 1 |
| personamem | 5.4-nano-low | summary | 6 → 7 | 3 |
| personamem | 5.4-nano-none | reflexive | 8 → 8 | 0 |
| personamem | 5.4-nano-none | summary | 5 → 5 | 0 |

## Два этапа смены цели

| Модель | Метод | Первая цель | Новая цель |
|---|---|---:|---:|
| 4.1-mini | reflexive | 11/12 | 2/12 |
| 4.1-mini | summary | 12/12 | 4/12 |
| 5.4-mini-low | reflexive | 12/12 | 8/12 |
| 5.4-mini-low | summary | 11/12 | 7/12 |
| 5.4-nano-low | reflexive | 12/12 | 3/12 |
| 5.4-nano-low | summary | 12/12 | 8/12 |
| 5.4-nano-none | reflexive | 12/12 | 2/12 |
| 5.4-nano-none | summary | 10/12 | 4/12 |

## Токены размышлений и время

Время — сумма длительности HTTP-запросов на пример; параллельное выполнение и сеть влияют на эти значения.

| Набор | Модель | Метод | Reasoning tokens | Cached input tokens | Среднее время запросов, с |
|---|---|---|---:|---:|---:|
| babilong | 4.1-mini | reflexive | 0 | 0 | 12.5 |
| babilong | 4.1-mini | summary | 0 | 0 | 5.9 |
| babilong | 5.4-mini-low | reflexive | 12888 | 0 | 17.0 |
| babilong | 5.4-mini-low | summary | 7077 | 0 | 6.6 |
| babilong | 5.4-nano-low | reflexive | 8951 | 0 | 16.7 |
| babilong | 5.4-nano-low | summary | 4171 | 0 | 6.3 |
| babilong | 5.4-nano-none | reflexive | 0 | 0 | 14.4 |
| babilong | 5.4-nano-none | summary | 0 | 0 | 5.8 |
| goal_shift | 4.1-mini | reflexive | 0 | 0 | 27.1 |
| goal_shift | 4.1-mini | summary | 0 | 0 | 10.0 |
| goal_shift | 5.4-mini-low | reflexive | 10430 | 0 | 24.5 |
| goal_shift | 5.4-mini-low | summary | 9923 | 0 | 12.4 |
| goal_shift | 5.4-nano-low | reflexive | 9158 | 0 | 30.5 |
| goal_shift | 5.4-nano-low | summary | 6949 | 0 | 14.2 |
| goal_shift | 5.4-nano-none | reflexive | 0 | 0 | 27.3 |
| goal_shift | 5.4-nano-none | summary | 0 | 0 | 11.4 |
| personamem | 4.1-mini | full_context | 0 | 0 | 1.7 |
| personamem | 4.1-mini | last_window | 0 | 0 | 1.0 |
| personamem | 4.1-mini | reflexive | 0 | 0 | 85.7 |
| personamem | 4.1-mini | summary | 0 | 12288 | 38.6 |
| personamem | 5.4-mini-low | full_context | 1170 | 0 | 1.7 |
| personamem | 5.4-mini-low | last_window | 1453 | 0 | 1.4 |
| personamem | 5.4-mini-low | reflexive | 47602 | 2432 | 81.6 |
| personamem | 5.4-mini-low | summary | 33498 | 0 | 34.7 |
| personamem | 5.4-nano-low | full_context | 973 | 0 | 1.8 |
| personamem | 5.4-nano-low | last_window | 900 | 0 | 1.2 |
| personamem | 5.4-nano-low | reflexive | 56269 | 1792 | 124.6 |
| personamem | 5.4-nano-low | summary | 27641 | 8960 | 55.3 |
| personamem | 5.4-nano-none | full_context | 0 | 0 | 1.4 |
| personamem | 5.4-nano-none | last_window | 0 | 0 | 0.9 |
| personamem | 5.4-nano-none | reflexive | 0 | 1792 | 107.5 |
| personamem | 5.4-nano-none | summary | 0 | 7168 | 41.1 |

## Ограничения

Выборка небольшая, на каждую комбинацию выполнен один прогон. Несколько вопросов и наборов проверяют разные навыки; их точности не объединяются в один рейтинг. Различия могут быть связаны с дополнительными вызовами и инструкциями reflexive. Перед/после retrieval — наблюдение в одном прогоне, а не отдельная рандомизированная проверка. Внешний оценщик не использовался; внутренний verify — часть метода сжатия.

Стоимость рассчитана по usage OpenAI и стандартным тарифам с учётом cache и reasoning. Это учёт запросов данного эксперимента, а не выгрузка баланса аккаунта. Неопределённые запросы удерживают полную предварительную оценку. Настройки, версии моделей, цены и хеши находятся в protocol.json; полные локальные журналы — в tasks/.
