# Сохранённые прогоны

Запуски от 9 октября 2026. Запросы, ответы модели и трассы сохранены без изменений; Markdown-отчёты пересобраны текущей версией программы.

| Папка | Провайдер | Сценарий |
| --- | --- | --- |
| [mock-correction](mock-correction/report.md) | Mock | Изменение срока доставки |
| [mock-supplier](mock-supplier/report.md) | Mock | Выбор поставщика и подготовка заказа |
| [mock-retrieval](mock-retrieval/report.md) | Mock | Восстановление кода из журнала |
| [local-correction](local-correction/summary/report.md) | Ollama, Llama 3.2 1B | Изменение срока доставки |
| [local-babilong-5](local-babilong-5/report.md) | Ollama, Llama 3.2 1B | Пять примеров BABILong qa1/8k |

[babilong-manifest.json](babilong-manifest.json) содержит revision, хеш файла и номера выбранных строк. Сам датасет загружается командой `python -m context_memory fetch-benchmark`.
