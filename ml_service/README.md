# Сервисный слой (`services/`)

Директория `services/` содержит автономные бэкенд-микросервисы проекта со своими зависимостями, Docker-сборкой и `.gitignore`.

## Структура

- [`sheet_parser/`](./sheet_parser/) — асинхронный FastAPI-микросервис распознавания, нормализации и риск-аудита японских автомобильных аукционных листов (`USS`, `TAA`, `JU`, `CAA`, `ARAI` и др.).
- [`docker-compose.yml`](./docker-compose.yml) — оркестрация локального и продакшен-запуска сервисов в контейнерах.
- [`.gitignore`](./.gitignore) — исключает локальные секреты (`.env`), виртуальные окружения (`.venv/`), дисковый кэш (`.cache/`) и сборочные артефакты Python.

---

## Быстрый старт через Docker Compose

Из каталога `services`:

```powershell
# 1. Создать .env с API-ключом Gemini (если ещё не создан)
Copy-Item .\sheet_parser\.env.example .\sheet_parser\.env

# 2. Собрать образ и запустить сервис
docker compose up --build -d
```

В `cmd`:

```cmd
copy sheet_parser\.env.example sheet_parser\.env
docker compose up --build -d
```

После запуска:
- Healthcheck: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`

Остановка:

```powershell
docker compose down
```

---

## Сборка и запуск `sheet_parser` отдельным Docker-образом

```powershell
docker build -t sheet-parser-service ./sheet_parser
docker run --rm -p 8000:8000 --env-file ./sheet_parser/.env -v "${PWD}/sheet_parser/.cache:/app/.cache" sheet-parser-service
```

---

## Локальный запуск (без Docker) и тесты

Подробные команды установки с нуля, настройки переменных окружения и запуска автотестов приведены в [`services/sheet_parser/README.md`](./sheet_parser/README.md).

Быстрый прогон тестов из `services/sheet_parser`:

```powershell
.\.venv\Scripts\pytest.exe tests -v
```
