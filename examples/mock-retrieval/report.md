# Проверка программы с заданными ответами

Ответы заданы программно. Пример проверяет обновление памяти, поиск и сохранение результатов; качество языковой модели здесь не измеряется.

## Ответы

ID ведёт к материалам конкретного прогона. Этап — номер контрольного вопроса; прочерк означает остановку до ответа.

| ID примера | Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- | --- |
| [retrieval](summary/report.md) | Summary | 1 | What is the current delivery date for Orion? | 19 November 2026 | answer | — |
| [retrieval](summary/report.md) | Summary | 2 | What is the archive access code? | RIVER-17 | answer | c001 |
| [retrieval](reflexive/report.md) | Reflexive | 1 | What is the current delivery date for Orion? | 19 November 2026 | answer | — |
| [retrieval](reflexive/report.md) | Reflexive | 2 | What is the archive access code? | RIVER-17 | answer | c001 |

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
| [retrieval](summary/report.md) | Summary | completed | 10 | 5 | 1 | 0.0 |
| [retrieval](reflexive/report.md) | Reflexive | completed | 20 | 5 | 1 | 0.0 |

## Исходные материалы

[Результаты JSON](results.json)
