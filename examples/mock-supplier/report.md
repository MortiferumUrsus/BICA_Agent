# Проверка программы с заданными ответами

Ответы заданы программно. Пример проверяет обновление памяти, поиск и сохранение результатов; качество языковой модели здесь не измеряется.

## Ответы

| Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- |
| summary | 1 | Choose the cheapest supplier delivering within 5 days. Return its name only. | Cedar | answer | — |
| summary | 2 | What payment terms and contract code should the order use for the chosen supplier? | Cedar: payment 30% advance, contract CD-104 | answer | — |
| reflexive | 1 | Choose the cheapest supplier delivering within 5 days. Return its name only. | Cedar | answer | — |
| reflexive | 2 | What payment terms and contract code should the order use for the chosen supplier? | Cedar: payment 30% advance, contract CD-104 | answer | — |

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
| reflexive | completed | 19 | 5 | 0 | 0.0 |

## Исходные материалы

[Результаты JSON](results.json)
