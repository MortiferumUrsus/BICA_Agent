# Локальная проверка Llama 3.2 1B

Исторический запуск от 9 октября 2026 года. Завершение программы означает выполнение протокола. Оно не означает правильный ответ.

## Ответы

ID ведёт к материалам конкретного прогона. Этап — номер контрольного вопроса. Прочерк означает остановку до ответа.

| ID примера | Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- | --- |
| [correction](summary/report.md) | Summary | 1 | What is the current delivery date for Orion? | ∅ | insufficient_data | c001, c002 |
| [correction](reflexive/report.md) | Reflexive | 1 | What is the current delivery date for Orion? | ∅ | insufficient_data | c002, c003 |

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
| [correction](summary/report.md) | Summary | completed | 9 | 6 | 1 | 0.0 |
| [correction](reflexive/report.md) | Reflexive | completed | 21 | 6 | 1 | 0.0 |

## Исходные материалы

[Результаты JSON](results.json)
