# Отчёты и подтверждающие материалы

| Папка | Назначение |
| --- | --- |
| [final](final/README.md) | Материалы для чтения и передачи: HTML, краткий и полный PDF |
| [analysis](analysis/babilong_sensitivity.md) | Дополнительный разбор метрики BABILong |
| [data](data/README.md) | Машиночитаемые ответы, источники и входные данные сборки |
| [figures](figures/) | Графики в SVG |

Основной вывод и все 686 итоговых ответов представлены в [HTML-отчёте](final/report.html). Для быстрого чтения предназначен [краткий PDF](final/report.summary.pdf); [полный PDF](final/report.pdf) включает подробную статистику и приложения.

Пересборка HTML, Markdown, графиков и данных из корня проекта:

```bash
python3 tools/build_research_report.py
```

Сборка PDF в macOS:

```bash
swift -module-cache-path /tmp/bica-swift-cache tools/render_research_pdf.swift docs/reports/data/pdf_data.json docs/reports/final/report.pdf
```

`--out` у Python-скрипта задаёт корневую папку отчётов. В ней создаются `final/`, `analysis/`, `data/` и `figures/`. Для обновления отчётов отдельных прогонов в `examples/` добавьте `--rewrite-run-reports`. Подробности — в [инструкции по запуску](../guides/testing.md).
