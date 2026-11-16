# План предрефактора (PR 0): функциональные и логические исправления

> **База:** ветка `refactor/architecture-prep` ([ARCHITECTURE_REFACTORING_PLAN.md](ARCHITECTURE_REFACTORING_PLAN.md))
> **Статус:** Утверждено в `/grill-me`. Выполняется **до** переноса/нарезки модулей, чтобы не переносить логические дефекты в новую архитектуру.

---

## Блок A (P0) — Расчёты, вердикты, статусы и пайплайн

1. **Актуальный `lot` в `compute_verdict` после пересчёта и сброса** (`backend/apps/lots/recalc.py`)
   - Вызывать `lot.refresh_from_db()` сразу после `recompute_lot_economics(...)` (до `compute_verdict(lot)`) в `recalculate_lot` и `reset_lot_simulation`, чтобы вердикт всегда соответствовал новой лесенке цен.
2. **METI-санкции для ДВС > 1900 см³ с неизвестным/иным `fuel_type`** (`backend/apps/lots/customs.py`)
   - В `meti_sanction_risk()` проверять `engine_cc > 1900` для любого не-EV/не-hybrid топлива (включая `None` и `FuelType.OTHER`).
3. **Разделение `airbag_deployed` и `FLOOD_OR_FIRE` в чеклисте безопасности** (`backend/apps/lots/safety.py`)
   - Убрать `flags.airbag_deployed` из условия `CRITICAL` строки `FLOOD_OR_FIRE` («Следы затопления / пожара / града») — подушки отражаются в своей строке `AIRBAGS_SRS`.
4. **Проверка обязательных полей паспорта до расчёта стартовой ставки** (`backend/apps/lots/pipeline.py`, `economics.py`)
   - Проверять наличие `first_reg_year` и `engine_cc` (для не-EV) в `_resolve_start_bid_jpy` / до вызова `derive_start_bid_from_market`, чтобы `_missing_customs_inputs` показывал точную причину вместо ошибки подбора ставки.
5. **Надёжность батчей и параллельных стадий** (`backend/apps/lots/pipeline.py`, `integrations/aleado/service.py`)
   - Обновлять `Batch.updated_at` при взятии и завершении каждого элемента в `run_batch_pipeline` (heartbeat, чтобы здоровый батч > 15 мин не перезапускался параллельно вторым воркером).
   - Ограничить/дожидаться завершения потоков в `_run_parallel_steps` или проверять cancel/non-FAILED статус перед мутацией `BatchItem` и `Lot`.
6. **Безопасная обработка `partial` OCR-лотов без HTTP 500** (`backend/apps/lots/queries.py`, `integrations/ml/parser.py`)
   - Оставлять `READY` при наличии критичных полей экономики; в `_build_normalized_sheet` подставлять честные фоллбэки для второстепенных полей (`OdometerStatus.UNKNOWN`, `FrameIdConfidence.RAW`, `transmission="не указана"`, `""` для пустых `model_code`/`chassis_number`) + предупреждение в `ocr_warnings`.
   - Сбрасывать невалидный `first_reg_month` (вне `1..12`) в `None` с предупреждением вместо падения `date(year, month, 15)`.
7. **Логика Aleado и нижний порог ставки** (`backend/apps/lots/integrations/aleado/service.py`, `economics.py`)
   - Не записывать аукционную стартовую цену `row.start_price_jpy` в `PastAuctionRecord.closing_price_jpy` (оставлять `None`, если нет фактической цены продажи).
   - Снизить минимальный порог ставки/слайдера в `_resolve_start_bid_jpy` до `100_000 ¥` синхронно с API (`recalc.py`).
   - В `_candidate_is_own_lot()` проверять непустоту `auction_branch`/`auction_house` до поиска подстроки.
   - В `clean_model_code()` поддержать однобуквенные коды кузова (`E12`, `T32`, `C27`, `L375S` и т.д., `[A-Z]{1,5}\d{1,4}[A-Z]{0,2}`) и 3-сегментные katashiki (`3BA-NRE210W-AWXNB`).
   - В `_evaluate_rules()` убрать `continue`, чтобы при оценке `R` не пропускалась проверка скрутки одометра `odometer_rollback`; расширить ремонтные оценки (`RB`, `RC`, `R1`, `R2`, `1`, `2`, `99`, `***`) и оценку `S`; не отправлять строки с `trading_date=None` в `verified_past` с сегодняшней датой.

---

## Блок B (P1) — Интеграции (`drom`, `farpost`, `currency`, `ml_service`)

1. **Drom каскад, URL-усечение и подбор `power_hp`**:
   - В `DromMarketService._build_step_url` сохранять `frame_type_id` на шагах `rf`, чтобы не смешивать типы кузова одной модели (`Corolla Touring` vs седан/хэтч, `Impreza Sport` vs `G4`).
   - Пробрасывать `lot.trim` в `DromSearchCriteria` и `DromPowerResolver.resolve`, чтобы не отфильтровывались `Type R`, `Touring`, `Turbo`, `NISMO`, `STI` у порога 160 л.с.
   - В `DromPowerResolver` использовать точную нормализацию в ключе каталога (и не кешировать неполный результат на 14 дней при обрыве по 403/429).
   - В `_truncate_drom_url` обрезать сначала хвостовые query-параметры, не ломая path-слаги марки/модели.
2. **Farpost кэш, матрица ремонта и кузовной код**:
   - Расширить окно `_stale_fallback` в `farpost/service.py` (например, до 7 дней, синхронно с `currency`), чтобы протухший 24-часовой кэш реально работал как fallback при сбоях/cooldown.
   - Обновить `repair_matrix.json` (+ `DefectCode` при необходимости) по рыночным котировкам Владивостока (Farpost + `research/03_AUCTION_INSPECTION_AND_REPAIR_ECONOMETRICS.md`):
     - `G` / `G1` (скол лобового полимером): `1 500 ₽` (рынок Farpost Владивосток: 700–1 800 ₽), `G2` / `G3` (глубокий скол/трещина): `2 000` / `2 500 ₽`, с корректной подписью работы по стеклу (не «PDR / полировка» и не `21 500 ₽` кузовщины; полная замена лобового остаётся на `X`/`XX`).
     - `P1`..`P3` (выцветание/облезание лака): покраска `11 000 ₽` (как `P`).
     - `R` (следы прошлого ремонта): `0 ₽` (`{}`), без накрутки `21 500 ₽`.
     - `S3` / `C3`: на уровне максимума коррозии/ржавчины (`6 500` / `37 500 ₽`).
   - В `_contains_code` / `_body_code` учитывать возможный суффикс кузова при синтезированном `frame_id` (`NRE210` → матчит и `NRE210W`).
3. **Currency и `ml_service`**:
   - В `currency/service.py` форматировать процент спреда без научной нотации (`10%`, а не `1E+1%`).
   - В `currency/cache.py` переиспользовать `upsert_external_cache` с защитой от гонки `IntegrityError`.
   - В `ml_service`:
     - При `normalize_auction_house == "OTHER"` всё равно пытаться определить дом по `ext.auction_house` (от распознавания логотипа).
     - Исправить `synthesize_frame_id` для 3-сегментных katashiki (`3BA-NRE210W-AWXNB`) и коротких кодов (`GB5-100`).
     - Сохранять `color_changed_ru` до `NormalizedSheetEntity` (`extra_ru`).
     - Не кэшировать `frame_id=None` в `ChassisOcrClient` навсегда без TTL.
     - Исправить `gemini_rpm_limit` в `GeminiKeyPool` (реальное ограничение RPM или разделение concurrency vs RPM).

---

## Блок C (P2) — Логика симулятора, батчей и риск-чипов на фронте

1. **Симулятор экономики и ручной `power_hp`** (`LotTabEconomics.vue`, `lotPresentation.ts`, `stores/lots.ts`, `backend/apps/lots/recalc.py`, `schemas.py`):
   - Добавить в симулятор компактный ввод мощности `custom_power_hp` (при `power_hp === null`, для EV или корректировке) и возвращать обновлённые `power_hp`, `power_hp_source`, `is_under_160_hp`, `ocr_warnings` из `RecalculateResponse`, чтобы UI и предупреждения обновлялись сразу без F5.
   - Убрать хардкод `'5 200 ₽'` в подписи утильсбора (учитывать `3 400 ₽` для авто `< 3` лет и явно пояснять обязательный коммерческий утиль при `power_hp === null`).
   - Синхронизировать минимум ввода ставки в рублях с API (`100 000 ¥ * jpyRate`) и откатывать черновые значения слайдера/свитчей при ошибке `/recalculate`.
   - Добавить недостающие 4 флага (включая критический `underbody_corrosion`) в `buildActiveRiskLabels`.
2. **Прогресс батча** (`batches.ts`, `BatchProgressView.vue`):
   - Разрешить дозагрузку в батч при статусе `partial_failed` (синхронно с бэкендом).
   - Добавить корректное отображение мягко удалённого готового лота (`"Удалён"` вместо попадания в `"В очереди"`).
