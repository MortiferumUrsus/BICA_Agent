# Проверка программы с заданными ответами

Ответы заданы программно. Пример проверяет обновление памяти, поиск и сохранение результатов. Качество языковой модели здесь не измеряется.

## Ответы

ID ведёт к материалам конкретного прогона. Этап — номер контрольного вопроса. Прочерк означает остановку до ответа.

| ID примера | Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- | --- |
| [correction](summary/report.md) | Summary | 1 | What is the current delivery date for Orion? | 19 November 2026 | answer | — |
| [correction](reflexive/report.md) | Reflexive | 1 | What is the current delivery date for Orion? | 19 November 2026 | answer | — |

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
| [correction](summary/report.md) | Summary | completed | 6 | 4 | 0 | 0.0 |
| [correction](reflexive/report.md) | Reflexive | completed | 14 | 4 | 0 | 0.0 |

## Исходные материалы

[Результаты JSON](results.json)
