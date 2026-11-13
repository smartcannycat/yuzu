# Каноническая спецификация REST API и дата-контрактов AuctionCalc

> **Статус документа:** Официальный Single Source of Truth (SSOT)  
> **Версия API:** `v1.0.0` (FastAPI + Pydantic V2 / OpenAPI 3.1.0)  
> **Целевая платформа:** Мобильное приложение AuctionCalc (iOS / Android / Web-Mobile)  
> **Дизайн-система:** Clean Light / AuctionCalc Design System v2.1 ([DESIGN.md](../DESIGN.md))  
> **Связанные документы доменов:**
> - [01_sheet_and_tech.md](./domains/01_sheet_and_tech.md) (Аукционный лист, ТТХ, 16 панелей кузова, дефекты A2/U2/XX/W1)
> - [02_audit_and_safety.md](./domains/02_audit_and_safety.md) (Кросс-аудит по Frame ID, скрутка одометра, тотал R)
> - [03_economics_and_customs.md](./domains/03_economics_and_customs.md) (Таможня ЕАЭС 1.7€, утильсбор 5 200 ₽ vs 528k, смета Farpost 31 000 ₽, Wise)
> - [04_app_flow_and_api.md](./domains/04_app_flow_and_api.md) (Светофор, очереди DAG, маскот, эндпоинты)
> - [DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md) (Архитектура данных)
> - [auction_pipeline.md](./auction_pipeline.md) (Пайплайн OCR, Fast Header OCR, Gatekeeper)
> - [BENCHMARK_CASE_COROLLA_TOURING.md](./BENCHMARK_CASE_COROLLA_TOURING.md) (Эталонный бенчмарк Corolla Touring)

---

## 1. Архитектурные принципы и технологический стек

Спецификация клиентского API сервиса AuctionCalc спроектирована по стандарту **API-First** на основе строгих контрактов **Pydantic V2**: основной бэкенд строится на **Django Ninja** (бизнес-логика, JWT-авторизация, БД, внешние парсеры, расчеты), а ML-пайплайн распознавания вынесен в отдельный микросервис на **FastAPI** (Python 3.11+). Все структуры данных совместимы со спецификацией **OpenAPI 3.1.0** (JSON Schema 2020-12).

> **Аутентификация:** Все эндпоинты `/api/v1/lots*` требуют заголовок `Authorization: Bearer <access_token>` (JWT). Данные изолируются по `user_id`; при регистрации нового пользователя автоматически привязываются 3 стартовых эталонных лота для мгновенного знакомства с лентой.

```
   ┌────────────────────────────────────────────────────────────────────────┐
   │                 МОБИЛЬНЫЙ КЛИЕНТ (iOS / Android Flutter/React Native)  │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │ HTTPS / JSON / Multipart
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                         BFF / FASTAPI GATEWAY                          │
   │  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
   │  │  Pydantic V2 Contracts  │  │   OpenAPI 3.1 Schema Validation     │  │
   │  └─────────────────────────┘  └─────────────────────────────────────┘  │
   └───────┬───────────────────┬───────────────────┬───────────────────┬────┘
           │ D1                │ D2                │ D3                │ D4
           ▼                   ▼                   ▼                   ▼
     ┌───────────┐       ┌───────────┐       ┌───────────┐       ┌───────────┐
     │ Sheet OCR │       │ AucJP /   │       │ Customs   │       │ Scoring & │
     │ & Tech    │       │ Archive   │       │ & Farpost │       │ Mascot    │
     └───────────┘       └───────────┘       └───────────┘       └───────────┘
```

### 1.1. Базовые правила сериализации и типизации данных:
1. **Zero-Float Currency Rule (Дисциплина валют):**
   - Все финансовые величины в рублях (`RUB`) и японских иенах (`JPY`) строго целочисленные (`int`). Дробные рубли (копейки) в автобизнесе не используются.
   - Курсы валют ЦБ РФ (`JPY_RUB`, `EUR_RUB`, `USD_RUB`) передаются как числа с плавающей точкой (`float`, 3-4 знака).
   - Таможенная ставка в евро за 1 см³ (`duty_rate_eur_per_cc`) и сумма пошлины в евро (`customs_duty_eur`) передаются как `float` (с округлением до 2 знаков).
2. **Строгая конфигурация Pydantic V2:**
   - Все модели наследуются от `StrictBaseModel` с параметрами `extra="forbid"` (запрет скрытых полей), `str_strip_whitespace=True` (автоматическая очистка пробелов) и `validate_assignment=True`.
3. **Идентификаторы и даты:**
   - Все первичные ключи сущностей (`lot_id`, `batch_id`) типизированы как `UUID` (RFC 4122 v4).
   - Все временные метки передаются в стандарте **ISO 8601 UTC** (`YYYY-MM-DDTHH:MM:SSZ`).
4. **Унифицированный формат ошибок RFC 7807 (Problem Details):**
   - Любая ошибка бэкенда (`400`, `404`, `422`, `500`) возвращается в структуре `ProblemDetail`.

---

## 2. Справочник канонических перечислений (Enums)

Ниже приведены официальные перечисления системы, исключающие магические строки в кодовой базе и мобильном клиенте:

```python
from enum import Enum

class TrafficLightColor(str, Enum):
    """Цвет вердикта скоринга 'Аукционный светофор'"""
    GREEN = "green"    # Рекомендовано к покупке (чистая выгода >= 150k, рисков нет)
    YELLOW = "yellow"  # Внимание / нюансы (выгода 50k..150k, либо косметические дефекты)
    RED = "red"        # Покупка нецелесообразна (стоп-факторы, скрутка, выгода < 50k)

class AuctionHouse(str, Enum):
    """Нормализованное наименование японского аукционного дома"""
    TAA = "TAA"        # Toyota Auto Auction (высшая строгость 1.00)
    USS = "USS"        # USS Auction (базовая строгость 0.75)
    CAA = "CAA"        # Chubu Auto Auction (0.70)
    JU = "JU"          # Japanese Used Car Dealers Association (0.60)
    HONDA = "Honda"    # Honda Auto Auction (0.90)
    ARAI = "ARAI"      # Arai Auction (0.65)
    MIRIVE = "MIRIVE"  # Mirive Auto Auction (0.70)
    KCAA = "KCAA"      # Kyushu Car Auto Auction (0.60)
    LAA = "LAA"        # Light Auto Auction (0.65)
    ORIX = "ORIX"      # ORIX Auto Auction (0.80)
    ZIP = "ZIP"        # ZIP Auto Auction (0.75)
    AUCNET = "AUCNET"  # Aucnet Virtual (0.65)
    OTHER = "OTHER"    # Прочие региональные площадки

class BatchStatus(str, Enum):
    """Статус пачки загруженных аукционных листов"""
    QUEUED = "queued"                  # Пачка в очереди на обработку
    PROCESSING = "processing"          # Пайплайн DAG выполняется
    COMPLETED = "completed"            # Все листы пачки успешно обработаны
    PARTIAL_FAILED = "partial_failed"  # Часть листов обработана, часть отклонена
    FAILED = "failed"                  # Сбой обработки всей пачки

class ItemProcessingStatus(str, Enum):
    """Статус обработки конкретного файла в пачке"""
    QUEUED = "queued"          # В очереди
    PROCESSING = "processing"  # Обрабатывается
    READY = "ready"            # Успешно готов, сформирован lot_id
    FAILED = "failed"          # Ошибка (не лист, нечитаемо, расфокус)

class TaskStep(str, Enum):
    """Текущий шаг сквозного конвейера DAG"""
    GATEKEEPER = "gatekeeper"           # Первичная валидация изображения (лист ли это)
    FAST_HEADER_OCR = "fast_header_ocr" # Сверхбыстрое чтение шапки (марка, модель, лот) для Экрана 3
    GEMINI_OCR = "gemini_ocr"           # Полное извлечение ТТХ, заметок и карты дефектов нейросетью
    CROSS_AUDIT = "cross_audit"         # Сверка истории по Frame ID через статистику аукционов (AucJP / AAA Japan / Pravto / Aleado)
    CUSTOMS_CALC = "customs_calc"       # Расчет пошлины ЕАЭС и утильсбора
    FARPOST_PARTS = "farpost_parts"     # Оценка контрактных деталей и работ по ремонту
    DROM_MARKET = "drom_market"         # Подбор аналогов на рынке РФ (Drom.ru) + обогащение power_hp из каталога Drom
    SCORING = "scoring"                 # Скоринг светофора и формирование вердикта
    COMPLETED = "completed"             # Завершено
    FAILED = "failed"                   # Сбой на шаге

class MascotMood(str, Enum):
    """Эмоциональное состояние маскота-робота 🤖 AuctionCalc"""
    SLEEPING = "sleeping"  # Ожидание загрузки (Dropzone)
    THINKING = "thinking"  # Робот анализирует данные (Live Polling)
    HAPPY = "happy"        # Успешный вердикт / Зеленый светофор
    CONFUSED = "confused"  # Сложный случай / Желтый светофор
    WARNING = "warning"    # Обнаружен стоп-фактор / Красный светофор

class BodyPanel(str, Enum):
    """Справочник 16 канонических зон кузова для 2D-проекции"""
    FRONT_BUMPER = "front_bumper"              # 1. Передний бампер
    REAR_BUMPER = "rear_bumper"                # 2. Задний бампер
    HOOD = "hood"                              # 3. Капот
    ROOF = "roof"                              # 4. Крыша
    TAILGATE = "tailgate"                      # 5. Крышка багажника / пятая дверь
    FRONT_LEFT_FENDER = "front_left_fender"    # 6. Переднее левое крыло
    FRONT_RIGHT_FENDER = "front_right_fender"  # 7. Переднее правое крыло
    FRONT_LEFT_DOOR = "front_left_door"        # 8. Передняя левая дверь
    FRONT_RIGHT_DOOR = "front_right_door"      # 9. Передняя правая дверь
    REAR_LEFT_DOOR = "rear_left_door"          # 10. Задняя левая дверь
    REAR_RIGHT_DOOR = "rear_right_door"        # 11. Задняя правая дверь
    REAR_LEFT_QUARTER = "rear_left_quarter"    # 12. Заднее левое крыло
    REAR_RIGHT_QUARTER = "rear_right_quarter"  # 13. Заднее правое крыло
    LEFT_SILL = "left_sill"                    # 14. Левый порог
    RIGHT_SILL = "right_sill"                  # 15. Правый порог
    WINDSHIELD = "windshield"                  # 16. Лобовое стекло

class DefectCode(str, Enum):
    """Базовые коды повреждений с аукционных листов"""
    A = "A"    # Царапина (Scratch)
    U = "U"    # Вмятина (Dent)
    W = "W"    # Восстановительный окрас (Repaint)
    S = "S"    # Ржавчина (Rust)
    C = "C"    # Коррозия сквозная (Corrosion)
    XX = "XX"  # Замененная деталь (Replaced)
    X = "X"    # Деталь требует замены (Needs replacement)
    P = "P"    # Выгорание краски (Paint faded)
    G = "G"    # Скол на лобовом стекле (Glass stone chip)

class OdometerStatus(str, Enum):
    """Статус достоверности одометра"""
    CONFIRMED = "confirmed"  # Родной подтвержденный пробег
    REPLACED = "replaced"    # Символ '*': одометр менялся в Японии
    TAMPERED = "tampered"    # Символ '$': одометр скручен / сомнителен
    UNKNOWN = "unknown"      # Символ '#': пробег неизвестен

class RiskLevel(str, Enum):
    """Уровень риска безопасности кросс-аудита"""
    CLEAN = "CLEAN"        # Чистая история (🟢)
    INFO = "INFO"          # Повторные штатные торги (ℹ️)
    WARNING = "WARNING"    # Завышение оценки, вторичный окрас (🟡)
    CRITICAL = "CRITICAL"  # Скрутка, скрытый тотал R, нарушение геометрии (🔴)

class AgeCorridor(str, Enum):
    """Возрастной коридор таможни ЕАЭС"""
    UNDER_3_YEARS = "under_3_years"        # До 3 лет (по стоимости)
    THREE_TO_FIVE_YEARS = "3_to_5_years"  # 3-5 лет (проходной, минимальная ставка)
    OVER_5_YEARS = "over_5_years"          # Старше 5 лет (повышенная пошлина)

class UtilFeeType(str, Enum):
    """Тип ставки утилизационного сбора РФ"""
    PERSONAL = "personal"      # Льготный для физлиц (до 160 л.с. — 5 200 ₽)
    COMMERCIAL = "commercial"  # Коммерческий (по сетке ПП РФ № 1255 в зависимости от объема и возраста)

class ChecklistItemStatus(str, Enum):
    """Статус пункта проверки систем безопасности"""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class CrossAuditStatus(str, Enum):
    """Статус проверки лота по внешней базе (AucJP)"""
    CLEAN = "clean"                        # Чистая история / нарушений не выявлено
    ANOMALY_DETECTED = "anomaly_detected"  # Найдена критическая аномалия (скрутка, скрытый R)
    NOT_FOUND = "not_found"                # Записей по Frame ID не найдено
    LIVE_ONLY = "live_only"                # Проверено только по текущим торгам (бесплатный доступ без архива прошлых лет)
    UNAVAILABLE = "unavailable"            # Внешний источник временно недоступен / таймаут

class DriveType(str, Enum):
    """Тип привода"""
    TWO_WD = "2WD"
    FOUR_WD = "4WD"

class FuelType(str, Enum):
    """Тип топлива / силовой установки"""
    GASOLINE = "gasoline"
    HYBRID = "hybrid"
    DIESEL = "diesel"
    EV = "ev"
    OTHER = "other"

class LotLifecycleFilter(str, Enum):
    """Фильтр жизненного цикла лотов в ленте главного дашборда"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    ALL = "all"

class LotArchiveReason(str, Enum):
    """Причина перевода лота в архив"""
    EXPIRED = "expired"  # Автоархивация по истечении срока актуальности торгов
    MANUAL = "manual"    # Переведен в архив вручную пользователем
```

---

## 3. Базовые доменные контракты (Pydantic V2)

Ниже представлены Pydantic V2 модели данных, соответствующие доменам 1, 2, 3 и 4:

```python
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictBaseModel(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        use_enum_values=True
    )

class CurrencyRates(StrictBaseModel):
    jpy_rub_bank: float = Field(..., description="Коммерческий курс JPY/RUB (банк ДВ для оплаты авто и фрахта, ₽ за 1 ¥)", examples=[0.585])
    jpy_rate_source: str = Field("ДВ-банк (ориентир)", description="Источник курса JPY/RUB")
    eur_rub_cbrf: float = Field(..., description="Официальный курс EUR/RUB ЦБ РФ для расчёта пошлины", examples=[95.0])
    usd_rub_cbrf: float = Field(..., description="Официальный курс USD/RUB ЦБ РФ", examples=[85.0])
    cbrf_date: str = Field(..., description="Дата фиксации курсов ЦБ РФ (ДД.ММ.ГГГГ)", examples=["12.11.2026"])

class NormalizedDefect(StrictBaseModel):
    panel_id: BodyPanel = Field(..., description="Канонический идентификатор панели кузова (1 из 16)")
    panel_ru: str = Field(..., description="Русское наименование детали")
    defect_types: List[str] = Field(..., description="Типы повреждений (A, U, W, S, XX и т.д.)")
    severity: Optional[int] = Field(None, ge=1, le=3, description="Степень дефекта (1..3) или null для XX/X")
    raw_code: str = Field(..., description="Оригинальный код с аукционника (A2, U2, W1, XX)")
    description_ru: str = Field(..., description="Краткая расшифровка для легенды под схемой кузова (Экран 5)", examples=["Передняя левая дверь — замена (в цвет 070)"])

class RiskFlags(StrictBaseModel):
    """Все 13 канонических флагов безопасности из парсера аукционных листов"""
    is_flooded: bool = Field(False, description="🔴 Автомобиль-топляк (следы затопления)")
    airbag_deployed: bool = Field(False, description="🔴 Сработавшие подушки безопасности")
    hail_damage: bool = Field(False, description="🔴 Машина после градобоя")
    underbody_rust: bool = Field(False, description="🟡 Поверхностный налет ржавчины на подвеске")
    underbody_corrosion: bool = Field(False, description="🔴 Сквозная коррозия порогов/лонжеронов")
    core_support_repair: bool = Field(False, description="🔴 Ремонт рамки радиатора (コアサポート)")
    pillar_or_frame_repair: bool = Field(False, description="🔴 Ремонт несущих стоек и лонжеронов")
    panel_replaced_xx: bool = Field(False, description="ℹ️ Деталь уже менялась в Японии (код XX)")
    panel_needs_replacement_x: bool = Field(False, description="🟡 Деталь под замену (код X)")
    odometer_issue: bool = Field(False, description="🔴 Проблемы с одометром: скручен ($), заменен (*), неизвестен (#)")
    color_changed: bool = Field(False, description="ℹ️ Отметка о смене цвета (色替)")
    windshield_damage: bool = Field(False, description="🟡 Скол/трещина/замена лобового стекла (FW, G)")
    repaired_grade_r_ra: bool = Field(False, description="🔴 Официальный аварийный статус R/RA/0")

class NormalizedSheet(StrictBaseModel):
    lot_number: str = Field(..., description="Номер лота на аукционе", examples=["3142"])
    auction_house: AuctionHouse = Field(..., description="Канонический аукционный дом")
    auction_branch: Optional[str] = Field(None, description="Филиал площадки, если указан на листе", examples=["TAA Chubu"])
    auction_date: Optional[str] = Field(None, description="Дата текущих торгов в формате ДД.ММ.ГГГГ (если распознана с листа/источника; null при обрезанном фото)", examples=["14.11.2026"])
    auction_strictness_index: float = Field(..., ge=0.0, le=1.0, description="Индекс строгости (0.55..1.00)", examples=[1.00])
    make: str = Field(..., description="Марка автомобиля латиницей", examples=["Toyota"])
    model: str = Field(..., description="Модель автомобиля латиницей", examples=["Corolla Touring"])
    trim: Optional[str] = Field(None, description="Комплектация (опционально для БД/PDF, не выносится в заголовок карточки)", examples=["W×B"])
    model_code: str = Field(..., description="Заводской код модели кузова", examples=["3BA-NRE210W"])
    chassis_number: str = Field(..., description="Серийный номер шасси", examples=["NRE210-2005418"])
    frame_id: str = Field(..., description="Канонический Frame ID", examples=["NRE210-2005418"])
    frame_id_confidence: Literal["exact", "synthesized", "raw"] = Field("exact", description="Достоверность Frame ID")
    first_reg_year: Optional[int] = Field(None, description="Год первой регистрации", examples=[2020])
    first_reg_month: Optional[int] = Field(None, ge=1, le=12, description="Месяц первой регистрации", examples=[10])
    first_reg_date_str: Optional[str] = Field(None, description="Дата и возраст", examples=["10.2020 (3-5 лет, ЕАЭС)"])
    is_pass_corridor_3_5: Optional[bool] = Field(None, description="Проходной возраст 3-5 лет (null, если дата не распознана)")
    engine_cc: Optional[int] = Field(None, description="Объем двигателя в см³", examples=[1196])
    power_hp: Optional[int] = Field(None, description="Мощность двигателя в л.с. (автоматически подтягивается из каталога Drom.ru по model_code/году или локального кэша katashiki)", examples=[116])
    power_hp_source: Optional[Literal["drom_catalog", "katashiki_cache", "manual"]] = Field(None, description="Источник мощности для расчета порога 160 л.с.")
    is_under_160_hp: Optional[bool] = Field(None, description="Мощность <= 160 л.с. (льготный утильсбор; null если мощность не найдена)")
    mileage_km: Optional[int] = Field(None, ge=0, description="Пробег в км", examples=[58240])
    odometer_status: OdometerStatus = Field(..., description="Статус одометра")
    transmission: str = Field(..., description="Тип КПП на русском", examples=["6MT"])
    drive_type: Optional[DriveType] = Field(None, description="Привод (2WD / 4WD)")
    fuel_type: Optional[FuelType] = Field(None, description="Тип топлива")
    color_ru: Optional[str] = Field(None, description="Цвет кузова на русском", examples=["Белый перламутр"])
    paint_code: Optional[str] = Field(None, description="Заводской код краски", examples=["070"])
    overall_grade: str = Field(..., description="Общая оценка аукциона", examples=["3.5"])
    exterior_grade: Optional[str] = Field(None, description="Оценка экстерьера", examples=["C"])
    interior_grade: Optional[str] = Field(None, description="Оценка интерьера", examples=["B"])
    shaken_until: Optional[str] = Field(None, description="Срок техосмотра Shaken в Японии (если указан)")
    recycling_fee_yen: Optional[int] = Field(None, ge=0, description="Японский утильсбор с листа (JPY)")
    recycling_fee_paid: Optional[bool] = Field(None, description="Отметка об оплате японского утильсбора")
    equipment_ru: List[str] = Field(default_factory=list, description="Список опций")
    defects: List[NormalizedDefect] = Field(default_factory=list, description="Дефекты кузова (до 16 панелей)")
    risk_flags: RiskFlags = Field(..., description="Флаги безопасности (13 флагов)")
    inspector_notes_ru: List[str] = Field(default_factory=list, description="Перевод замечаний инспектора")
    inspector_notes_raw: List[str] = Field(default_factory=list, description="Исходные японские замечания инспектора для Bottom Sheet")
    seller_comments_ru: List[str] = Field(default_factory=list, description="Перевод заметок продавца")
    extra_ru: List[str] = Field(default_factory=list, description="Дополнительные отметки с бланка")
    ocr_warnings: List[str] = Field(default_factory=list, description="Предупреждения парсера (например, нечеткий скан или синтезированный Frame ID)")
    low_confidence_fields: List[str] = Field(default_factory=list, description="Поля с низкой уверенностью распознавания")

class AnomalyAlert(StrictBaseModel):
    type: str = Field(..., description="Тип аномалии")
    severity: Literal["critical", "warning", "info"] = Field(..., description="Уровень критичности")
    title_ru: str = Field(..., description="Заголовок аномалии")
    message_ru: str = Field(..., description="Разъяснение нестыковки")
    diff_details: Optional[Dict[str, Any]] = Field(None, description="Объект расхождений 'было-стало'")

class PastAuctionRecord(StrictBaseModel):
    auction_date: str = Field(..., description="Дата прошлых торгов (ДД.ММ.ГГГГ)", examples=["15.11.2023"])
    auction_house: str = Field(..., description="Аукцион прошлых торгов", examples=["TAA Chubu"])
    auction_strictness: Optional[float] = Field(None, description="Индекс строгости площадки", examples=[1.00])
    lot_number: str = Field(..., description="Номер архивного лота", examples=["3142"])
    overall_grade: str = Field(..., description="Оценка на прошлых торгах", examples=["3.5"])
    mileage_km: Optional[int] = Field(None, description="Пробег на прошлых торгах", examples=[58240])
    defects_summary: Optional[str] = Field(None, description="Описание повреждений в архиве")
    closing_price_jpy: Optional[int] = Field(None, description="Цена закрытия в иенах", examples=[780000])
    sheet_archive_url: Optional[str] = Field(None, description="Ссылка на архивный скан листа")

class CrossAuditReport(StrictBaseModel):
    status: CrossAuditStatus = Field(..., description="Статус аудита по Frame ID в статистике аукционов")
    source_name: str = Field("AucJP + AAA Japan / Pravto", description="Агрегаторы статистики и истории торгов (см. Том 4)")
    is_archive_available: bool = Field(True, description="Удалось ли получить историю завершенных торгов (False только при фолбэке в live_only)")
    risk_level: RiskLevel = Field(..., description="Уровень риска безопасности")
    has_critical_anomaly: bool = Field(..., description="Флаг критической аномалии (триггер Sticky Alert)")
    headline_ru: str = Field(..., description="Краткий вывод проверки")
    times_auctioned: int = Field(..., ge=0, description="Сколько раз авто найдено на торгах")
    verified_at: datetime = Field(..., description="Время верификации (UTC)")
    anomalies: List[AnomalyAlert] = Field(default_factory=list, description="Список обнаруженных расхождений")
    history: List[PastAuctionRecord] = Field(default_factory=list, description="История торгов")

class DamagedPartItem(StrictBaseModel):
    """Карточка контрактной или кузовной детали для Bottom Sheet (Экран 7 — без прямых внешних ссылок)"""
    panel_id: BodyPanel = Field(..., description="Панель кузова")
    defect_code: str = Field(..., description="Код дефекта (XX, X, A2, U2)", examples=["XX"])
    part_name_ru: str = Field(..., description="Название заменяемой детали", examples=["Передняя левая дверь"])
    subtitle_ru: Optional[str] = Field(None, description="Пояснение под строкой", examples=["контрактная деталь в заводской цвет 070"])
    price_from_rub: int = Field(..., ge=0, description="Нижняя граница стоимости детали во Владивостоке (формат UI: 'от X ₽')", examples=[18000])
    in_stock_vladivostok: bool = Field(..., description="Наличие во Владивостоке", examples=[True])
    is_statistical_fallback: bool = Field(False, description="True, если взято из статистической матрицы ремонта вместо живого Farpost")

class ServiceWorkItem(StrictBaseModel):
    """Строка работ СТО для Bottom Sheet сметы ремонта (Экран 7)"""
    work_type: Literal["mount_dismount", "paint", "pdr_and_polish", "bodywork"] = Field(..., description="Категория работ")
    label_ru: str = Field(..., description="Название работы для UI", examples=["Снятие и монтаж двери"])
    amount_rub: int = Field(..., ge=0, description="Стоимость работы в рублях", examples=[4000])
    zero_cost_reason_ru: Optional[str] = Field(None, description="Причина нулевой стоимости (например, 'не требуется' при детали в цвет)", examples=["не требуется"])

class FarpostRepairSummary(StrictBaseModel):
    parts: List[DamagedPartItem] = Field(default_factory=list, description="Список деталей под замену (блок 1 на Экране 7)")
    service_works: List[ServiceWorkItem] = Field(default_factory=list, description="Список работ СТО (блок 2 на Экране 7)")
    total_parts_from_rub: int = Field(..., ge=0, description="Сумма деталей 'от ...'", examples=[18000])
    total_works_rub: int = Field(..., ge=0, description="Сумма работ СТО", examples=[13000])
    grand_total_repair_rub: int = Field(..., ge=0, description="Итоговый расчетный ремонт", examples=[31000])
    has_color_matched_parts: bool = Field(..., description="Есть ли детали, подобранные в заводской цвет без покраски")
    included_in_turnkey_hint_ru: str = Field("Сумма уже включена в расчёт под ключ", description="Пояснение в футере Bottom Sheet (Экран 7)")

class WiseCostStep(StrictBaseModel):
    step_number: int = Field(..., ge=1, le=10, description="Порядковый номер шага лестницы затрат")
    name_ru: str = Field(..., description="Наименование статьи расходов")
    amount_rub: int = Field(..., ge=0, description="Сумма в рублях РФ")
    original_currency: Optional[str] = Field(None, description="Оригинальная валюта (JPY, EUR, RUB)")
    original_amount: Optional[float] = Field(None, description="Сумма в оригинальной валюте")
    is_optional: bool = Field(False, description="Признак отключаемого шага (смета ремонта)")

class WiseCostLadder(StrictBaseModel):
    car_bid_jpy: int = Field(..., ge=0, description="Ставка на аукционе в JPY", examples=[780000])
    car_bid_rub: int = Field(..., ge=0, description="Эквивалент ставки в RUB", examples=[500760])
    turnkey_cost_rub: int = Field(..., ge=0, description="Итого расходов под ключ во Владивостоке", examples=[1104899])
    market_price_rf_rub: int = Field(..., ge=0, description="Медианная рыночная цена в РФ (Drom)", examples=[1520000])
    net_benefit_rub: int = Field(..., description="Чистая выгода клиента", examples=[415101])
    benefit_percentage: float = Field(..., description="Процент выгоды", examples=[37.6])
    steps: List[WiseCostStep] = Field(..., description="Шаги прозрачной лестницы расходов (Экран 6)")

class MarketComparisonInfo(StrictBaseModel):
    """Данные для сравнения с рынком РФ на Drom.ru (Экран 4, строка Drom + Экран 6)"""
    market_price_rf_rub: int = Field(..., ge=0, description="Медианная цена аналогов в РФ (₽)", examples=[1520000])
    analogs_count: int = Field(..., ge=0, description="Количество найденных сопоставимых объявлений в наличии в РФ", examples=[14])
    price_min_rub: Optional[int] = Field(None, ge=0, description="Минимум по выборке аналогов РФ", examples=[1390000])
    price_max_rub: Optional[int] = Field(None, ge=0, description="Максимум по выборке аналогов РФ", examples=[1680000])
    search_region_ru: str = Field("ДФО / Владивосток", description="Регион поиска аналогов")
    excludes_under_order: bool = Field(True, description="Двухуровневая фильтрация: URL-фильтры Drom ('в наличии') + стоп-слова в описании ('под заказ', 'в пути', 'привезем') и отсечение нижних ценовых выбросов")
    filtered_out_under_order_count: int = Field(0, ge=0, description="Количество отброшенных объявлений 'Под заказ / В пути' и ценовых аномалий", examples=[6])
    is_fallback: bool = Field(False, description="True, если точных аналогов < 3 и выборка расширена по РФ/годам")
    fallback_reason_ru: Optional[str] = Field(None, description="Пояснение расширения выборки при малом числе объявлений")
    drom_search_url: str = Field(..., description="Готовая ссылка с фильтрами на поиск аналогов на Drom.ru")

class CustomsCalculation(StrictBaseModel):
    age_corridor: AgeCorridor = Field(..., description="Коридор возраста ЕАЭС")
    duty_calculation_mode: Literal["eur_per_cc", "pct_of_value"] = Field("eur_per_cc", description="Режим расчета пошлины: по ставке €/см³ (3-5 и 5+ лет) или % от цены с минимумом (до 3 лет)")
    engine_cc: int = Field(..., description="Рабочий объем двигателя в см³", examples=[1196])
    duty_rate_eur_per_cc: Optional[float] = Field(None, description="Ставка пошлины EUR за см³ (для 3-5 и 5+ лет)", examples=[1.70])
    effective_duty_pct: Optional[float] = Field(None, description="Процент пошлины от стоимости авто (для авто до 3 лет: 48-54%)")
    customs_duty_eur: float = Field(..., description="Пошлина в EUR", examples=[2033.20])
    customs_duty_rub: int = Field(..., description="Пошлина в RUB", examples=[193154])
    excise_rub: int = Field(0, ge=0, description="Акциз РФ (для электромобилей вне единых ставок ЕАЭС)", examples=[0])
    import_vat_rub: int = Field(0, ge=0, description="Ввозной НДС РФ (для электромобилей вне единых ставок ЕАЭС)", examples=[0])
    is_under_160_hp: Optional[bool] = Field(None, description="Мощность <= 160 л.с. (null если мощность не подтверждена)")
    is_commercial_util: bool = Field(..., description="Коммерческий утильсбор")
    utilization_fee_rub: int = Field(..., description="Утильсбор РФ", examples=[5200])
    customs_clearance_fee_rub: int = Field(..., description="Таможенный сбор за оформление", examples=[4268])
    freight_vladivostok_rub: int = Field(..., description="Морской фрахт во Владивосток и СВХ", examples=[95000])
    broker_svh_sbkts_rub: int = Field(..., description="Брокер, СБКТС, лаборатория, ЭПТС", examples=[43835])
    meti_sanction_risk: bool = Field(False, description="Риск санкционного ограничения экспорта (гибрид, EV или ДВС > 1900 см³)")
    rates_snapshot: CurrencyRates = Field(..., description="Снимок курсов валют (ЦБ РФ + коммерческий банк ДВ)")

class TrafficLightVerdict(StrictBaseModel):
    verdict: TrafficLightColor = Field(..., description="Цвет светофора (green, yellow, red)")
    headline: str = Field(..., description="Заголовок вердикта на Экране 4", examples=["РЕКОМЕНДОВАНО К ПОКУПКЕ"])
    short_verdict_label: str = Field(..., description="Короткая строка вердикта для карточки на Экране 1", examples=["🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ"])
    badge_text: str = Field(..., description="Текст зеленого/желтого/красного бейджа на Экране 4", examples=["Выгода: +415 101 ₽"])
    net_benefit_rub: int = Field(..., description="Чистая выгода в рублях", examples=[415101])
    benefit_percentage: float = Field(..., description="Процент выгоды", examples=[37.6])
    body_summary_ru: str = Field(..., description="Короткий буллит 'Кузов' на Экране 4 (состояние + ключ. ремонт)")
    interior_summary_ru: str = Field(..., description="Короткий буллит 'Салон' на Экране 4 (оценка + заметки)")
    reasoning_bullets: List[str] = Field(default_factory=list, description="Дополнительные тезисы для PDF-отчета")
```

---

## 4. Спецификация клиентских REST эндпоинтов приложения

```
[ Веб / PWA приложение: Сводка REST эндпоинтов ]
   │
   ├── Auth (JWT Bearer):
   │     ├── POST /api/v1/auth/register        ➔ Регистрация + выдача JWT + сид стартовых лотов
   │     ├── POST /api/v1/auth/login           ➔ Вход (email + пароль) ➔ access/refresh токены
   │     ├── POST /api/v1/auth/refresh         ➔ Обновление access_token по refresh_token
   │     └── GET  /api/v1/auth/me              ➔ Профиль текущего пользователя
   │
   ├── Lots & Pipeline (требуют Authorization: Bearer <token>):
   │     ├── (1)  POST   /api/v1/lots/batches             ➔ Загрузка пачки фото 1–10 файлов (Экран 2: Модалка)
   │     ├── (2)  GET    /api/v1/lots/batches/{batch_id}  ➔ Live Polling очереди 1.5с + Fast Header OCR (Экран 3)
   │     ├── (3)  POST   /api/v1/lots/batches/{batch_id}/items ➔ Догрузка файлов без прерывания (Экран 3: «Догрузить еще листы»)
   │     ├── (4)  GET    /api/v1/lots                     ➔ Главный дашборд: Активные / Архив, фильтры, счетчики и In-Progress (Экран 1)
   │     ├── (5)  GET    /api/v1/lots/{lot_id}            ➔ Полная спецификация лота: Табы 4, 5, 6 + Bottom Sheets (Экран 4–7)
   │     ├── (6)  POST   /api/v1/lots/{lot_id}/recalculate➔ Интерактивная симуляция ставки и утильсбора (Экран 6)
   │     ├── (7)  GET    /api/v1/lots/{lot_id}/report.pdf ➔ [P1] Серверный PDF (на MVP — клиентский экспорт HTML→PDF)
   │     ├── (8)  PATCH  /api/v1/lots/{lot_id}            ➔ Ручная архивация / возврат из архива (Экран 1, шапка деталей)
   │     ├── (9)  DELETE /api/v1/lots/{lot_id}            ➔ Soft-delete ненужного лота без корзины в UI (Экран 1, шапка деталей)
   │     └── (10) POST   /api/v1/lots/bulk-delete         ➔ Массовый soft-delete выбранных ненужных лотов (Экран 1)
```

---

### Блок Auth: Регистрация и JWT-авторизация

- **Эндпоинты:** `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `GET /api/v1/auth/me`
- **Назначение в UI:** Экран входа / регистрации и автоматическое продление сессии (`401 Unauthorized` -> refresh). При регистрации нового пользователя бэкенд опционально привязывает 3 стартовых эталонных лота (`Corolla Touring`, `Honda Vezel`, `Nissan Note`) в его ленту.

```python
class UserRegisterRequest(StrictBaseModel):
    email: str = Field(..., description="Email пользователя", examples=["alex@example.com"])
    password: str = Field(..., min_length=8, max_length=128, description="Пароль (от 8 символов)")
    name: Optional[str] = Field(None, max_length=100, description="Имя пользователя", examples=["Алексей"])

class UserLoginRequest(StrictBaseModel):
    email: str = Field(..., description="Email пользователя", examples=["alex@example.com"])
    password: str = Field(..., description="Пароль")

class TokenRefreshRequest(StrictBaseModel):
    refresh_token: str = Field(..., description="Действующий refresh JWT токен")

class UserProfileResponse(StrictBaseModel):
    user_id: UUID = Field(..., description="Идентификатор пользователя")
    email: str = Field(..., description="Email пользователя")
    name: Optional[str] = Field(None, description="Имя")
    created_at: datetime = Field(..., description="Дата регистрации (UTC)")

class AuthTokensResponse(StrictBaseModel):
    access_token: str = Field(..., description="JWT access token (Bearer)")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: Literal["bearer"] = Field("bearer", description="Тип токена")
    expires_in_sec: int = Field(3600, description="Время жизни access_token в секундах")
    user: UserProfileResponse = Field(..., description="Профиль пользователя")
```

- **HTTP Статус-коды Auth и защищенных роутов:**
  - `201 Created` (`/register`), `200 OK` (`/login`, `/refresh`, `/me`).
  - `401 Unauthorized` — Отсутствует/просрочен JWT или неверные учетные данные.
  - `409 Conflict` (`/register`) — Email уже зарегистрирован.

---

### Эндпоинт 1: Загрузка пачки аукционных листов

- **Название:** Загрузка пачки аукционных листов (Multi-sheet Upload)
- **HTTP Метод:** `POST`
- **Путь:** `/api/v1/lots/batches`
- **Назначение в UI:** **Экран 2 (Модалка добавления листов)**. Пользователь выбирает от 1 до 10 фотографий/сканов аукционных листов с устройства или с камеры смартфона в веб-приложении.
- **Content-Type:** `multipart/form-data`
- **Параметры:**

| Параметр | Расположение | Тип | Обязательный | Валидация | Описание |
| :--- | :--- | :--- | :-: | :--- | :--- |
| `files` | `form-data` | `List[UploadFile]` | **Да** | 1..10 файлов, MIME: `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif`. Размер до 15 МБ на файл. | Массив изображений аукционных листов. `HEIC/HEIF` (фото с камеры/галереи iPhone в Safari/веб-браузере) автоматически декодируется на бэкенде через `pillow-heif`. Ручных параметров mode нет — роутинг автоматический. |

#### Pydantic V2 модели Request / Response:

```python
class BatchCreateResponse(StrictBaseModel):
    batch_id: UUID = Field(..., description="Уникальный идентификатор созданной пачки")
    total_items: int = Field(..., ge=1, le=10, description="Количество принятых файлов")
    status: BatchStatus = Field(..., description="Статус пачки")
    created_at: datetime = Field(..., description="Время постановки в очередь (UTC)")
    poll_interval_ms: int = Field(1500, description="Рекомендуемый интервал опроса polling в миллисекундах")
```

#### HTTP Статус-коды:
- `202 Accepted` — Пачка успешно принята в асинхронную очередь DAG.
- `400 Bad Request` — Недопустимый формат файла, превышен лимит 10 файлов или размер файла > 15 МБ.
- `422 Unprocessable Entity` — Ошибка парсинга multipart-запроса.

#### Эталонный JSON-сниппет ответа (`202 Accepted`):
```json
{
  "batch_id": "4d1b8294-9876-4321-abcd-ef0123456789",
  "total_items": 4,
  "status": "queued",
  "created_at": "2026-11-13T10:15:00Z",
  "poll_interval_ms": 1500
}
```

---

### Эндпоинт 2: Live Polling очереди обработки и статуса маскота

- **Название:** Live Polling очереди обработки (Batch Progress & Mascot State)
- **HTTP Метод:** `GET`
- **Путь:** `/api/v1/lots/batches/{batch_id}`
- **Назначение в UI:** **Экран 3 (Очередь обработки и маскот 🤖)**. Клиент опрашивает этот роут каждые 1.5–2.0 секунды. Отображает прогресс-бар (`3/4`), статус каждой строки файла, мгновенное название машины из **Fast Header OCR** (`preview_title`, например `Subaru Forester #5190`) пока идет полный разбор, и готовые карточки. По клику на готовую строку (`status == "ready"`) клиент открывает лот (`GET /lots/{lot_id}`).
- **Параметры:**

| Параметр | Расположение | Тип | Обязательный | Валидация | Описание |
| :--- | :--- | :--- | :-: | :--- | :--- |
| `batch_id` | `Path` | `UUID` | **Да** | Валидный UUIDv4 | Идентификатор пачки |

#### Pydantic V2 модели Request / Response:

```python
class MascotState(StrictBaseModel):
    mood: MascotMood = Field(..., description="Эмоциональное состояние маскота-робота 🤖")
    phrase_ru: str = Field(..., description="Контекстная фраза маскота для UI")
    badge_text: str = Field(..., description="Текст прогресса ('Распознаем лоты... 3/4')")

class BatchItemStatus(StrictBaseModel):
    lot_id: Optional[UUID] = Field(None, description="Идентификатор лота (создается при принятии листа; null при failed / rejected_not_sheet или если лот уже удален пользователем)")
    file_index: int = Field(..., ge=0, description="Порядковый номер файла в пачке")
    original_filename: str = Field(..., description="Оригинальное имя загруженного файла")
    preview_title: Optional[str] = Field(None, description="Предварительное название из Fast Header OCR (make + model + #lot_number) пока полный анализ ещё идет", examples=["Subaru Forester #5190"])
    status: ItemProcessingStatus = Field(..., description="Статус обработки файла")
    current_step: TaskStep = Field(..., description="Текущий этап DAG-конвейера")
    error_message: Optional[str] = Field(None, description="Текст ошибки при сбое")
    summary: Optional['LotSummary'] = Field(None, description="Компактная карточка авто (заполняется при ready; null если лот был удален)")

class BatchProgressResponse(StrictBaseModel):
    batch_id: UUID = Field(..., description="Идентификатор опрашиваемой пачки")
    status: BatchStatus = Field(..., description="Общий статус пачки")
    mascot: MascotState = Field(..., description="Текущее состояние маскота 🤖")
    total_count: int = Field(..., ge=1, description="Всего файлов в пачке")
    processed_count: int = Field(..., ge=0, description="Полностью обработано файлов")
    ready_count: int = Field(..., ge=0, description="Успешно готовых лотов")
    failed_count: int = Field(..., ge=0, description="Забракованных файлов со сбоем")
    items: List[BatchItemStatus] = Field(..., description="Детальный статус каждого файла в очереди")
```

#### HTTP Статус-коды:
- `200 OK` — Успешное получение текущего состояния пачки.
- `404 Not Found` — Пачка с указанным `batch_id` не найдена в реестре очередей.

#### Эталонный JSON-сниппет ответа (`200 OK` — кейс 1 из 4 готов):
```json
{
  "batch_id": "4d1b8294-9876-4321-abcd-ef0123456789",
  "status": "processing",
  "mascot": {
    "mood": "thinking",
    "phrase_ru": "Распознаем лоты... 1/4",
    "badge_text": "1 из 4 готово"
  },
  "total_count": 4,
  "processed_count": 1,
  "ready_count": 1,
  "failed_count": 0,
  "items": [
    {
      "lot_id": "8fa1947b-1234-4567-8901-abcdef123456",
      "file_index": 0,
      "original_filename": "sheet_corolla_3142.jpg",
      "preview_title": "Toyota Corolla Touring #3142",
      "status": "ready",
      "current_step": "completed",
      "error_message": null,
      "summary": {
        "lot_id": "8fa1947b-1234-4567-8901-abcdef123456",
        "make": "Toyota",
        "model": "Corolla Touring",
        "year": 2020,
        "engine_cc": 1196,
        "frame_id": "NRE210-2005418",
        "auction_house": "TAA",
        "lot_number": "3142",
        "overall_grade": "3.5",
        "mileage_km": 58240,
        "turnkey_cost_rub": 1104899,
        "market_price_rf_rub": 1520000,
        "verdict": "green",
        "verdict_headline": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
        "net_benefit_rub": 415101,
        "meti_sanction_risk": false,
        "has_anomaly": false,
        "anomaly_text": null,
        "thumbnail_url": "https://cdn.auction-calc.ru/lots/3142/sheet_thumb.webp",
        "created_at": "2026-11-13T10:15:00Z"
      }
    },
    {
      "lot_id": "7bb2947b-0000-1111-2222-abcdef123456",
      "file_index": 1,
      "original_filename": "IMG_5190.heic",
      "preview_title": "Subaru Forester #5190",
      "status": "processing",
      "current_step": "farpost_parts",
      "error_message": null,
      "summary": null
    },
    {
      "lot_id": "6aa1947b-3333-4444-5555-abcdef123456",
      "file_index": 2,
      "original_filename": "sheet_harrier_5541.jpg",
      "preview_title": "Toyota Harrier #5541",
      "status": "processing",
      "current_step": "cross_audit",
      "error_message": null,
      "summary": null
    },
    {
      "lot_id": "5ff1947b-7777-8888-9999-abcdef123456",
      "file_index": 3,
      "original_filename": "sheet_note_1102.jpg",
      "preview_title": null,
      "status": "processing",
      "current_step": "fast_header_ocr",
      "error_message": null,
      "summary": null
    }
  ]
}
```

---

### Эндпоинт 3: Догрузка файлов в существующую очередь

- **Название:** Догрузка файлов в активную очередь (Append Sheets to Batch)
- **HTTP Метод:** `POST`
- **Путь:** `/api/v1/lots/batches/{batch_id}/items`
- **Назначение в UI:** **Экран 3 (Кнопка «Догрузить еще листы»)**. Позволяет пользователю прямо во время обработки текущих листов добавить в очередь еще 1–10 файлов без сброса активной пачки и без прерывания идущих процессов.
- **Content-Type:** `multipart/form-data`
- **Параметры:**

| Параметр | Расположение | Тип | Обязательный | Валидация | Описание |
| :--- | :--- | :--- | :-: | :--- | :--- |
| `batch_id` | `Path` | `UUID` | **Да** | Валидный UUIDv4 | Идентификатор существующей активной пачки |
| `files` | `form-data` | `List[UploadFile]` | **Да** | 1..10 файлов, MIME: `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif`. Размер до 15 МБ | Дополнительные файлы аукционных листов |

#### Pydantic V2 модель Response:
- Возвращает актуализированную модель `BatchProgressResponse` (аналогично Эндпоинту 2).

#### HTTP Статус-коды:
- `202 Accepted` — Новые файлы добавлены в очередь пачки, возвращается актуализированный объект `BatchProgressResponse`.
- `400 Bad Request` — Превышен суммарный лимит файлов в пачке (максимум 20) или недопустимый формат.
- `404 Not Found` — Пачка не найдена.
- `409 Conflict` — Пачка уже полностью завершена (`completed` или `failed`); клиент должен открыть новую пачку через `POST /api/v1/lots/batches`.

---

### Эндпоинт 4: Главный дашборд (Лента расчетов и блок In-Progress)

- **Название:** Главный дашборд расчетов (Feed, Filters & Active Batches)
- **HTTP Метод:** `GET`
- **Путь:** `/api/v1/lots`
- **Назначение в UI:** **Экран 1 (Главный дашборд)**. Единая LIFO-лента ранее рассчитанных автомобилей (от новых к старым), строка полнотекстового поиска `query`, чипсы фильтров по марке, модели и цвету вердикта светофора. Содержит отдельный блок `in_progress` для отрисовки выпадающей компактной плашки «⏳ В обработке: N авто ▾».
- **Параметры запроса (Query Parameters):**

| Параметр | Расположение | Тип | Обязательный | Дефолт | Описание |
| :--- | :--- | :--- | :-: | :-: | :--- |
| `query` | `Query` | `Optional[str]` | Нет | `None` | Полнотекстовый поиск (марка, модель, Frame ID, номер лота) |
| `make` | `Query` | `Optional[str]` | Нет | `None` | Фильтр по марке (например, `"Toyota"`) |
| `model` | `Query` | `Optional[str]` | Нет | `None` | Фильтр по модели (например, `"Corolla Touring"`) |
| `verdict` | `Query` | `Optional[TrafficLightColor]` | Нет | `None` | Фильтр по вердикту: `green`, `yellow`, `red` |
| `has_anomaly` | `Query` | `Optional[bool]` | Нет | `None` | Фильтр по наличию критических аномалий аудита |
| `lifecycle` | `Query` | `LotLifecycleFilter` | Нет | `"active"` | Фильтр жизненного цикла: `active` (актуальные), `archived` (архив), `all` (все не удаленные) |
| `page` | `Query` | `int` | Нет | `1` | Номер страницы (>= 1) |
| `page_size` | `Query` | `int` | Нет | `20` | Количество элементов (1..100) |
| `sort_by` | `Query` | `str` | Нет | `"created_at"` | Сортировка: `created_at`, `net_benefit`, `turnkey_cost` |
| `sort_order` | `Query` | `str` | Нет | `"desc"` | Порядок: `desc`, `asc` |

#### Pydantic V2 модели Request / Response:

```python
class LotSummary(StrictBaseModel):
    lot_id: UUID = Field(..., description="Уникальный идентификатор лота")
    make: str = Field(..., description="Марка авто", examples=["Toyota"])
    model: str = Field(..., description="Модель авто", examples=["Corolla"])
    year: Optional[int] = Field(None, description="Год выпуска (null при частичном OCR)", examples=[2020])
    engine_cc: Optional[int] = Field(None, description="Объем двигателя в см³", examples=[1196])
    frame_id: str = Field(..., description="Канонический номер кузова", examples=["NRE210-2005418"])
    auction_house: AuctionHouse = Field(..., description="Канонический аукционный дом")
    lot_number: str = Field(..., description="Номер лота", examples=["3142"])
    overall_grade: str = Field(..., description="Оценка аукциона", examples=["3.5"])
    mileage_km: Optional[int] = Field(None, ge=0, description="Пробег в км (null при неизвестном пробеге)", examples=[58240])
    turnkey_cost_rub: int = Field(..., description="Цена под ключ во Владивостоке", examples=[1104899])
    market_price_rf_rub: int = Field(..., description="Рыночная цена в РФ (Drom)", examples=[1520000])
    verdict: TrafficLightColor = Field(..., description="Цвет вердикта светофора", examples=[TrafficLightColor.GREEN])
    verdict_headline: str = Field(..., description="Текст вердикта в карточке", examples=["🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ"])
    net_benefit_rub: int = Field(..., description="Чистая выгода относительно рынка РФ", examples=[415101])
    meti_sanction_risk: bool = Field(False, description="Санкционный риск экспорта из Японии (гибрид, EV или ДВС > 1900 см³)")
    has_anomaly: bool = Field(..., description="Флаг аномалии кросс-аудита")
    anomaly_text: Optional[str] = Field(None, description="Текст предупреждения об аномалии")
    thumbnail_url: Optional[str] = Field(None, description="URL миниатюры оригинального скана аукционного листа (НЕ фото автомобиля)")
    auction_date: Optional[str] = Field(None, description="Дата текущих торгов в формате ДД.ММ.ГГГГ (null если дата не распознана)", examples=["14.11.2026"])
    is_archived: bool = Field(False, description="Флаг нахождения лота в архиве (скрыт из активной ленты по умолчанию)")
    archived_at: Optional[datetime] = Field(None, description="Время перевода в архив (UTC), null для активных лотов")
    archived_reason: Optional[LotArchiveReason] = Field(None, description="Причина архивации: expired (истек срок) | manual (вручную)")
    expires_at: Optional[datetime] = Field(None, description="Плановый дедлайн автоархивации (UTC): auction_date JST + 24ч либо created_at + 3 дня; null если автоархивация отключена после ручного возврата")
    created_at: datetime = Field(..., description="Время создания записи (UTC)")

class InProgressItemPreview(StrictBaseModel):
    """Строка в выпадающем аккордеоне '⏳ В обработке: N авто ▾' (без процентов)"""
    batch_id: UUID = Field(..., description="Идентификатор пачки")
    lot_id: Optional[UUID] = Field(None, description="Идентификатор лота (если уже создан)")
    display_title: str = Field(..., description="Марка/модель из Fast Header OCR или имя файла", examples=["Subaru Forester #5190"])
    status: ItemProcessingStatus = Field(..., description="Статус элемента")
    current_step: TaskStep = Field(..., description="Текущий шаг конвейера")

class InProgressSummary(StrictBaseModel):
    active_batches_count: int = Field(..., ge=0, description="Число активных пачек")
    total_processing_lots: int = Field(..., ge=0, description="Количество авто в обработке (для текста '⏳ В обработке: N авто ▾', проценты не выводятся)")
    items: List[InProgressItemPreview] = Field(default_factory=list, description="Список авто в обработке для раскрывающегося аккордеона")

class PaginationMeta(StrictBaseModel):
    total_items: int = Field(..., ge=0, description="Всего записей")
    page: int = Field(..., ge=1, description="Текущая страница")
    page_size: int = Field(..., ge=1, le=100, description="Размер страницы")
    total_pages: int = Field(..., ge=0, description="Всего страниц")

class FilterCountItem(StrictBaseModel):
    value: str = Field(..., description="Значение фильтра для query param", examples=["Vezel"])
    count: int = Field(..., ge=0, description="Количество готовых лотов в ленте", examples=[4])

class AvailableFilters(StrictBaseModel):
    total_lots_count: int = Field(..., ge=0, description="Счетчик для чипса 'Все (N)' строго внутри выбранного lifecycle", examples=[12])
    archived_lots_count: int = Field(0, ge=0, description="Общее число не удаленных архивных лотов пользователя (для бейджа переключателя 'Архив (N)')", examples=[4])
    makes: List[FilterCountItem] = Field(default_factory=list, description="Марки со счетчиками внутри выбранного lifecycle для шторки '⚙️'")
    models: List[FilterCountItem] = Field(default_factory=list, description="Модели со счетчиками внутри выбранного lifecycle для чипсов ('Vezel (4)', 'Corolla (3)')")
    counts_by_verdict: Dict[TrafficLightColor, int] = Field(default_factory=dict, description="Количество по цветам светофора внутри выбранного lifecycle")

class LotListResponse(StrictBaseModel):
    items: List[LotSummary] = Field(..., description="Список готовых лотов (LIFO) без soft-deleted записей")
    in_progress: InProgressSummary = Field(..., description="Блок активных задач для выпадающей плашки в хедере")
    pagination: PaginationMeta = Field(..., description="Метаданные пагинации")
    available_filters: AvailableFilters = Field(..., description="Фильтры со счетчиками")
```

#### Бизнес-правила жизненного цикла и автоархивации:
- **Гибридный дедлайн актуальности (`expires_at`):** если распознана дата текущих торгов `auction_date`, дедлайн вычисляется как **конец дня `auction_date` в Японии (`JST, UTC+9`) + 24 часа** (т.е. `auction_date + 1 день, 23:59:59 JST`, переведённые в UTC). Если `auction_date == null` (обрезанный скан), используется fallback `created_at + 3 дня (72 часа)`.
- **Автоархивация без удаления:** при достижении `now_utc >= expires_at` активный лот (если для него не отключена автоархивация ручным возвратом) переводится в архив (`is_archived = true`, `archived_reason = "expired"`, `archived_at = expires_at`) и скрывается из дефолтного `lifecycle="active"`, оставаясь в `lifecycle="archived"` бессрочно до явного удаления пользователем.
- **Ручной возврат (Unarchive):** при возврате лота из архива через `PATCH /api/v1/lots/{lot_id}` (`{"is_archived": false}`) сервер сбрасывает `archived_at = null`, `archived_reason = null`, `expires_at = null` и отключает дальнейшую автоархивацию для этого лота, чтобы просроченный лот не возвращался в архив автоматически.
- **Повторная загрузка:** наличие архивного или удалённого (`deleted_at IS NOT NULL`) лота с тем же `frame_id` / `lot_number` не блокирует создание нового расчёта при повторном выставлении машины на торги.

#### HTTP Статус-коды:
- `200 OK` — Успешное получение ленты лотов.
- `422 Unprocessable Entity` — Ошибка валидации параметров фильтрации или пагинации.

#### Эталонный JSON-сниппет ответа (`200 OK`):
```json
{
  "items": [
    {
      "lot_id": "8fa1947b-1234-4567-8901-abcdef123456",
      "make": "Toyota",
      "model": "Corolla",
      "year": 2020,
      "engine_cc": 1196,
      "frame_id": "NRE210-2005418",
      "auction_house": "TAA",
      "lot_number": "3142",
      "overall_grade": "3.5",
      "mileage_km": 58240,
      "turnkey_cost_rub": 1104899,
      "market_price_rf_rub": 1520000,
      "verdict": "green",
      "verdict_headline": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
      "net_benefit_rub": 415101,
      "meti_sanction_risk": false,
      "has_anomaly": false,
      "anomaly_text": null,
      "thumbnail_url": "https://cdn.auction-calc.ru/lots/3142/sheet_thumb.webp",
      "auction_date": "14.11.2026",
      "is_archived": false,
      "archived_at": null,
      "archived_reason": null,
      "expires_at": "2026-11-15T14:59:59Z",
      "created_at": "2026-11-13T10:15:00Z"
    }
  ],
  "in_progress": {
    "active_batches_count": 1,
    "total_processing_lots": 4,
    "items": [
      {
        "batch_id": "4d1b8294-9876-4321-abcd-ef0123456789",
        "lot_id": "7bb2947b-0000-1111-2222-abcdef123456",
        "display_title": "Subaru Forester #5190",
        "status": "processing",
        "current_step": "farpost_parts"
      }
    ]
  },
  "pagination": {
    "total_items": 12,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  },
  "available_filters": {
    "total_lots_count": 12,
    "archived_lots_count": 4,
    "makes": [
      {"value": "Toyota", "count": 5},
      {"value": "Honda", "count": 4},
      {"value": "Nissan", "count": 3}
    ],
    "models": [
      {"value": "Vezel", "count": 4},
      {"value": "Corolla", "count": 3},
      {"value": "Note", "count": 2}
    ],
    "counts_by_verdict": {
      "green": 7,
      "yellow": 4,
      "red": 1
    }
  }
}
```

---

### Эндпоинт 5: Детальный экран лота (Табы 4, 5, 6 и Bottom Sheets)

- **Название:** Детальная спецификация лота (Full Lot Specification)
- **HTTP Метод:** `GET`
- **Путь:** `/api/v1/lots/{lot_id}`
- **Назначение в UI:** **Детальный экран лота (Официальная архитектура v3.2)**. Питает все 3 нижних таба и всплывающие шторки (Bottom Sheets):
  - **Экран 4 (Таб «Общий»):** Шапка (марка/модель, подзаголовок год·объем·пробег, кнопка `PDF`), блок светофора (вердикт + 2 буллита «Кузов» и «Салон»), плашка «Себестоимость под ключ» + капсула «Выгода: +... ₽» + «Рынок РФ (Drom) / Вложения», карточка ТТХ, а также кликабельные строки «Оригинальный аукционный лист ›» и «Сравнить с рынком на Drom.ru ›».
  - **Экран 5 (Таб «Техника»):** 2D-схема кузова с пинами (`XX`, `W1`, `A2`, `U2`) и 4-строчной легендой (`description_ru`), а также 3 нативных list-row: `Смета ремонта Farpost | 31 000 ₽ ›`, `Замечания инспектора аукциона | Перевод ›`, `Системы безопасности | В норме ›`.
  - **Экран 6 (Таб «Экономика»):** Слайдер «Максимальный бюджет / ваша ставка на аукционе», переключатель «Льготный утильсбор (личный): 5 200 ₽», 6-шаговая таблица расходов и блок сравнения с рынком РФ (`1. Рыночная цена → 2. Наша цена под ключ → 3. Чистая выгода клиента`).
  - **Экран 7 и Bottom Sheets:** Модальные шторки «Смета ремонта (Farpost)» (с форматом цен `от X ₽` и разбивкой работ СТО без прямых внешних ссылок), «Замечания инспектора» и «Системы безопасности».
- **Параметры:**

| Параметр | Расположение | Тип | Обязательный | Валидация | Описание |
| :--- | :--- | :--- | :-: | :--- | :--- |
| `lot_id` | `Path` | `UUID` | **Да** | Валидный UUIDv4 | Идентификатор лота |

#### Pydantic V2 модели Request / Response:

```python
class SafetyCheckItem(StrictBaseModel):
    system_key: Literal["structural_frame", "airbags_srs", "engine_transmission", "underbody_corrosion", "flood_or_fire"] = Field(..., description="Код проверяемой системы")
    label_ru: str = Field(..., description="Название системы для Bottom Sheet")
    status: ChecklistItemStatus = Field(..., description="Статус по данным листа")
    detail_ru: str = Field(..., description="Расшифровка строго по отметкам листа (без выдуманных дозиметрий)")

class SafetyChecklist(StrictBaseModel):
    overall_status: ChecklistItemStatus = Field(..., description="Общий статус для строки списка на Экране 5")
    overall_label_ru: str = Field(..., description="Краткий статус в строке ('В норме', 'Есть замечания', 'Стоп-фактор')", examples=["В норме"])
    items: List[SafetyCheckItem] = Field(..., description="Пункты чек-листа для Bottom Sheet «Системы безопасности»")

class LotMediaLinks(StrictBaseModel):
    sheet_thumbnail_url: str = Field(..., description="URL миниатюры скана аукционного листа")
    sheet_scan_url: str = Field(..., description="URL полного скана оригинального аукционного листа для лайтбокса")
    drom_search_url: str = Field(..., description="Ссылка на выборку сопоставимых аналогов на Drom.ru")

class EconomicsDetail(StrictBaseModel):
    bid_slider_min_jpy: int = Field(300000, description="Минимальное значение слайдера ставки на Экране 6 (JPY)")
    bid_slider_max_jpy: int = Field(2500000, description="Максимальное значение слайдера ставки на Экране 6 (JPY)")
    bid_slider_step_jpy: int = Field(10000, description="Шаг слайдера ставки (JPY)")
    is_repairs_included: bool = Field(True, description="Учтена ли смета ремонта Farpost в текущем расчете под ключ")
    customs: CustomsCalculation = Field(..., description="Таможенно-логистический расчет")
    farpost_repair: FarpostRepairSummary = Field(..., description="Смета контрактных деталей и работ СТО (Экран 5 и 7)")
    wise_cost_ladder: WiseCostLadder = Field(..., description="Прозрачная лестница затрат (Экран 6)")

class LotDetailResponse(StrictBaseModel):
    """Единая недублированная модель детального экрана лота (Табы 4, 5, 6 и Bottom Sheets)"""
    lot_id: UUID = Field(..., description="Уникальный идентификатор лота")
    created_at: datetime = Field(..., description="Время создания (UTC)")
    updated_at: datetime = Field(..., description="Время обновления (UTC)")
    is_archived: bool = Field(False, description="Находится ли лот в архиве (архивный лот остаётся полностью интерактивным)")
    archived_at: Optional[datetime] = Field(None, description="Время архивации (UTC)")
    archived_reason: Optional[LotArchiveReason] = Field(None, description="Причина архивации: expired | manual")
    expires_at: Optional[datetime] = Field(None, description="Плановый дедлайн автоархивации (UTC), null при ручном возврате из архива")
    passport: NormalizedSheet = Field(..., description="Паспорт авто, дефекты 2D-схемы, риски и заметки инспектора")
    verdict: TrafficLightVerdict = Field(..., description="Светофор, буллиты 'Кузов'/'Салон' и чистая выгода")
    market: MarketComparisonInfo = Field(..., description="Сравнение с рынком РФ (Drom.ru)")
    audit: CrossAuditReport = Field(..., description="Результат кросс-проверки истории (AucJP)")
    safety_checklist: SafetyChecklist = Field(..., description="Сводный статус и чек-лист систем безопасности")
    economics: EconomicsDetail = Field(..., description="Параметры слайдера, таможня, смета ремонта и лестница затрат")
    media: LotMediaLinks = Field(..., description="Скан оригинального листа и ссылка на Drom.ru")
```

#### HTTP Статус-коды:
- `200 OK` — Полная спецификация лота успешно сформирована (работает как для активных, так и для архивных лотов; для архивных лотов также остаются доступными `POST /recalculate` и экспорт PDF).
- `404 Not Found` — Лот не найден, принадлежит другому пользователю или был удалён (`deleted_at IS NOT NULL`).

#### Эталонный JSON-сниппет ответа (`200 OK` — Toyota Corolla Touring Лот #3142):
```json
{
  "lot_id": "8fa1947b-1234-4567-8901-abcdef123456",
  "created_at": "2026-11-13T10:15:00Z",
  "updated_at": "2026-11-13T10:15:00Z",
  "is_archived": false,
  "archived_at": null,
  "archived_reason": null,
  "expires_at": "2026-11-15T14:59:59Z",
  "passport": {
    "lot_number": "3142",
    "auction_house": "TAA",
    "auction_branch": "TAA Chubu",
    "auction_date": "14.11.2026",
    "auction_strictness_index": 1.0,
    "make": "Toyota",
    "model": "Corolla Touring",
    "trim": "W×B",
    "model_code": "3BA-NRE210W",
    "chassis_number": "NRE210-2005418",
    "frame_id": "NRE210-2005418",
    "frame_id_confidence": "exact",
    "first_reg_year": 2020,
    "first_reg_month": 10,
    "first_reg_date_str": "10.2020 (3-5 лет, ЕАЭС)",
    "is_pass_corridor_3_5": true,
    "engine_cc": 1196,
    "power_hp": 116,
    "power_hp_source": "drom_catalog",
    "is_under_160_hp": true,
    "mileage_km": 58240,
    "odometer_status": "confirmed",
    "transmission": "6MT",
    "drive_type": "2WD",
    "fuel_type": "gasoline",
    "color_ru": "Белый перламутр",
    "paint_code": "070",
    "overall_grade": "3.5",
    "exterior_grade": "C",
    "interior_grade": "B",
    "shaken_until": null,
    "recycling_fee_yen": 11400,
    "recycling_fee_paid": true,
    "equipment_ru": [
      "Климат-контроль",
      "Светодиодная LED-оптика",
      "Литые диски R17",
      "Круиз-контроль",
      "Электростеклоподъемники",
      "Toyota Safety Sense (TSS)"
    ],
    "defects": [
      {
        "panel_id": "front_left_door",
        "panel_ru": "Передняя левая дверь",
        "defect_types": ["XX"],
        "severity": null,
        "raw_code": "XX",
        "description_ru": "Передняя левая дверь — замена (в цвет 070)"
      },
      {
        "panel_id": "front_left_fender",
        "panel_ru": "Арка переднего крыла",
        "defect_types": ["A"],
        "severity": 2,
        "raw_code": "A2",
        "description_ru": "Арка переднего крыла — царапина до 10 см"
      },
      {
        "panel_id": "left_sill",
        "panel_ru": "Левый порог",
        "defect_types": ["U"],
        "severity": 2,
        "raw_code": "U2",
        "description_ru": "Порог — мелкая вмятина (PDR без покраски)"
      },
      {
        "panel_id": "rear_left_door",
        "panel_ru": "Задняя левая дверь",
        "defect_types": ["W"],
        "severity": 1,
        "raw_code": "W1",
        "description_ru": "Задняя левая дверь — вторичный заводской окрас"
      }
    ],
    "risk_flags": {
      "is_flooded": false,
      "airbag_deployed": false,
      "hail_damage": false,
      "underbody_rust": false,
      "underbody_corrosion": false,
      "core_support_repair": false,
      "pillar_or_frame_repair": false,
      "panel_replaced_xx": true,
      "panel_needs_replacement_x": false,
      "odometer_issue": false,
      "color_changed": false,
      "windshield_damage": false,
      "repaired_grade_r_ra": false
    },
    "inspector_notes_ru": [
      "Царапина A2 на арке переднего крыла, вмятина U2 на пороге",
      "Заменена передняя левая дверь (XX), вторичный окрас задней двери W1 без шпаклевки",
      "Салон чистый, без прокуров, естественные следы эксплуатации (оценка B)",
      "Силовой каркас, лонжероны и геометрия в норме"
    ],
    "inspector_notes_raw": [
      "左Fドア交換(XX) / 左Rドア再塗装(W1)",
      "下廻り異常なし・室内に気になる臭いなし"
    ],
    "seller_comments_ru": [
      "Один владелец, сервисная книжка в наличии"
    ],
    "extra_ru": [],
    "ocr_warnings": [],
    "low_confidence_fields": []
  },
  "verdict": {
    "verdict": "green",
    "headline": "РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "short_verdict_label": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "badge_text": "Выгода: +415 101 ₽",
    "net_benefit_rub": 415101,
    "benefit_percentage": 37.6,
    "body_summary_ru": "Кузов (оценка C): замена левой двери (XX), деталь найдена на Farpost в цвет за от 18 000 ₽.",
    "interior_summary_ru": "Салон (оценка B): чистый, без прокуров, мелкие естественные следы эксплуатации.",
    "reasoning_bullets": [
      "Строгий аукцион TAA Chubu: оценка 3.5 C/B, родной пробег 58 240 км",
      "Несущий каркас и подушки SRS целы, повреждены только навесные панели",
      "Льготный утильсбор (5 200 ₽) и проходной коридор ЕАЭС 3-5 лет"
    ]
  },
  "market": {
    "market_price_rf_rub": 1520000,
    "analogs_count": 14,
    "price_min_rub": 1390000,
    "price_max_rub": 1680000,
    "search_region_ru": "ДФО / Владивосток",
    "excludes_under_order": true,
    "filtered_out_under_order_count": 6,
    "is_fallback": false,
    "fallback_reason_ru": null,
    "drom_search_url": "https://vladivostok.drom.ru/toyota/corolla_touring/year-2020/engine-1.2/manual/"
  },
  "audit": {
    "status": "clean",
    "source_name": "AucJP + AAA Japan / Pravto",
    "is_archive_available": true,
    "risk_level": "CLEAN",
    "has_critical_anomaly": false,
    "headline_ru": "Аудит истории торгов: нарушений по Frame ID не обнаружено",
    "times_auctioned": 1,
    "verified_at": "2026-11-13T10:15:00Z",
    "anomalies": [],
    "history": [
      {
        "auction_date": "12.11.2026",
        "auction_house": "TAA Chubu",
        "auction_strictness": 1.0,
        "lot_number": "3142",
        "overall_grade": "3.5",
        "mileage_km": 58240,
        "defects_summary": "Замена двери XX, окрас задней двери W1, царапина A2",
        "closing_price_jpy": 1060000,
        "sheet_archive_url": null
      }
    ]
  },
  "safety_checklist": {
    "overall_status": "ok",
    "overall_label_ru": "В норме",
    "items": [
      {
        "system_key": "structural_frame",
        "label_ru": "Силовой каркас и лонжероны",
        "status": "ok",
        "detail_ru": "Нарушений геометрии, ремонта стоек и рамки радиатора на листе не отмечено"
      },
      {
        "system_key": "airbags_srs",
        "label_ru": "Подушки безопасности (SRS)",
        "status": "ok",
        "detail_ru": "Отметок о срабатывании или отсутствии подушек нет"
      },
      {
        "system_key": "engine_transmission",
        "label_ru": "ДВС и трансмиссия",
        "status": "ok",
        "detail_ru": "Замечаний инспектора по работе 1.2T и 6MT в бланке нет"
      },
      {
        "system_key": "underbody_corrosion",
        "label_ru": "Днище и пороги",
        "status": "ok",
        "detail_ru": "Сквозная коррозия не отмечена"
      },
      {
        "system_key": "flood_or_fire",
        "label_ru": "Следы затопления / пожара / града",
        "status": "ok",
        "detail_ru": "Стоп-факторов в бланке не зафиксировано"
      }
    ]
  },
  "economics": {
    "bid_slider_min_jpy": 300000,
    "bid_slider_max_jpy": 2500000,
    "bid_slider_step_jpy": 10000,
    "is_repairs_included": true,
    "customs": {
      "age_corridor": "3_to_5_years",
      "duty_calculation_mode": "eur_per_cc",
      "engine_cc": 1196,
      "duty_rate_eur_per_cc": 1.7,
      "effective_duty_pct": null,
      "customs_duty_eur": 2033.2,
      "customs_duty_rub": 193154,
      "excise_rub": 0,
      "import_vat_rub": 0,
      "is_under_160_hp": true,
      "is_commercial_util": false,
      "utilization_fee_rub": 5200,
      "customs_clearance_fee_rub": 3120,
      "freight_vladivostok_rub": 97750,
      "broker_svh_sbkts_rub": 99000,
      "meti_sanction_risk": false,
      "rates_snapshot": {
        "jpy_rub_bank": 0.585,
        "jpy_rate_source": "ДВ-банк (ориентир)",
        "eur_rub_cbrf": 95.0,
        "usd_rub_cbrf": 85.0,
        "cbrf_date": "12.11.2026"
      }
    },
    "farpost_repair": {
      "parts": [
        {
          "panel_id": "front_left_door",
          "defect_code": "XX",
          "part_name_ru": "Передняя левая дверь",
          "subtitle_ru": "контрактная деталь в заводской цвет 070",
          "price_from_rub": 18000,
          "in_stock_vladivostok": true,
          "is_statistical_fallback": false
        }
      ],
      "service_works": [
        {
          "work_type": "mount_dismount",
          "label_ru": "Снятие и монтаж двери",
          "amount_rub": 4000,
          "zero_cost_reason_ru": null
        },
        {
          "work_type": "paint",
          "label_ru": "Покраска двери (в цвет 070)",
          "amount_rub": 0,
          "zero_cost_reason_ru": "не требуется"
        },
        {
          "work_type": "pdr_and_polish",
          "label_ru": "PDR удаление вмятины + полировка",
          "amount_rub": 9000,
          "zero_cost_reason_ru": null
        }
      ],
      "total_parts_from_rub": 18000,
      "total_works_rub": 13000,
      "grand_total_repair_rub": 31000,
      "has_color_matched_parts": true,
      "included_in_turnkey_hint_ru": "Сумма уже включена в расчёт под ключ"
    },
    "wise_cost_ladder": {
      "car_bid_jpy": 1060000,
      "car_bid_rub": 620100,
      "turnkey_cost_rub": 1104899,
      "market_price_rf_rub": 1520000,
      "net_benefit_rub": 415101,
      "benefit_percentage": 37.6,
      "steps": [
        {
          "step_number": 1,
          "name_ru": "Ставка на аукционе",
          "amount_rub": 620100,
          "original_currency": "JPY",
          "original_amount": 1060000.0,
          "is_optional": false
        },
        {
          "step_number": 2,
          "name_ru": "Расходы в Японии (FOB и сбор)",
          "amount_rub": 55575,
          "original_currency": "JPY",
          "original_amount": 95000.0,
          "is_optional": false
        },
        {
          "step_number": 3,
          "name_ru": "Фрахт Тояма-ВЛК",
          "amount_rub": 97750,
          "original_currency": "USD",
          "original_amount": 1150.0,
          "is_optional": false
        },
        {
          "step_number": 4,
          "name_ru": "Таможенная пошлина ЕАЭС и сбор",
          "amount_rub": 196274,
          "original_currency": "EUR",
          "original_amount": 2033.2,
          "is_optional": false
        },
        {
          "step_number": 5,
          "name_ru": "Утилизационный сбор РФ",
          "amount_rub": 5200,
          "original_currency": "RUB",
          "original_amount": 5200.0,
          "is_optional": false
        },
        {
          "step_number": 6,
          "name_ru": "СВХ, брокер, СБКТС, ЭПТС",
          "amount_rub": 99000,
          "original_currency": "RUB",
          "original_amount": 99000.0,
          "is_optional": false
        },
        {
          "step_number": 7,
          "name_ru": "Запчасти Farpost и ремонт",
          "amount_rub": 31000,
          "original_currency": "RUB",
          "original_amount": 31000.0,
          "is_optional": true
        }
      ]
    }
  },
  "media": {
    "sheet_thumbnail_url": "https://cdn.auction-calc.ru/lots/3142/sheet_thumb.webp",
    "sheet_scan_url": "https://cdn.auction-calc.ru/lots/3142/taa_sheet_original.jpg",
    "drom_search_url": "https://vladivostok.drom.ru/toyota/corolla_touring/year-2020/engine-1.2/manual/"
  }
}
```

---

### Эндпоинт 6: Интерактивный пересчет ставки и утильсбора (Таб «Экономика»)

- **Название:** Симуляция ставки и параметров импорта (Recalculate Economics)
- **HTTP Метод:** `POST`
- **Путь:** `/api/v1/lots/{lot_id}/recalculate`
- **Назначение в UI:** **Экран 6 (Таб «Экономика»)**. Вызывается при изменении максимальной ставки (слайдер или прямой ввод суммы в ₽/¥) и переключателя утильсбора РФ (`Льготный утильсбор (личный): 5 200 ₽` vs коммерческий по таблице `ПП РФ № 1255`), а также опционального тоггла сметы ремонта.
  - На клиенте для авто возрастом **3–5 и 5+ лет** (пошлина зависит только от см³) движение слайдера отрабатывает за **0 мс** линейным сдвигом `ΔBid_JPY * JPY_RUB`.
  - Для авто **до 3 лет** (`duty_calculation_mode == "pct_of_value"`, пошлина 48–54% от цены) клиент делает мгновенную оценку и пересчитывается на бэкенде.
  - При отпускании ползунка (дебаунс 300 мс) клиент всегда запрашивает сервер для верификации пошлины, утильсбора, выгоды и обновления светофора.
- **Параметры:**

| Параметр | Расположение | Тип | Обязательный | Валидация | Описание |
| :--- | :--- | :--- | :-: | :--- | :--- |
| `lot_id` | `Path` | `UUID` | **Да** | UUIDv4 | Идентификатор лота |
| `bid_jpy` | `Body` | `Optional[int]` | Нет | 100 000 <= bid <= 50 000 000 | Новая ставка в иенах (нельзя передавать одновременно с `bid_rub`) |
| `bid_rub` | `Body` | `Optional[int]` | Нет | 50 000 <= bid <= 50 000 000 | Альтернативный прямой ввод ставки в рублях |
| `is_commercial_util` | `Body` | `bool` | Нет | Дефолт `False` | `True` = коммерческий утильсбор по сетке ПП РФ № 1255 |
| `include_repairs` | `Body` | `bool` | Нет | Дефолт `True` | Включать ли смету ремонта Farpost в себестоимость |
| `custom_freight_rub` | `Body` | `Optional[int]`| Нет | >= 0 | Корректировка ставки фрахта при необходимости |

#### Pydantic V2 модели Request / Response:

```python
class RecalculateRequest(StrictBaseModel):
    bid_jpy: Optional[int] = Field(None, ge=100000, le=50000000, description="Новая ставка на аукционе в JPY", examples=[850000])
    bid_rub: Optional[int] = Field(None, ge=50000, le=50000000, description="Альтернативный прямой ввод ставки в рублях", examples=[545700])
    is_commercial_util: bool = Field(False, description="Переключатель утильсбора: False=Личный льготный, True=Коммерческий (ПП РФ № 1255)")
    include_repairs: bool = Field(True, description="Включать ли смету ремонта Farpost в себестоимость")
    custom_power_hp: Optional[int] = Field(None, ge=1, le=2000, description="Ручное переопределение мощности в л.с. (если каталог Drom не определил точный гибрид/комплектацию)")
    custom_freight_rub: Optional[int] = Field(None, ge=0, description="Кастомная стоимость фрахта")

    @model_validator(mode="after")
    def validate_exclusive_bid_currency(self) -> "RecalculateRequest":
        if self.bid_jpy is not None and self.bid_rub is not None:
            raise ValueError("Укажите либо 'bid_jpy', либо 'bid_rub', но не оба поля одновременно")
        return self

class RecalculateResponse(StrictBaseModel):
    lot_id: UUID = Field(..., description="Идентификатор лота")
    recalculated_at: datetime = Field(..., description="Время пересчета (UTC)")
    applied_bid_jpy: int = Field(..., description="Примененная ставка в иенах", examples=[850000])
    applied_bid_rub: int = Field(..., description="Примененная ставка в рублях", examples=[545700])
    is_commercial_util: bool = Field(..., description="Примененный режим утильсбора")
    include_repairs: bool = Field(..., description="Учтена ли смета ремонта")
    customs: CustomsCalculation = Field(..., description="Обновленный таможенный расчет")
    wise_cost_ladder: WiseCostLadder = Field(..., description="Обновленная лестница себестоимости")
    turnkey_cost_rub: int = Field(..., description="Обновленная себестоимость под ключ", examples=[1149839])
    market_price_rf_rub: int = Field(..., description="Рыночная цена в РФ", examples=[1520000])
    net_benefit_rub: int = Field(..., description="Обновленная чистая выгода", examples=[370161])
    benefit_percentage: float = Field(..., description="Обновленный процент выгоды", examples=[32.2])
    verdict: TrafficLightVerdict = Field(..., description="Обновленный вердикт светофора")
    pdf_report_stale: bool = Field(True, description="Флаг того, что для экспорта PDF нужно передать параметры симуляции")
```

#### HTTP Статус-коды:
- `200 OK` — Успешный пересчет себестоимости.
- `400 Bad Request` — Переданы взаимоисключающие параметры или некорректная ставка.
- `404 Not Found` — Лот не найден.

#### Эталонный JSON-сниппет ответа (`200 OK` — ставка увеличена до 1 150 000 ¥):
```json
{
  "lot_id": "8fa1947b-1234-4567-8901-abcdef123456",
  "recalculated_at": "2026-11-13T10:15:00Z",
  "applied_bid_jpy": 1150000,
  "applied_bid_rub": 672750,
  "is_commercial_util": false,
  "include_repairs": true,
  "customs": {
    "age_corridor": "3_to_5_years",
    "duty_calculation_mode": "eur_per_cc",
    "engine_cc": 1196,
    "duty_rate_eur_per_cc": 1.7,
    "effective_duty_pct": null,
    "customs_duty_eur": 2033.2,
    "customs_duty_rub": 193154,
    "excise_rub": 0,
    "import_vat_rub": 0,
    "is_under_160_hp": true,
    "is_commercial_util": false,
    "utilization_fee_rub": 5200,
    "customs_clearance_fee_rub": 3120,
    "freight_vladivostok_rub": 97750,
    "broker_svh_sbkts_rub": 99000,
    "meti_sanction_risk": false,
    "rates_snapshot": {
      "jpy_rub_bank": 0.585,
      "jpy_rate_source": "ДВ-банк (ориентир)",
      "eur_rub_cbrf": 95.0,
      "usd_rub_cbrf": 85.0,
      "cbrf_date": "12.11.2026"
    }
  },
  "wise_cost_ladder": {
    "car_bid_jpy": 1150000,
    "car_bid_rub": 672750,
    "turnkey_cost_rub": 1157549,
    "market_price_rf_rub": 1520000,
    "net_benefit_rub": 362451,
    "benefit_percentage": 31.3,
    "steps": [
      {
        "step_number": 1,
        "name_ru": "Ставка на аукционе",
        "amount_rub": 672750,
        "original_currency": "JPY",
        "original_amount": 1150000.0,
        "is_optional": false
      },
      {
        "step_number": 2,
        "name_ru": "Расходы в Японии (FOB и сбор)",
        "amount_rub": 55575,
        "original_currency": "JPY",
        "original_amount": 95000.0,
        "is_optional": false
      },
      {
        "step_number": 3,
        "name_ru": "Фрахт Тояма-ВЛК",
        "amount_rub": 97750,
        "original_currency": "USD",
        "original_amount": 1150.0,
        "is_optional": false
      },
      {
        "step_number": 4,
        "name_ru": "Таможенная пошлина ЕАЭС и сбор",
        "amount_rub": 196274,
        "original_currency": "EUR",
        "original_amount": 2033.2,
        "is_optional": false
      },
      {
        "step_number": 5,
        "name_ru": "Утилизационный сбор РФ",
        "amount_rub": 5200,
        "original_currency": "RUB",
        "original_amount": 5200.0,
        "is_optional": false
      },
      {
        "step_number": 6,
        "name_ru": "СВХ, брокер, СБКТС, ЭПТС",
        "amount_rub": 99000,
        "original_currency": "RUB",
        "original_amount": 99000.0,
        "is_optional": false
      },
      {
        "step_number": 7,
        "name_ru": "Запчасти Farpost и ремонт",
        "amount_rub": 31000,
        "original_currency": "RUB",
        "original_amount": 31000.0,
        "is_optional": true
      }
    ]
  },
  "turnkey_cost_rub": 1157549,
  "market_price_rf_rub": 1520000,
  "net_benefit_rub": 362451,
  "benefit_percentage": 31.3,
  "verdict": {
    "verdict": "green",
    "headline": "РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "short_verdict_label": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "badge_text": "Выгода: +362 451 ₽",
    "net_benefit_rub": 362451,
    "benefit_percentage": 31.3,
    "body_summary_ru": "Кузов (оценка C): замена левой двери (XX), деталь найдена на Farpost в цвет за от 18 000 ₽.",
    "interior_summary_ru": "Салон (оценка B): чистый, без прокуров, мелкие естественные следы эксплуатации.",
    "reasoning_bullets": [
      "Строгий аукцион TAA Chubu: оценка 3.5 C/B, родной пробег 58 240 км",
      "Выгода под ключ при ставке 1 150 000 ¥ составляет +362 451 ₽ (31.3%)",
      "Льготный утильсбор (5 200 ₽) и проходной коридор ЕАЭС 3-5 лет"
    ]
  },
  "pdf_report_stale": true
}
```

---

### Эндпоинт 7 [P1 — Post-MVP]: Серверный экспорт PDF-отчета

> [!NOTE]
> **Решение для MVP:** Кнопка `[PDF]` на Экранах 4–6 в первой версии формирует отчёт **на клиенте (Frontend)**: рендерится печатная HTML-версия отчёта из уже загруженных данных `LotDetailResponse` + активной симуляции Экрана 6 и сохраняется через `window.print()` (`@media print`) или `html2pdf`. Серверный эндпоинт ниже вынесен в **P1**.

- **Название:** Экспорт PDF-отчета дефектоскопии и расчета (Export PDF Report)
- **HTTP Метод:** `GET`
- **Путь:** `/api/v1/lots/{lot_id}/report.pdf`
- **Назначение в UI:** **Кнопка `PDF` в правом верхнем углу шапки (на всех табах 4, 5, 6)**. Формирует PDF-документ с логотипом AuctionCalc, расшифровкой дефектов, чек-листом систем безопасности, сметой ремонта и таблицей расходов — **строго под текущую симуляцию ставки и утильсбора** с Экрана 6.
- **Параметры:**

| Параметр | Расположение | Тип | Обязательный | Дефолт | Описание |
| :--- | :--- | :--- | :-: | :--- | :--- |
| `lot_id` | `Path` | `UUID` | **Да** | — | Идентификатор лота |
| `bid_jpy` | `Query` | `Optional[int]` | Нет | `None` | Активная ставка с Экрана 6 (если `null`, берется базовая ставка лота) |
| `is_commercial_util` | `Query` | `Optional[bool]` | Нет | `False` | Активный переключатель утильсбора с Экрана 6 |
| `include_repairs` | `Query` | `Optional[bool]` | Нет | `True` | Включать ли смету ремонта в расчет под ключ в PDF |
| `locale` | `Query` | `str` | Нет | `"ru"` | Язык отчета (`ru`, `en`) |
| `branding` | `Query` | `str` | Нет | `"auction_calc"` | Шаблон оформления: `auction_calc`, `white_label`, `neutral` |
| `include_farpost_estimate` | `Query` | `bool` | Нет | `True` | Включать страницу со сметой ремонта Farpost |
| `include_auction_scan` | `Query` | `bool` | Нет | `True` | Включать скан оригинального листа с печатями |

#### HTTP Заголовки ответа:
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="AuctionCalc_Report_Lot_3142_Toyota_Corolla_Touring.pdf"`
- `Cache-Control: private, no-store`

#### HTTP Статус-коды:
- `200 OK` — Бинарный поток PDF-файла.
- `404 Not Found` — Лот не найден.
- `409 Conflict` — Обработка лота в конвейере еще не завершена (`status != ready`).

---

### Эндпоинт 8: Ручная архивация и возврат лота из архива

- **Название:** Обновление жизненного цикла лота (Archive / Unarchive Lot)
- **HTTP Метод:** `PATCH`
- **Путь:** `/api/v1/lots/{lot_id}`
- **Назначение в UI:** Перевод неактуального лота в «Архив» или ручной возврат архивного лота в «Активные» с карточки на главном экране или из шапки детального экрана. При возврате из архива (`is_archived = false`) бэкенд сбрасывает `archived_at` / `archived_reason` / `expires_at` в `null` и отключает дальнейшую автоархивацию для этого лота.
- **Параметры:** `lot_id: UUID` (`Path`, обязательный).

#### Pydantic V2 модели Request / Response:

```python
class LotLifecyclePatchRequest(StrictBaseModel):
    is_archived: bool = Field(..., description="true — отправить в архив вручную (archived_reason='manual'); false — вернуть в активную ленту и отключить автоархивацию")
```

- **Ответ (`200 OK`):** Возвращает актуализированную модель `LotSummary`.

#### HTTP Статус-коды:
- `200 OK` — Статус жизненного цикла лота обновлён.
- `404 Not Found` — Лот не найден, принадлежит другому пользователю или уже удалён.
- `422 Unprocessable Entity` — Некорректное тело запроса.

---

### Эндпоинт 9: Удаление одного ненужного лота

- **Название:** Удаление лота (Soft-Delete Lot)
- **HTTP Метод:** `DELETE`
- **Путь:** `/api/v1/lots/{lot_id}`
- **Назначение в UI:** Удаление красного, дублирующего или ошибочно загруженного лота из карточки на Экране 1 (без отдельной «Корзины» в UI; клиент может показывать Undo-тост 4–5 сек перед отправкой или выполнять немедленное удаление с коротким подтверждением в шапке детального экрана).
- **Поведение на сервере:** Выполняется **soft-delete** (`deleted_at = now_utc`) с проверкой владельца (`user_id`). Удалённый лот исключается из `GET /api/v1/lots` и пересчёта `AvailableFilters`, при прямом обращении к `GET / PATCH / POST recalculate / DELETE` возвращает `404 Not Found`, а в `BatchProgressResponse.items` связанные `lot_id` и `summary` становятся `null`, исключая битые ссылки в истории пачек.
- **Параметры:** `lot_id: UUID` (`Path`, обязательный).

#### HTTP Статус-коды:
- `204 No Content` — Лот успешно удалён (тело ответа пустое).
- `404 Not Found` — Лот не найден, принадлежит другому пользователю или уже был удалён.

---

### Эндпоинт 10: Массовое удаление ненужных лотов

- **Название:** Батчевое удаление лотов (Bulk Soft-Delete Lots)
- **HTTP Метод:** `POST`
- **Путь:** `/api/v1/lots/bulk-delete`
- **Назначение в UI:** Массовая очистка ленты или архива (мультивыбор карточек / быстрая зачистка ненужных лотов после пачки).
- **Поведение на сервере:** Идемпотентно помечает как `deleted_at = now_utc` все активные/архивные (не удалённые ранее) лоты из списка `lot_ids`, принадлежащие текущему `user_id`. Записи, которые уже удалены, не существуют или принадлежат другому пользователю, возвращаются в `not_found_ids` без падения всего запроса.

#### Pydantic V2 модели Request / Response:

```python
class LotBulkDeleteRequest(StrictBaseModel):
    lot_ids: List[UUID] = Field(..., min_length=1, max_length=100, description="Список UUID лотов к удалению (от 1 до 100 за запрос)")

class LotBulkDeleteResponse(StrictBaseModel):
    deleted_ids: List[UUID] = Field(..., description="UUID лотов, успешно переведенных в deleted состояние этим запросом")
    not_found_ids: List[UUID] = Field(default_factory=list, description="UUID из запроса, которые не найдены, уже удалены или недоступны пользователю")
    deleted_count: int = Field(..., ge=0, description="Количество реально удалённых лотов (len(deleted_ids))")
```

#### HTTP Статус-коды:
- `200 OK` — Запрос обработан (`LotBulkDeleteResponse`).
- `422 Unprocessable Entity` — Пустой массив `lot_ids`, невалидный UUID или превышен лимит `100` элементов.

---

## 5. Стандарт обработки ошибок (RFC 7807 Problem Details)

Все ошибки бэкенда возвращаются строго в соответствии со стандартом **RFC 7807 (Problem Details for HTTP APIs)**:

```python
class InvalidParamDetail(StrictBaseModel):
    name: str = Field(..., description="Имя ошибочного поля или заголовка", examples=["files[0]"])
    reason: str = Field(..., description="Причина отклонения валидации", examples=["Файл превышает допустимый размер 15 МБ"])

class ProblemDetail(StrictBaseModel):
    type: str = Field("about:blank", description="URI идентификатор типа ошибки")
    title: str = Field(..., description="Краткое название ошибки на понятном языке")
    status: int = Field(..., description="HTTP статус-код (400, 404, 422, 500)")
    detail: str = Field(..., description="Подробное человекочитаемое разъяснение проблемы")
    instance: Optional[str] = Field(None, description="URI эндпоинта, вызвавшего ошибку")
    invalid_params: List[InvalidParamDetail] = Field(default_factory=list, description="Список полей с ошибками")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Время фиксации сбоя (UTC)")
```

### Примеры ответов при ошибках:

#### 1. Ошибка загрузки неподдерживаемого файла (`400 Bad Request`):
```json
{
  "type": "https://api.auction-calc.ru/errors/unsupported-media-type",
  "title": "Неподдерживаемый формат файла",
  "status": 400,
  "detail": "Загруженный файл 'doc_scan.pdf' не является изображением допустимого формата (допускаются JPEG, PNG, WEBP, HEIC/HEIF)",
  "instance": "/api/v1/lots/batches",
  "invalid_params": [
    {
      "name": "files[1]",
      "reason": "MIME-тип 'application/pdf' не поддерживается"
    }
  ],
  "timestamp": "2026-11-13T10:15:00Z"
}
```

#### 2. Ошибка валидации параметров запроса (`422 Unprocessable Entity`):
```json
{
  "type": "https://api.auction-calc.ru/errors/validation-error",
  "title": "Ошибка валидации параметров",
  "status": 422,
  "detail": "Значение ставки bid_jpy должно находиться в диапазоне от 100 000 до 50 000 000 иен",
  "instance": "/api/v1/lots/8fa1947b-1234-4567-8901-abcdef123456/recalculate",
  "invalid_params": [
    {
      "name": "bid_jpy",
      "reason": "Значение 50000 меньше минимального порога 100000"
    }
  ],
  "timestamp": "2026-11-13T10:15:00Z"
}
```

---

## 6. Сквозная матрица маппинга полей и контрактов на UI экраны 1–7 (v3.2 Official)

| № | Экран UI (v3.2) | Компонент интерфейса | Технический ключ контракта | Тип данных | Отображение в UI (Бенчмарк Corolla Touring) |
| :-: | :--- | :--- | :--- | :--- | :--- |
| **0** | **Экран 0: Auth** | Вход / Регистрация | `POST /auth/login`, `/register`, `/refresh` | `JWT Bearer` | Авторизация, токен в `Authorization: Bearer ...` |
| **1** | **Экран 1: Дашборд** | Поиск и фильтры `⚙️` | `query`, `lifecycle`, `AvailableFilters.makes` | `string` / `FilterCountItem[]` | Поиск по кузову + счетчики марок |
| **1** | **Экран 1: Дашборд** | Вкладки «Активные / Архив» | `lifecycle=active\|archived`, `archived_lots_count` | `enum` / `int` | Переключатель `Активные` / `Архив (4)` |
| **1** | **Экран 1: Дашборд** | Очистка / архив карточки | `PATCH /lots/{id}`, `DELETE /lots/{id}`, `POST /lots/bulk-delete` | `endpoint` | Архивация, Undo-удаление карточки и массовая очистка |
| **1** | **Экран 1: Дашборд** | Чипсы моделей | `AvailableFilters.total_lots_count`, `models` | `int` / `FilterCountItem[]` | `Все (12)`, `Vezel (4)`, `Corolla (3)`, `Note (2)` |
| **1** | **Экран 1: Дашборд** | Плашка «⏳ В обработке ▾» | `LotListResponse.in_progress` | `InProgressSummary` | «⏳ В обработке: 4 авто ▾» (без `%`, аккордеон со списком) |
| **1** | **Экран 1: Дашборд** | Карточка: Миниатюра | `LotSummary.thumbnail_url` | `string?` | Миниатюра оригинального скана аукционного листа |
| **1** | **Экран 1: Дашборд** | Карточка: Паспорт и цена | `make`, `model`, `year`, `frame_id`, `turnkey_cost_rub` | `various` | `Toyota Corolla 2020 • TAA 3.5` / `Под ключ: 1 104 899 ₽` |
| **1** | **Экран 1: Дашборд** | Карточка: Вердикт | `verdict_headline`, `meti_sanction_risk` | `string / bool` | `🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ` / `🟡 ВНИМАНИЕ: СКОЛЫ A2/U2` |
| **2** | **Экран 2: Модалка** | Выбор файлов | `POST /batches: files[]` | `binary[]` | 1..10 фото/сканов (`JPEG/PNG/WEBP/HEIC`) |
| **3** | **Экран 3: Очередь** | Маскот 🤖 | `BatchProgressResponse.mascot` | `MascotState` | Робот 🤖 + «Распознаем лоты... 3/4» |
| **3** | **Экран 3: Очередь** | Строка в обработке | `BatchItemStatus.preview_title` | `string?` | «⏳ Subaru Forester #5190» (из Fast Header OCR) |
| **3** | **Экран 3: Очередь** | Кнопка догрузки | `POST /batches/{id}/items` | `endpoint` | «Догрузить еще листы» без сброса очереди |
| **4** | **Экран 4: Таб «Общий»** | Хедер, архив, удаление и PDF | `is_archived`, `PATCH /lots/{id}`, `DELETE /lots/{id}`, Client Print/PDF | `bool` / `endpoint` | `Toyota Corolla Touring` + бейдж архива + `[В архив / Удалить / PDF]` |
| **4** | **Экран 4: Таб «Общий»** | Светофор + 2 буллита | `verdict.headline`, `body_summary_ru`, `interior_summary_ru` | `string` | Зелёная/жёлтая/красная плашка + «Кузов» + «Салон» |
| **4** | **Экран 4: Таб «Общий»** | Выгода под ключ | `wise_cost_ladder.turnkey_cost_rub`, `verdict.badge_text`, `market` | `int / string` | `1 104 899 ₽` + `Выгода: +415 101 ₽` + Рынок / Вложения |
| **4** | **Экран 4: Таб «Общий»** | Карточка ТТХ | `passport` (`frame_id`, `first_reg_date_str`, `engine_cc`, `transmission`, `mileage_km`, `overall_grade`) | `various` | Аккуратная двухколоночная сетка ТТХ |
| **4** | **Экран 4: Таб «Общий»** | Ссылки внизу | `media.sheet_scan_url`, `market.drom_search_url`, `market.analogs_count` | `url / int` | `Оригинальный аукционный лист ›` + `Сравнить с рынком на Drom.ru ›` |
| **5** | **Экран 5: Таб «Техника»** | 2D-схема и легенда | `passport.defects[]` (`panel_id`, `raw_code`, `description_ru`) | `array` | Пины `[XX]`, `[W1]`, `[A2]`, `[U2]` + 4 строки легенды |
| **5** | **Экран 5: Таб «Техника»** | 3 строки списка | `economics.farpost_repair`, `passport.inspector_notes_ru`, `safety_checklist.overall_label_ru` | `various` | `Смета ремонта Farpost | 31 000 ₽ ›`, `Замечания | Перевод ›`, `Безопасность | В норме ›` |
| **6** | **Экран 6: Таб «Экономика»** | Слайдер и утильсбор | `bid_slider_*`, `wise_cost_ladder.car_bid_jpy`, `is_commercial_util`, `POST .../recalculate` | `various` | `1 060 000 ¥ (~620 100 ₽)` + свитч `Льготный утильсбор (личный): 5 200 ₽` |
| **6** | **Экран 6: Таб «Экономика»** | Лестница и сравнение | `wise_cost_ladder.steps[]`, `market.market_price_rf_rub`, `net_benefit_rub` | `array / int` | 7 статей расходов + `1.52M → 1.10M → +415 101 ₽ (37.6%)` |
| **7** | **Экран 7: Bottom Sheet** | Смета ремонта Farpost | `farpost_repair.parts[]` (`price_from_rub`), `service_works[]` | `object` | `Передняя левая дверь — от 18 000 ₽` + работы СТО (без прямых ссылок) |

---

## 7. Тестовый контур и правила валидации контрактов

Для обеспечения 100% стабильности в CI/CD пайплайне настроена обязательная автоматическая проверка:

```bash
# 1. Валидация типов Pydantic V2 и сериализации
python3 -m pytest tests/test_pydantic_contracts.py -v

# 2. Проверка соответствия эталонного бенчмарка Corolla Touring NRE210
python3 -m pytest tests/test_benchmark_corolla.py -v

# 3. Валидация синтаксиса OpenAPI 3.1 и перекрестных ссылок
openapi-spec-validator docs/openapi.yaml
```

Все дата-контракты полностью зафиксированы и служат каноническим фундаментом для бэкенда FastAPI и клиентского приложения.
