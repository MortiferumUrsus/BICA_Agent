# Проверка программы с заданными ответами

Ответы заданы программно. Пример проверяет обновление памяти, поиск и сохранение результатов; качество языковой модели здесь не измеряется.

## Ответы

| Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- |
| summary | 1 | Choose the cheapest supplier delivering within 5 days. Return its name only. | Cedar | answer | — |
| summary | 2 | What payment terms and contract code should the order use for the chosen supplier? | Cedar: payment 30% advance, contract CD-104 | answer | — |

## Условия

| Параметр | Значение |
| --- | --- |
| Модель | deterministic-demo-fixture |
| Окно с резервом | 4096 |
| Память | 512 |
| Состояние | 256 |
| Фрагмент | 1024 |
| Резерв ответа | 768 |

## Работа программы

| Метод | Завершение | Вызовы | Сжатия | Поиски | USD |
| --- | --- | --- | --- | --- | --- |
| summary | completed | 9 | 5 | 0 | 0.0 |

## Пример изменения памяти

Это фактические записи модели. Наличие записи не подтверждает её истинность.

<details>
<summary>Показать записи до и после обновления</summary>

| Момент | Запись | Источники |
| --- | --- | --- |
| До | Supplier Cedar: price=90; delivery_days=4; payment=30% advance; contract=CD-104. | c001 |
| До | Supplier Maple: price=80; delivery_days=9; payment=full advance; contract=MP-209. | c002 |
| До | Supplier Birch: price=110; delivery_days=3; payment=on delivery; contract=BR-307. | c004 |
| После | Supplier Cedar: price=90; delivery_days=4; payment=30% advance; contract=CD-104. | c001 |
| После | Supplier Maple: price=80; delivery_days=9; payment=full advance; contract=MP-209. | c002 |
| После | Supplier Birch: price=110; delivery_days=3; payment=on delivery; contract=BR-307. | c004 |

</details>

## Исходные материалы

[Результаты JSON](results.json) · [Журнал текста](journal.jsonl) · [Версии памяти](memory_versions.jsonl) · [Трасса](trace.jsonl) · [Запросы и ответы](api_calls.jsonl)
