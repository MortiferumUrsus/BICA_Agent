# Разбор сохранённого платного прогона

Показательный случай первой серии. Он объясняет поведение метода, но не заменяет оценку всей выборки.

## Ответы

ID ведёт к материалам конкретного прогона. Этап — номер контрольного вопроса. Прочерк означает остановку до ответа.

| ID примера | Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- | --- |
| [goal-shift-001](results.json) | Summary | 1 | Which supplier is cheapest among those delivering within 5 days? Return its name only. | Vendor-01-D | answer | — |
| [goal-shift-001](results.json) | Summary | 2 | What is the contract code of the supplier with the shortest delivery time, regardless of price? Return only the exact code. | AG-68601-3 | answer | — |

## Условия

| Параметр | Значение |
| --- | --- |
| Модель | gpt-5.4-mini-2026-03-17 |
| Окно с резервом | 8192 |
| Память | 512 |
| Состояние | 512 |
| Фрагмент | 2048 |
| Резерв ответа | 2048 |

## Работа программы

| ID примера | Метод | Завершение | Вызовы | Сжатия | Поиски | USD |
| --- | --- | --- | --- | --- | --- | --- |
| [goal-shift-001](results.json) | Summary | completed | 9 | 5 | 0 | 0.00840825 |

## Пример изменения памяти

Это фактические записи модели. Наличие записи не подтверждает её истинность.

<details>
<summary>Показать записи до и после обновления</summary>

| Момент | Запись | Источники |
| --- | --- | --- |
| До | Cheapest supplier delivering within 5 days: Vendor-01-D, price=50, delivery_days=5, contract_code=AG-68601-3, payment=on delivery. Previous price was 133; corrected by c004. | c001, c004 |
| После | Fastest supplier: Vendor-01-D, delivery_days=5, contract_code=AG-68601-3, payment=on delivery. | c001, c004 |
| После | Previous identification was cheapest supplier delivering within 5 days: Vendor-01-D, price=50, delivery_days=5, contract_code=AG-68601-3, payment=on delivery; previous price was 133, corrected by c004. | c001, c004 |

</details>

## Исходные материалы

[Результаты JSON](results.json) · [Журнал текста](journal.jsonl) · [Версии памяти](memory_versions.jsonl) · [Трасса](trace.jsonl) · [Запросы и ответы](api_calls.jsonl)
