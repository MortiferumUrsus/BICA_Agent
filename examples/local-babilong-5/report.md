# Локальная проверка Llama 3.2 1B

Исторический запуск от 9 октября 2026 года. Завершение программы означает выполнение протокола; оно не означает правильный ответ.

## Ответы

| Метод | Этап | Вопрос | Ответ | Статус | Перечитаны |
| --- | --- | --- | --- | --- | --- |
| summary | 1 | Where is Sandra?  | ∅ | insufficient_data | c001 |
| reflexive | — | Остановка до вопроса | ∅ | ResponseError | — |
| summary | 1 | Where is Sandra?  | ∅ | insufficient_data | c001 |
| reflexive | — | Остановка до вопроса | ∅ | ResponseError | — |
| summary | 1 | Where is Daniel?  | ∅ | insufficient_data | c003 |
| reflexive | — | Остановка до вопроса | ∅ | ResponseError | — |
| summary | 1 | Where is Sandra?  | ∅ | insufficient_data | c004, c006 |
| reflexive | 1 | Where is Sandra?  | ∅ | insufficient_data | c002, c001 |
| summary | — | Остановка до вопроса | ∅ | ResponseError | — |
| reflexive | — | Остановка до вопроса | ∅ | ResponseError | — |

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

| Метод | Завершение | Вызовы | Сжатия | Поиски | USD |
| --- | --- | --- | --- | --- | --- |
| summary | completed | 12 | 9 | 1 | 0.0 |
| reflexive | error | 2 | 0 | 0 | 0.0 |
| summary | completed | 12 | 9 | 1 | 0.0 |
| reflexive | error | 2 | 0 | 0 | 0.0 |
| summary | completed | 12 | 9 | 1 | 0.0 |
| reflexive | error | 7 | 1 | 0 | 0.0 |
| summary | completed | 13 | 10 | 1 | 0.0 |
| reflexive | completed | 33 | 10 | 1 | 0.0 |
| summary | error | 2 | 0 | 0 | 0.0 |
| reflexive | error | 2 | 0 | 0 | 0.0 |

**Остановка reflexive:** ResponseError — Model answer does not match the required JSON schema.


**Остановка reflexive:** ResponseError — Model answer does not match the required JSON schema.


**Остановка reflexive:** ResponseError — Model answer does not match the required JSON schema.


**Остановка summary:** ResponseError — Model answer does not match the required JSON schema.


**Остановка reflexive:** ResponseError — Model answer does not match the required JSON schema.


## Оценка BABILong

| Метод | Запрошено | Завершено | Верно | Ошибки формата |
| --- | --- | --- | --- | --- |
| summary | 5 | 4 | 0 | 1 |
| reflexive | 5 | 1 | 0 | 4 |

## Исходные материалы

[Результаты JSON](results.json)
