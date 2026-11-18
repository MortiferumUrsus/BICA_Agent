# Локальная проверка Llama 3.2 1B

Исторический запуск от 9 октября 2026 года. Завершение программы означает выполнение протокола. Оно не означает правильный ответ.

## Ответы

ID ведёт к материалам конкретного прогона. Этап — номер контрольного вопроса. Прочерк означает остановку до ответа.

| ID примера | Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- | --- |
| [qa1-8k-00005](qa1-8k-00005/summary/report.md) | Summary | 1 | Where is Sandra?  | ∅ | insufficient_data | c001 |
| [qa1-8k-00005](qa1-8k-00005/reflexive/report.md) | Reflexive | — | Where is Sandra?  | ∅ | ResponseError | — |
| [qa1-8k-00006](qa1-8k-00006/summary/report.md) | Summary | 1 | Where is Sandra?  | ∅ | insufficient_data | c001 |
| [qa1-8k-00006](qa1-8k-00006/reflexive/report.md) | Reflexive | — | Where is Sandra?  | ∅ | ResponseError | — |
| [qa1-8k-00007](qa1-8k-00007/summary/report.md) | Summary | 1 | Where is Daniel?  | ∅ | insufficient_data | c003 |
| [qa1-8k-00007](qa1-8k-00007/reflexive/report.md) | Reflexive | — | Where is Daniel?  | ∅ | ResponseError | — |
| [qa1-8k-00008](qa1-8k-00008/summary/report.md) | Summary | 1 | Where is Sandra?  | ∅ | insufficient_data | c004, c006 |
| [qa1-8k-00008](qa1-8k-00008/reflexive/report.md) | Reflexive | 1 | Where is Sandra?  | ∅ | insufficient_data | c002, c001 |
| [qa1-8k-00009](qa1-8k-00009/summary/report.md) | Summary | — | Where is Daniel?  | ∅ | ResponseError | — |
| [qa1-8k-00009](qa1-8k-00009/reflexive/report.md) | Reflexive | — | Where is Daniel?  | ∅ | ResponseError | — |

## Условия

| Параметр | Значение |
| --- | --- |
| Модель | llama3.2:1b |
| Окно с резервом | 4096 |
| Память | 512 |
| Состояние | 256 |
| Фрагмент | 1024 |
| Резерв ответа | 768 |

## Работа программы

| ID примера | Метод | Завершение | Вызовы | Сжатия | Поиски | USD |
| --- | --- | --- | --- | --- | --- | --- |
| [qa1-8k-00005](qa1-8k-00005/summary/report.md) | Summary | completed | 12 | 9 | 1 | 0.0 |
| [qa1-8k-00005](qa1-8k-00005/reflexive/report.md) | Reflexive | error | 2 | 0 | 0 | 0.0 |
| [qa1-8k-00006](qa1-8k-00006/summary/report.md) | Summary | completed | 12 | 9 | 1 | 0.0 |
| [qa1-8k-00006](qa1-8k-00006/reflexive/report.md) | Reflexive | error | 2 | 0 | 0 | 0.0 |
| [qa1-8k-00007](qa1-8k-00007/summary/report.md) | Summary | completed | 12 | 9 | 1 | 0.0 |
| [qa1-8k-00007](qa1-8k-00007/reflexive/report.md) | Reflexive | error | 7 | 1 | 0 | 0.0 |
| [qa1-8k-00008](qa1-8k-00008/summary/report.md) | Summary | completed | 13 | 10 | 1 | 0.0 |
| [qa1-8k-00008](qa1-8k-00008/reflexive/report.md) | Reflexive | completed | 33 | 10 | 1 | 0.0 |
| [qa1-8k-00009](qa1-8k-00009/summary/report.md) | Summary | error | 2 | 0 | 0 | 0.0 |
| [qa1-8k-00009](qa1-8k-00009/reflexive/report.md) | Reflexive | error | 2 | 0 | 0 | 0.0 |

## Причины остановки

Одинаковые ошибки объединены. Остановка по формату отличается от ответа insufficient_data: в первом случае протокол прерван, во втором модель явно сообщает о нехватке данных.

| Ошибка | Что произошло | Прогонов | Какие прогоны |
| --- | --- | --- | --- |
| ResponseError | Модель нарушила требуемую JSON-схему. | 5 | [qa1-8k-00005](qa1-8k-00005/reflexive/report.md) / Reflexive; [qa1-8k-00006](qa1-8k-00006/reflexive/report.md) / Reflexive; [qa1-8k-00007](qa1-8k-00007/reflexive/report.md) / Reflexive; [qa1-8k-00009](qa1-8k-00009/summary/report.md) / Summary; [qa1-8k-00009](qa1-8k-00009/reflexive/report.md) / Reflexive |

## Оценка BABILong

| Метод | Запрошено | Завершено | Верно | Ошибки формата |
| --- | --- | --- | --- | --- |
| summary | 5 | 4 | 0 | 1 |
| reflexive | 5 | 1 | 0 | 4 |

## Исходные материалы

[Результаты JSON](results.json)
