from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domains.entities import (
    RawDefectEntity,
    RawExtractionEntity,
    RawRiskFlagsEntity,
)
from app.domains.enums import (
    BodyPanel,
    DriveType,
    FuelType,
    OdometerStatus,
)


class FastHeaderPreviewSchema(BaseModel):
    """Lightweight top-header preview extracted rapidly for batch progress UI."""

    make_en: str | None = None
    model_en: str | None = None
    lot_number: str | None = None


class DefectExtractionSchema(BaseModel):
    """Structured defect mark extracted from the vehicle body diagram."""

    visual_location: str = Field(
        description="Где на схеме кузова стоит метка (ориентация сверху по ходу движения, без зеркалирования)"
    )
    panel_id: BodyPanel
    panel_ru: str = Field(description="Название детали кузова на русском")
    raw_code: str = Field(description="Оригинальный код дефекта с листа: A1, U2, W2, XX, AU3 и т. п.")


class ExtractedRiskFlagsSchema(BaseModel):
    """Safety and structural stop-factors extracted directly by the Vision model."""

    is_flooded: bool = Field(description="Следы затопления/топляк (冠水車, 水没) — безусловный стоп-фактор")
    airbag_deployed: bool = Field(description="Сработали подушки безопасности (エアバッグ展開) — стоп-фактор")
    hail_damage: bool = Field(description="Повреждения кузова градом (ひょう害車, 雹) — стоп-фактор")
    underbody_rust: bool = Field(description="Поверхностная ржавчина по днищу/подвеске (下廻り S)")
    underbody_corrosion: bool = Field(description="Сквозная коррозия, гниение порогов/арок/днища (下廻り 腐食/C)")
    core_support_repair: bool = Field(description="Упомянут ли ремонт/замена/складка рамки радиатора (コアサポート)")
    pillar_or_frame_repair: bool = Field(
        description="Упомянут ли ремонт/окрас стоек, лонжеронов, крыши, силовой структуры (ピラー, フレーム)"
    )
    color_changed: bool = Field(description="Есть ли отметка о смене цвета (色替)")
    windshield_damage: bool = Field(description="Есть ли скол/трещина/замена лобового стекла (FW, G)")


class AuctionExtractionSchema(BaseModel):
    """Dual-Schema Pydantic output: raw Japanese anchor fields strictly before translated fields."""

    model_config = ConfigDict(protected_namespaces=())

    # 1. Сырые значения (извлекаются первыми как якорь точности)
    auction_house_raw: str | None = Field(
        default=None,
        description="Название аукционной системы из шапки/логотипа бланка: USS, TAA, CAA, JU, ARAI, Honda, MIRIVE, KCAA, Aucnet и т. д.",
    )
    lot_number_raw: str
    make_raw: str
    model_raw: str
    trim_raw: str | None = None
    model_code_raw: str = Field(description="Код кузова (型式), например DAA-RU3 или 3BA-NRE210W")
    chassis_number_raw: str = Field(description="Номер шасси (車台番号), например RU3-1248879 или 1356915")
    first_reg_raw: str = Field(description="Дата первой регистрации в оригинале: H30/2, 26年5月, R8 11")
    mileage_raw: str = Field(description="Пробег и знаки одометра (*, $, #)")
    engine_cc_raw: str
    transmission_raw: str
    drive_type_raw: str | None = Field(default=None, description="ТОЛЬКО если 2WD или 4WD явно отмечены на листе")
    color_raw: str | None = None
    paint_code_raw: str | None = None
    shaken_raw: str | None = None
    recycling_fee_raw: str | None = None
    overall_grade: str
    exterior_grade: str | None = None
    interior_grade: str | None = None
    inspector_notes_raw: list[str] = Field(default_factory=list)
    seller_comments_raw: list[str] = Field(default_factory=list)

    # 2. Типизированные и переведённые поля (строго с листа, без каталожных догадок)
    auction_house: str | None = Field(
        default=None,
        description="Нормализованное название аукционного дома латиницей: USS, TAA, CAA, JU, ARAI, Honda, MIRIVE, KCAA, Aucnet, ORIX, ZIP, LAA",
    )
    auction_branch: str | None = Field(
        default=None,
        description="Филиал аукциона (например Tokyo, Nagoya, Kyushu), если прямо указан в шапке бланка",
    )
    right_hand_drive: bool | None = Field(
        default=None,
        description="True для правого руля (右ハンドル), False для левого (左ハンドル), null если не указано",
    )
    name_change_deadline: str | None = Field(
        default=None,
        description="Срок перерегистрации 名変 / 名義変更期限 (например 3/30), если указан на листе",
    )
    make_en: str = Field(description="Марка авто на латинице, например Honda")
    model_en: str = Field(description="Модель авто на латинице, например Vezel")
    trim_en: str | None = Field(default=None, description="Комплектация, например Hybrid Z Honda Sensing")
    mileage_km: int | None = Field(default=None, description="Пробег целым числом в км")
    odometer_status: Literal["confirmed", "replaced", "tampered", "unknown"] = "confirmed"
    engine_cc: int | None = Field(default=None, description="Объём двигателя в см³ целым числом, например 1490 или 1500")
    transmission_ru: str
    drive_type: Literal["2WD", "4WD"] | None = Field(
        default=None,
        description="ТОЛЬКО если явно отмечено на листе, иначе null",
    )
    fuel_type: Literal["gasoline", "hybrid", "diesel", "ev", "other"] | None = None
    color_ru: str | None = Field(default=None, description="Буквальный перевод цвета без угадывания оттенка по коду")
    color_changed_ru: str | None = None
    shaken_ru: str | None = None
    recycling_fee_yen: int | None = None
    recycling_fee_paid: bool | None = None
    equipment_ru: list[str] = Field(default_factory=list, description="Отмеченные опции + графа кондиционера")
    defects: list[DefectExtractionSchema] = Field(default_factory=list)
    risk_flags: ExtractedRiskFlagsSchema
    inspector_notes_ru: list[str] = Field(default_factory=list)
    seller_comments_ru: list[str] = Field(default_factory=list)
    extra_ru: list[str] = Field(default_factory=list)
    unreadable_fields: list[str] = Field(
        default_factory=list,
        description="Названия полей, которые не удалось разобрать из-за почерка или качества скана",
    )


SYSTEM_PROMPT = """
Ты — точный парсер японских автомобильных аукционных листов.
Правила:
1. БЕЗ домыслов: извлекай ТОЛЬКО то, что прямо написано или отмечено на листе. Название аукционной системы (USS, TAA, CAA, JU, Honda, ARAI и др.) считывай строго из шапки/логотипа бланка (не додумывай филиал по номеру лота). Если привод (2WD/4WD) не обведён — ставь null. Не угадывай оттенок цвета по коду краски (パール = перламутр).
2. В *_ru полях и extra_ru — БЕЗ кандзи, каны и транслита (пиши 'скол', без '(тобиси)').
3. Стоп-факторы безопасности: внимательно проверяй заметки инспектора на маркеры затопления (冠水, 水没), сработавших подушек безопасности (エアバッグ), града (ひょう害, 雹), деформации стоек (ピラー) и сквозной коррозии (腐食).
4. Схема дефектов: позиции зон бери ТОЛЬКО по схеме кузова (смотри сверху по ходу движения: перед вверху → левый борт слева, правый справа; не зеркаль стороны!). Передняя дверь — ближе к переднему колесу, задняя — к заднему. Чек-лист лобового стекла (FW) переноси в inspector_notes_ru и risk_flags.windshield_damage, а не в defects. Текстовые заметки инспектора оставляй в inspector_notes_raw/inspector_notes_ru.
5. Коды дефектов: извлекай в точности как написано, включая составные коды (A2/W1, AU3, U2), ремонт (R), замену (XX) и деформацию под замену (X).
6. Отдельно проверяй вертикальный текст по краям листа, глубину протектора шин в мм у колёс (добавляй в extra_ru), расположение руля (右ハンドル/左ハンドル -> right_hand_drive), филиал аукциона (auction_branch) и срок перерегистрации (名変 -> name_change_deadline).
7. Если поле обрезано или неразборчиво — не угадывай, добавь его имя в unreadable_fields.
""".strip()


def to_raw_extraction_entity(schema: AuctionExtractionSchema) -> RawExtractionEntity:
    """Map validated Pydantic extraction schema to pure domain RawExtractionEntity."""
    defects = [
        RawDefectEntity(
            visual_location=item.visual_location,
            panel_id=BodyPanel(item.panel_id),
            panel_ru=item.panel_ru,
            raw_code=item.raw_code,
        )
        for item in schema.defects
    ]

    risk_flags = RawRiskFlagsEntity(
        is_flooded=schema.risk_flags.is_flooded,
        airbag_deployed=schema.risk_flags.airbag_deployed,
        hail_damage=schema.risk_flags.hail_damage,
        underbody_rust=schema.risk_flags.underbody_rust,
        underbody_corrosion=schema.risk_flags.underbody_corrosion,
        core_support_repair=schema.risk_flags.core_support_repair,
        pillar_or_frame_repair=schema.risk_flags.pillar_or_frame_repair,
        color_changed=schema.risk_flags.color_changed,
        windshield_damage=schema.risk_flags.windshield_damage,
    )

    return RawExtractionEntity(
        auction_house_raw=schema.auction_house_raw,
        lot_number_raw=schema.lot_number_raw,
        make_raw=schema.make_raw,
        model_raw=schema.model_raw,
        trim_raw=schema.trim_raw,
        model_code_raw=schema.model_code_raw,
        chassis_number_raw=schema.chassis_number_raw,
        first_reg_raw=schema.first_reg_raw,
        mileage_raw=schema.mileage_raw,
        engine_cc_raw=schema.engine_cc_raw,
        transmission_raw=schema.transmission_raw,
        drive_type_raw=schema.drive_type_raw,
        color_raw=schema.color_raw,
        paint_code_raw=schema.paint_code_raw,
        shaken_raw=schema.shaken_raw,
        recycling_fee_raw=schema.recycling_fee_raw,
        overall_grade=schema.overall_grade,
        exterior_grade=schema.exterior_grade,
        interior_grade=schema.interior_grade,
        inspector_notes_raw=list(schema.inspector_notes_raw),
        seller_comments_raw=list(schema.seller_comments_raw),
        auction_house=schema.auction_house,
        make_en=schema.make_en,
        model_en=schema.model_en,
        trim_en=schema.trim_en,
        mileage_km=schema.mileage_km,
        odometer_status=OdometerStatus(schema.odometer_status),
        engine_cc=schema.engine_cc,
        transmission_ru=schema.transmission_ru,
        drive_type=DriveType(schema.drive_type) if schema.drive_type else None,
        fuel_type=FuelType(schema.fuel_type) if schema.fuel_type else None,
        color_ru=schema.color_ru,
        color_changed_ru=schema.color_changed_ru,
        shaken_ru=schema.shaken_ru,
        recycling_fee_yen=schema.recycling_fee_yen,
        recycling_fee_paid=schema.recycling_fee_paid,
        equipment_ru=list(schema.equipment_ru),
        defects=defects,
        risk_flags=risk_flags,
        inspector_notes_ru=list(schema.inspector_notes_ru),
        seller_comments_ru=list(schema.seller_comments_ru),
        extra_ru=list(schema.extra_ru),
        unreadable_fields=list(schema.unreadable_fields),
        auction_branch=schema.auction_branch,
        right_hand_drive=schema.right_hand_drive,
        name_change_deadline=schema.name_change_deadline,
    )
