# Запуск и проверка программы

Все команды выполняются из корня проекта. Сначала проверьте программу на mock, затем выбранную модель на коротком сценарии и только после этого запускайте длинную историю.

## Установка

Нужен Python 3.11+. Для macOS и Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,bench]"
python -m context_memory doctor
python -m pytest -q
python -m context_memory smoke --out runs/smoke-mock
```

В PowerShell используйте `py -3.11 -m venv .venv` и `.venv\Scripts\Activate.ps1`. Doctor показывает зависимости и конфигурацию без генерации. Smoke проверяет исправление срока доставки и сверяет ответ кодом. Mock использует заданные ответы; его успех не измеряет качество LLM.

## Локальная модель

В одном терминале запустите `ollama serve`. Затем:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
python -m context_memory doctor --provider ollama --model qwen3:4b-instruct-2507-q4_K_M
python -m context_memory smoke --provider ollama --model qwen3:4b-instruct-2507-q4_K_M --format-retries 1 --timeout-s 180 --out runs/smoke-qwen
```

Это пример конфигурации, не подтверждённый результат Qwen в опубликованных сериях. Историческая Llama 3.2 1B показала 0/5 на BABILong; её результаты разобраны в [локальной проверке](validation.md). При нехватке памяти модель выбирается вручную. Программа не подменяет её автоматически.

## Локальный OpenAI-совместимый сервер

Провайдер `openai` означает локальный API, например vLLM. Провайдер `openai-api` означает платный OpenAI. Для сервера через SSH используйте проброс:

```bash
ssh -N -L 8000:127.0.0.1:8000 user@gpu-host
python -m context_memory smoke --provider openai --model Qwen/Qwen3-4B-Instruct-2507 --timeout-s 180 --format-retries 1 --out runs/smoke-server
```

По умолчанию локальный URL — http://127.0.0.1:8000/v1. Сервер должен поддерживать JSON Schema; это проверяется реальной генерацией smoke.

## Данные и предварительный план

```bash
python -m context_memory fetch-benchmark --dataset personamem
python -m context_memory benchmark --dataset personamem --limit 5 --mode both --provider ollama --model qwen3:4b-instruct-2507-q4_K_M --max-api-calls 1500 --dry-run --out runs/personamem-plan
```

Dry run создаёт план без клиента модели. В него входят ID примеров, хеши, лимиты и нижняя оценка числа вызовов. Для первых пяти eval-вопросов сохранённого экспорта оценка составляет 580 вызовов. Поиск, повторы и дополнительное дробление могут увеличить расход. Отладку параметров проводите на `--split debug`.

## Генерация и отдельная оценка

```bash
python -m context_memory benchmark --dataset personamem --limit 5 --mode both --provider ollama --model qwen3:4b-instruct-2507-q4_K_M --max-api-calls 1500 --format-retries 1 --timeout-s 180 --no-score --out runs/personamem-qwen
python -m context_memory evaluate runs/personamem-qwen --data-dir data/personamem
```

Первый шаг сохраняет ответы, не открывая эталоны. Второй проверяет идентичность данных и полноту предсказаний, затем пишет оценку в `evaluation/`. Ошибки выполнения, невалидный ответ и неверный содержательный ответ учитываются отдельно. Все назначенные примеры остаются в знаменателе точности.

Для BABILong замените датасет на `babilong` и каталог на `data/babilong`. По умолчанию там вопрос известен до чтения. Более пяти eval-примеров требуют явного `--full-eval`.

## Отчёты и повторяемость

```bash
python3 tools/build_research_report.py
```

Эта команда использует только сохранённые файлы. Она не вызывает модели. В `docs/research/` появятся HTML, графики, CSV и JSON. Для обновления производных Markdown-отчётов есть `--rewrite-run-reports`.

В macOS PDF собирается системным Swift-рендерером. После сборки HTML выполните:

```bash
swift -module-cache-path /tmp/bica-swift-cache tools/render_research_pdf.swift docs/research/pdf_data.json docs/research/report.pdf
```

Получаются полный PDF с приложением и краткий `report.summary.pdf` из девяти исследовательских страниц. Swift-рендерер рассчитан на macOS; на других платформах доступен HTML с печатными стилями.

Точный повтор платных серий требует исходных датасетов, полных журналов и соответствующей версии кода. Большинство журналов не включены в Git. Старый протокол первой серии фиксирует прежний API-клиент; его нельзя незаметно заменить текущим. В сохранённом протоколе продолжения есть Windows-пути — на macOS их нужно нормализовать в рабочей копии протокола, сохранив оригинал.

Исторические проверки: 136 тестов в 0.1, 167 в 0.2, 179 в 0.3 и 182 в 0.4. Эти числа относятся к разным версиям и не являются результатом повторного запуска при редактуре.
