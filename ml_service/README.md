# Sheet Parser Microservice (`sheet-parser-service`)

Асинхронный FastAPI-микросервис для распознавания, перевода и нормализации японских автомобильных аукционных листов в чистой слоистой DDD-архитектуре (`domains` ← `factories` ← `services` ← `infrastructure` & `api`).

## Архитектура

- `app/domains/` — чистые `@dataclass`-сущности и `Enum`-перечисления без зависимостей от FastAPI, Pydantic и Pillow.
- `app/factories/` — детерминированные нормализаторы японских дат (`R`/`H`/`S`, кандзи и «голых» годов), синтез `Frame ID`, разбор кодов дефектов (`A2/W1`, `AU3`, `XX`, `X`), расчёт индекса строгости аукционов, риск-флаги, рендер Markdown и сборка `ParserResultEntity`.
- `app/infrastructure/`:
  - `AsyncImageLoader` (`httpx` + `sha256` + проверка сигнатур);
  - `PillowImageCropper` (обрезка белых полей, 2×2 пересекающихся квадранта 60%×60%, в продакшн-конфиге компактное `JPEG`-сжатие `1000–1400 px`, `quality=88`; по умолчанию `PNG` для юнит-тестов);
  - `ResultCache` (двухуровневый memory + JSON-кэш на диске по SHA-256);
  - `GeminiKeyPool` (Round-Robin пул ключей, `asyncio.Semaphore`, cooldown при `429`);
  - `AsyncGeminiVisionClient` (`gemini-decision-1` Gatekeeper с `fail_open`, основная модель `gemini-3.6-flash` + автоматический failover по резервной цепочке `gemini-3-flash-preview`, `gemini-3.7-flash`, `gemini-3.8-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, кэшированные клиенты `genai.Client`, жёсткий таймаут `25s` и `HttpRetryOptions(attempts=1)`).
- `app/services/` — `SheetParserService` и `BatchParserService` (пачки `1..10` снимков с фоновыми задачами и Live Polling).
- `app/api/` — тонкие FastAPI-контроллеры, DI из `app.state` и явная обработка ошибок (`400`, `502`, `503` + `Retry-After`).

---

## Переменные окружения (`.env`)

| Переменная | По умолчанию | Назначение |
| :--- | :--- | :--- |
| `GEMINI_API_KEYS` | `""` | Список API-ключей Gemini через запятую |
| `GEMINI_API_KEY` | `""` | Одиночный ключ Gemini (если пуст `GEMINI_API_KEYS`) |
| `GEMINI_DECISION_MODEL` | `gemini-decision-1` | Модель Gatekeeper (проверка: лист/не лист, сложность) |
| `GEMINI_FLASH_MODEL` | `gemini-3.6-flash` | Основная Vision-модель извлечения данных |
| `GEMINI_FALLBACK_MODELS` | `gemini-3-flash-preview,gemini-3.7-flash,gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite` | Резервная цепочка моделей при `503`/`504`/`429`/`404` |
| `ENABLE_GATEKEEPER` | `true` | Включить предварительную проверку через `gemini-decision-1` |
| `GEMINI_GATEKEEPER_FAIL_OPEN` | `true` | При сбое Gatekeeper пропускать лист напрямую в экстрактор |
| `GEMINI_RPM_LIMIT` | `5` | Максимум одновременных запросов к Gemini API |
| `GEMINI_REQUEST_TIMEOUT_MS` | `25000` | Таймаут одного вызова модели в миллисекундах |
| `GEMINI_SDK_MAX_ATTEMPTS` | `1` | Число попыток внутри SDK до переключения на fallback-модель |
| `GEMINI_MODEL_COOLDOWN_SECONDS` | `120.0` | Пауза модели после `503`/`504`/таймаута |
| `GEMINI_THINKING_LEVEL` | `LOW` | Уровень размышлений Gemini 3 (`LOW`, `MINIMAL`, `MEDIUM`, `HIGH`) |
| `CROP_FORMAT` | `JPEG` | Формат фрагментов (`JPEG`, `WEBP`, `PNG`) |
| `CROP_QUALITY` | `88` | Качество сжатия `JPEG`/`WEBP` (`50..100`) |
| `CROP_MIN_PX` / `CROP_MAX_PX` | `1000` / `1400` | Ограничение длинной стороны листа и квадрантов |
| `MAX_IMAGE_SIZE_MB` | `15` | Максимальный размер входного файла |
| `CACHE_DIR` | `.cache/sheets` | Путь к кэшу (относительные пути резолвятся внутри `services/sheet_parser`) |
| `REFERENCE_YEAR` | `2026` | Опорный год для расчёта возраста и 3–5-летнего коридора |

---

## Быстрый старт (локально)

Все команды ниже выполняются из каталога `services/sheet_parser`:

### 1. Создание виртуального окружения (если запускаете впервые)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -e ".[dev]"
```

### 2. Настройка `.env`

В PowerShell:
```powershell
Copy-Item .env.example .env
```

В командной строке Windows (`cmd`):
```cmd
copy .env.example .env
```

Укажите рабочий ключ Google AI Studio в `GEMINI_API_KEYS`.

### 3. Запуск API-сервера

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
```

Интерактивная документация OpenAPI: `http://localhost:8000/docs`.

---

## Запуск в Docker

Из каталога `services/` (через Compose):

```powershell
docker compose up --build -d
```

Или сборка и запуск только образа `sheet_parser` из каталога `services/sheet_parser/`:

```powershell
docker build -t sheet-parser-service .
docker run --rm -p 8000:8000 --env-file .env -v "${PWD}/.cache:/app/.cache" sheet-parser-service
```

---

## Основные эндпоинты и примеры запросов

- `GET /health` — статус сервиса, количество ключей Gemini и директория кэша.
- `POST /api/v1/sheets/parse` — загрузка изображения (`multipart/form-data`, поле `file`, query `?force_refresh=true`).
- `POST /api/v1/sheets/parse-url` — скачивание и парсинг снимка по URL (`{"url": "...", "force_refresh": false}`).
- `POST /api/v1/lots/batches` — пакетный разбор `1..10` файлов (`202 Accepted`, возвращает `batch_id`).
- `GET /api/v1/lots/batches/{batch_id}` — статус и результаты по мере готовности.
- `POST /api/v1/lots/batches/{batch_id}/items` — догрузка файлов в существующую пачку.

Примеры в `curl.exe` (Windows):

```cmd
curl.exe http://localhost:8000/health
curl.exe -X POST "http://localhost:8000/api/v1/sheets/parse" -F "file=@..\..\sample_sheets\06_taa_toyota_corolla_touring_3142_grade_3_5.png"
```

## Запуск тестов

```powershell
.\.venv\Scripts\pytest.exe tests -v
```
