# Проверка программы с заданными ответами

Ответы заданы программно. Пример проверяет обновление памяти, поиск и сохранение результатов. Качество языковой модели здесь не измеряется.

## Ответы

ID ведёт к материалам конкретного прогона. Этап — номер контрольного вопроса. Прочерк означает остановку до ответа.

| ID примера | Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- | --- |
| [supplier](summary/report.md) | Summary | 1 | Choose the cheapest supplier delivering within 5 days. Return its name only. | Cedar | answer | — |
| [supplier](summary/report.md) | Summary | 2 | What payment terms and contract code should the order use for the chosen supplier? | Cedar: payment 30% advance, contract CD-104 | answer | — |
| [supplier](reflexive/report.md) | Reflexive | 1 | Choose the cheapest supplier delivering within 5 days. Return its name only. | Cedar | answer | — |
| [supplier](reflexive/report.md) | Reflexive | 2 | What payment terms and contract code should the order use for the chosen supplier? | Cedar: payment 30% advance, contract CD-104 | answer | — |

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

| ID примера | Метод | Завершение | Вызовы | Сжатия | Поиски | USD |
| --- | --- | --- | --- | --- | --- | --- |
| [supplier](summary/report.md) | Summary | completed | 9 | 5 | 0 | 0.0 |
| [supplier](reflexive/report.md) | Reflexive | completed | 19 | 5 | 0 | 0.0 |

## Исходные материалы

[Результаты JSON](results.json)
