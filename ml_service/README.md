# Auction Sheet Parser Microservice (`ml-service`)

Асинхронный FastAPI-микросервис для распознавания, перевода и нормализации японских автомобильных аукционных листов в слоистой DDD-архитектуре (`domains` ← `factories` ← `services` ← `infrastructure` & `api`).

## Архитектура

- `domains/` — чистые `@dataclass`-сущности и `Enum`-перечисления (`AuctionHouse`, `BodyPanel`, `DefectCode`, `TaskStep`, `BatchStatus`, `BatchItemState`) без зависимостей от FastAPI, Pydantic и Pillow.
- `factories/` — детерминированные нормализаторы японских дат (`R`/`H`/`S`, кандзи и «голых» годов), синтез `Frame ID`, валидация кодов дефектов (`DefectCode`, `S小` → `S1` + пометка `small`, `R`, `description_ru`, сохранение неизвестных кодов с warning `unknown_defect_code:<код>`), токенный матчинг аукционных домов по таблице `D1`, нормализация КПП/цвета, построчные риск-флаги, рендер Markdown и сборка `ParserResultEntity`.
- `infrastructure/`:
  - `AsyncImageLoader` (`httpx` + `sha256` + проверка `Content-Type` и сигнатур `JPEG`/`PNG`/`WEBP`/`HEIC`/`HEIF` через `pillow-heif` + стриминг с пошаговым лимитом размера + SSRF-защита URL, редиректов и асинхронного DNS);
  - `PillowImageCropper` (обрезка белых полей, 2×2 пересекающихся квадранта 60%×60%, в продакшн-конфиге компактное `JPEG`-сжатие `1000–1400 px`, `quality=88`);
  - `ResultCache` (двухуровневый memory + JSON-кэш на диске по SHA-256);
  - `GeminiKeyPool` (Round-Robin пул ключей, `asyncio.Semaphore`, cooldown при `429`);
  - `AsyncGeminiVisionClient` (`gemini-decision-1` Gatekeeper с `fail_open` и warning, параллельный `FastHeaderPreview` ≤ 1.2 с для `preview_title`, основная модель `gemini-3.6-flash` + автоматический failover/hedging через 8 с по резервной цепочке с общим дедлайном 45 с и телеметрией `meta.attempts`).
- `services/` — `SheetParserService` и `BatchParserService` (пачки `1..10` снимков с UUID v4, TTL-очисткой и лимитом очереди, синхронной валидацией на входе, `409` при догрузке в завершённую пачку и Live Polling с `mascot` и `preview_title`).
- `api/` — тонкие FastAPI-контроллеры, аутентификация всех эндпоинтов по заголовку `X-API-Key` (constant-time `hmac.compare_digest`, fail-closed), sliding-window rate limiting, DI из `app.state`, строгие схемы `extra="forbid"` и ошибки в формате RFC 7807 (`application/problem+json` с `invalid_params` и `timestamp`: `400`, `401`, `404`, `409`, `422`, `429`, `502`, `503` + `Retry-After`).

---

## Переменные окружения (`.env`)

| Переменная | По умолчанию | Назначение |
| :--- | :--- | :--- |
| `ML_SERVICE_API_KEY` | `""` | Сервисный ключ для обязательного заголовка `X-API-Key` на всех ручках (включая `/health`) |
| `ML_SERVICE_API_KEYS` | `""` | Список сервисных `X-API-Key` через запятую для ротации (приоритетнее `ML_SERVICE_API_KEY`) |
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
| `GEMINI_KEY_COOLDOWN_SECONDS` | `30.0` | Пауза ключа после HTTP `429` |
| `GEMINI_THINKING_LEVEL` | `LOW` | Уровень размышлений Gemini 3 (`LOW`, `MINIMAL`, `MEDIUM`, `HIGH`) |
| `GEMINI_REQUEST_DEADLINE_SECONDS` | `45.0` | Общий дедлайн разбора на всю цепочку моделей |
| `GEMINI_HEDGE_DELAY_SECONDS` | `8.0` | Задержка перед параллельным запуском резервной модели (hedging) |
| `GEMINI_FAST_HEADER_TIMEOUT_SECONDS` | `1.2` | Жёсткий таймаут быстрого предпросмотра шапки (`preview_title`) |
| `DEFAULT_AUCTION_STRICTNESS` | `0.65` | Индекс строгости по умолчанию для `AuctionHouse.OTHER` |
| `BATCH_POLL_INTERVAL_MS` | `1500` | Рекомендуемый интервал поллинга пачки в ответе `202` |
| `BATCH_MAX_ITEMS` | `10` | Максимум файлов в одной пачке |
| `BATCH_MAX_CONCURRENCY` | `3` | Максимум одновременно разбираемых листов в пачке |
| `BATCH_MAX_STORED_BATCHES` | `200` | Максимум хранимых в памяти пачек |
| `BATCH_TTL_SECONDS` | `1800` | TTL завершённых пачек в памяти перед автоочисткой |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `120` | Лимит запросов в минуту на IP (`0` отключает) |
| `CROP_FORMAT` | `JPEG` | Формат фрагментов (`JPEG`, `WEBP`, `PNG`) |
| `CROP_QUALITY` | `88` | Качество сжатия `JPEG`/`WEBP` (`50..100`) |
| `CROP_MIN_PX` / `CROP_MAX_PX` | `1000` / `1400` | Ограничение длинной стороны листа и квадрантов |
| `MAX_IMAGE_SIZE_MB` | `15` | Максимальный размер входного файла |
| `CACHE_DIR` | `.cache/sheets` | Путь к кэшу (относительные пути резолвятся внутри `ml_service/`) |
| `REFERENCE_YEAR` / `REFERENCE_MONTH` | `2026` / `11` | Опорные год и месяц для расчёта возраста и 3–5-летнего коридора |

---

## Быстрый старт (локально)

Все команды выполняются из каталога `project/ml_service`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -e ".[dev]"
Copy-Item .env.example .env
```

Укажите сервисный ключ `ML_SERVICE_API_KEY` (все эндпоинты, включая `/health`, защищены заголовком `X-API-Key` в режиме fail-closed) и рабочий ключ Google AI Studio в `GEMINI_API_KEYS` внутри `.env`, затем запустите сервер на порту **8001** (ожидаемый порт для `backend` `ML_SERVICE_URL=http://127.0.0.1:8001`):

```powershell
.\.venv\Scripts\uvicorn.exe ml_service.main:app --host 0.0.0.0 --port 8001 --reload
```

Интерактивная документация OpenAPI: `http://localhost:8001/docs`.

---

## Запуск в Docker

Из каталога `project/ml_service`:

```powershell
docker compose up --build -d
```

Или сборка и запуск вручную:

```powershell
docker build -t yuzu-ml-service .
docker run --rm -p 8001:8001 --env-file .env -v "${PWD}/.cache:/app/ml_service/.cache" yuzu-ml-service
```

Контейнер слушает порт `8001` (в Compose имя сервиса — `ml`, что соответствует `ML_SERVICE_URL=http://ml:8001` в `backend`).

---

## Основные эндпоинты и примеры запросов

Все ручки ниже (включая `/health`) требуют заголовок `X-API-Key` (`401 Unauthorized` при отсутствии/неверном ключе, `503 Service Unavailable` если ключ сервиса не настроен).

- `GET /health` — статус сервиса, количество ключей Gemini и опорный год.
- `POST /api/v1/sheets/parse` — загрузка изображения (`multipart/form-data`, поле `file`, query `?force_refresh=true`).
- `POST /api/v1/sheets/parse-url` — скачивание и парсинг снимка по URL (`{"url": "...", "force_refresh": false}`).
- `POST /api/v1/lots/batches` — пакетный разбор `1..10` файлов (`202 Accepted`, `total_items`, `batch_id: UUID`).
- `GET /api/v1/lots/batches/{batch_id}` — статус (`total_count`, `mascot`, `items[].preview_title`) и результаты по мере готовности.
- `POST /api/v1/lots/batches/{batch_id}/items` — догрузка файлов в активную пачку (`202 Accepted`, `BatchProgressResponse`, или `409 Conflict` для завершённой пачки).

```cmd
curl.exe -H "X-API-Key: <ML_SERVICE_API_KEY>" http://localhost:8001/health
curl.exe -H "X-API-Key: <ML_SERVICE_API_KEY>" -X POST "http://localhost:8001/api/v1/sheets/parse" -F "file=@tests/fixtures/real_sheets/taa_corolla_touring_3142.png"
```

## Запуск тестов и линтера

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\pytest.exe tests -m "not live" -v
```
