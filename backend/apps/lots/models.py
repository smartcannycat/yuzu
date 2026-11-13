import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from apps.core.enums import (
    AgeCorridor,
    AnomalySeverity,
    AuctionHouse,
    BatchStatus,
    BodyPanel,
    ChecklistItemStatus,
    CrossAuditStatus,
    DriveType,
    DutyCalculationMode,
    FrameIdConfidence,
    FuelType,
    ItemProcessingStatus,
    OdometerStatus,
    PowerHpSource,
    RiskLevel,
    SystemKey,
    TaskStep,
    TrafficLightColor,
    WorkType,
)
from apps.users.models import User


def _batch_item_upload_to(instance: "BatchItem", filename: str) -> str:
    return f"batches/{instance.batch_id}/{filename}"


def _lot_scan_upload_to(instance: "Lot", filename: str) -> str:
    return f"lots/{instance.id or 'temp'}/scans/{filename}"


def _lot_thumb_upload_to(instance: "Lot", filename: str) -> str:
    return f"lots/{instance.id or 'temp'}/thumbs/{filename}"


class Batch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="batches")
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.QUEUED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lots_batches"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return str(self.id)


class Lot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lots")
    completed_at = models.DateTimeField(null=True, blank=True)

    lot_number = models.CharField(max_length=50, blank=True, null=True)
    auction_house = models.CharField(
        max_length=20, choices=AuctionHouse.choices, blank=True, null=True
    )
    auction_branch = models.CharField(max_length=100, blank=True, null=True)
    auction_strictness_index = models.FloatField(null=True, blank=True)

    make = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=200, blank=True, null=True)
    trim = models.CharField(max_length=100, blank=True, null=True)
    model_code = models.CharField(max_length=50, blank=True, null=True)
    chassis_number = models.CharField(max_length=50, blank=True, null=True)
    frame_id = models.CharField(max_length=50, blank=True, null=True)
    frame_id_confidence = models.CharField(
        max_length=20,
        choices=FrameIdConfidence.choices,
        blank=True,
        null=True,
    )

    first_reg_year = models.IntegerField(null=True, blank=True)
    first_reg_month = models.IntegerField(null=True, blank=True)
    first_reg_date_str = models.CharField(max_length=100, blank=True, null=True)
    is_pass_corridor_3_5 = models.BooleanField(null=True, blank=True)

    auction_bid_jpy = models.PositiveBigIntegerField(null=True, blank=True)
    customs_rates_input = models.JSONField(null=True, blank=True)
    is_verified_mild_hybrid = models.BooleanField(default=False)

    engine_cc = models.IntegerField(null=True, blank=True)
    power_hp = models.IntegerField(null=True, blank=True)
    power_hp_source = models.CharField(
        max_length=20,
        choices=PowerHpSource.choices,
        blank=True,
        null=True,
    )
    is_under_160_hp = models.BooleanField(null=True, blank=True)

    mileage_km = models.PositiveIntegerField(null=True, blank=True)
    odometer_status = models.CharField(
        max_length=20, choices=OdometerStatus.choices, blank=True, null=True
    )

    transmission = models.CharField(max_length=50, blank=True, null=True)
    drive_type = models.CharField(max_length=10, choices=DriveType.choices, blank=True, null=True)
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices, blank=True, null=True)

    color_ru = models.CharField(max_length=100, blank=True, null=True)
    paint_code = models.CharField(max_length=20, blank=True, null=True)

    overall_grade = models.CharField(max_length=10, blank=True, null=True)
    exterior_grade = models.CharField(max_length=5, blank=True, null=True)
    interior_grade = models.CharField(max_length=5, blank=True, null=True)
    shaken_until = models.CharField(max_length=50, blank=True, null=True)

    recycling_fee_yen = models.PositiveIntegerField(null=True, blank=True)
    recycling_fee_paid = models.BooleanField(null=True, blank=True)

    equipment_ru = ArrayField(models.CharField(max_length=200), blank=True, default=list)
    inspector_notes_ru = ArrayField(models.TextField(), blank=True, default=list)
    inspector_notes_raw = ArrayField(models.TextField(), blank=True, default=list)
    seller_comments_ru = ArrayField(models.TextField(), blank=True, default=list)
    extra_ru = ArrayField(models.TextField(), blank=True, default=list)
    ocr_warnings = ArrayField(models.CharField(max_length=300), blank=True, default=list)
    low_confidence_fields = ArrayField(models.CharField(max_length=100), blank=True, default=list)

    sheet_scan = models.FileField(upload_to=_lot_scan_upload_to, blank=True, null=True)
    sheet_thumbnail = models.FileField(upload_to=_lot_thumb_upload_to, blank=True, null=True)

    year = models.IntegerField(null=True, blank=True)
    turnkey_cost_rub = models.BigIntegerField(null=True, blank=True)
    market_price_rf_rub = models.BigIntegerField(null=True, blank=True)
    net_benefit_rub = models.BigIntegerField(null=True, blank=True)
    benefit_percentage = models.FloatField(null=True, blank=True)
    verdict = models.CharField(
        max_length=10,
        choices=TrafficLightColor.choices,
        blank=True,
        null=True,
    )
    verdict_headline = models.CharField(max_length=200, blank=True, null=True)
    meti_sanction_risk = models.BooleanField(default=False)
    has_anomaly = models.BooleanField(default=False)
    anomaly_text = models.CharField(max_length=500, blank=True, null=True)

    bid_slider_min_jpy = models.PositiveIntegerField(default=300000)
    bid_slider_max_jpy = models.PositiveIntegerField(default=2500000)
    bid_slider_step_jpy = models.PositiveIntegerField(default=10000)
    is_repairs_included = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lots"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["frame_id"]),
            models.Index(fields=["verdict"]),
            models.Index(fields=["make"]),
            models.Index(fields=["model"]),
        ]

    def __str__(self) -> str:
        parts = [self.make, self.model]
        if self.lot_number:
            parts.append(f"#{self.lot_number}")
        return " ".join(p for p in parts if p) or str(self.id)


class BatchItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="items")
    lot = models.OneToOneField(
        Lot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_item",
    )
    file_index = models.IntegerField()
    original_filename = models.CharField(max_length=255)
    original_file = models.FileField(upload_to=_batch_item_upload_to)
    preview_title = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=ItemProcessingStatus.choices,
        default=ItemProcessingStatus.QUEUED,
    )
    current_step = models.CharField(
        max_length=30,
        choices=TaskStep.choices,
        default=TaskStep.GATEKEEPER,
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lots_batch_items"
        ordering = ["file_index"]
        unique_together = [("batch", "file_index")]
        indexes = [
            models.Index(fields=["batch", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.batch_id} [{self.file_index}] {self.original_filename}"


class LotDefect(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="defects")
    panel_id = models.CharField(max_length=30, choices=BodyPanel.choices)
    panel_ru = models.CharField(max_length=100)
    defect_types = ArrayField(models.CharField(max_length=10))
    severity = models.IntegerField(null=True, blank=True)
    raw_code = models.CharField(max_length=20)
    description_ru = models.CharField(max_length=300)

    class Meta:
        db_table = "lots_defects"
        ordering = ["panel_id"]
        indexes = [
            models.Index(fields=["lot", "panel_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.lot_id} {self.panel_id} {self.raw_code}"


class LotRiskFlags(models.Model):
    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="risk_flags",
    )
    is_flooded = models.BooleanField(default=False)
    airbag_deployed = models.BooleanField(default=False)
    hail_damage = models.BooleanField(default=False)
    underbody_rust = models.BooleanField(default=False)
    underbody_corrosion = models.BooleanField(default=False)
    core_support_repair = models.BooleanField(default=False)
    pillar_or_frame_repair = models.BooleanField(default=False)
    panel_replaced_xx = models.BooleanField(default=False)
    panel_needs_replacement_x = models.BooleanField(default=False)
    odometer_issue = models.BooleanField(default=False)
    color_changed = models.BooleanField(default=False)
    windshield_damage = models.BooleanField(default=False)
    repaired_grade_r_ra = models.BooleanField(default=False)

    class Meta:
        db_table = "lots_risk_flags"

    def __str__(self) -> str:
        return f"RiskFlags for {self.lot_id}"


class TrafficLightVerdict(models.Model):
    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="verdict_detail",
    )
    verdict = models.CharField(max_length=10, choices=TrafficLightColor.choices)
    headline = models.CharField(max_length=200)
    short_verdict_label = models.CharField(max_length=200)
    badge_text = models.CharField(max_length=200)
    net_benefit_rub = models.BigIntegerField()
    benefit_percentage = models.FloatField()
    body_summary_ru = models.TextField()
    interior_summary_ru = models.TextField()
    reasoning_bullets = ArrayField(
        models.TextField(),
        blank=True,
        default=list,
    )

    class Meta:
        db_table = "lots_verdicts"

    def __str__(self) -> str:
        return f"{self.verdict} for {self.lot_id}"


class MarketComparisonInfo(models.Model):
    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="market_info",
    )
    market_price_rf_rub = models.BigIntegerField()
    analogs_count = models.PositiveIntegerField()
    price_min_rub = models.BigIntegerField(null=True, blank=True)
    price_max_rub = models.BigIntegerField(null=True, blank=True)
    search_region_ru = models.CharField(max_length=100, default="ДФО / Владивосток")
    excludes_under_order = models.BooleanField(default=True)
    filtered_out_under_order_count = models.PositiveIntegerField(default=0)
    is_fallback = models.BooleanField(default=False)
    fallback_reason_ru = models.CharField(max_length=500, blank=True, null=True)
    drom_search_url = models.URLField(max_length=500)

    class Meta:
        db_table = "lots_market_comparisons"

    def __str__(self) -> str:
        return f"Market for {self.lot_id}"


class CrossAuditReport(models.Model):
    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="cross_audit",
    )
    status = models.CharField(max_length=20, choices=CrossAuditStatus.choices)
    source_name = models.CharField(max_length=100, default="AucJP + AAA Japan / Pravto")
    is_archive_available = models.BooleanField(default=True)
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices)
    has_critical_anomaly = models.BooleanField(default=False)
    headline_ru = models.CharField(max_length=500)
    times_auctioned = models.PositiveIntegerField(default=0)
    verified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "lots_cross_audits"

    def __str__(self) -> str:
        return f"{self.status} for {self.lot_id}"


class AnomalyAlert(models.Model):
    audit = models.ForeignKey(
        CrossAuditReport,
        on_delete=models.CASCADE,
        related_name="anomalies",
    )
    type = models.CharField(max_length=50)
    severity = models.CharField(max_length=10, choices=AnomalySeverity.choices)
    title_ru = models.CharField(max_length=200)
    message_ru = models.TextField()
    diff_details = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "lots_anomaly_alerts"
        ordering = ["severity", "id"]

    def __str__(self) -> str:
        return f"{self.severity}: {self.title_ru}"


class PastAuctionRecord(models.Model):
    audit = models.ForeignKey(
        CrossAuditReport,
        on_delete=models.CASCADE,
        related_name="history",
    )
    auction_date = models.DateField()
    auction_house = models.CharField(max_length=100)
    auction_strictness = models.FloatField(null=True, blank=True)
    lot_number = models.CharField(max_length=50)
    overall_grade = models.CharField(max_length=10)
    mileage_km = models.PositiveIntegerField(null=True, blank=True)
    defects_summary = models.CharField(max_length=500, blank=True, null=True)
    closing_price_jpy = models.PositiveBigIntegerField(null=True, blank=True)
    sheet_archive_url = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        db_table = "lots_past_auctions"
        ordering = ["-auction_date"]

    @property
    def auction_date_str(self) -> str:
        return self.auction_date.strftime("%d.%m.%Y") if self.auction_date else ""

    def __str__(self) -> str:
        return f"{self.auction_house} {self.auction_date_str} #{self.lot_number}"


class SafetyChecklist(models.Model):
    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="safety_checklist",
    )
    overall_status = models.CharField(max_length=10, choices=ChecklistItemStatus.choices)
    overall_label_ru = models.CharField(max_length=100)

    class Meta:
        db_table = "lots_safety_checklists"

    def __str__(self) -> str:
        return f"{self.overall_label_ru} for {self.lot_id}"


class SafetyCheckItem(models.Model):
    checklist = models.ForeignKey(
        SafetyChecklist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    system_key = models.CharField(max_length=30, choices=SystemKey.choices)
    label_ru = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=ChecklistItemStatus.choices)
    detail_ru = models.TextField()

    class Meta:
        db_table = "lots_safety_check_items"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.label_ru


class CurrencyRatesSnapshot(models.Model):
    customs = models.OneToOneField(
        "CustomsCalculation",
        on_delete=models.CASCADE,
        related_name="rates_snapshot",
    )
    jpy_rub_bank = models.FloatField()
    jpy_rate_source = models.CharField(max_length=100, default="ДВ-банк (ориентир)")
    eur_rub_cbrf = models.FloatField()
    usd_rub_cbrf = models.FloatField()
    cbrf_date = models.CharField(max_length=20)

    class Meta:
        db_table = "lots_currency_rates"

    def __str__(self) -> str:
        return f"Rates {self.cbrf_date}"


class CustomsCalculation(models.Model):
    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="customs_calc",
    )
    age_corridor = models.CharField(max_length=20, choices=AgeCorridor.choices)
    duty_calculation_mode = models.CharField(
        max_length=20,
        choices=DutyCalculationMode.choices,
        default=DutyCalculationMode.EUR_PER_CC,
    )
    engine_cc = models.IntegerField()
    duty_rate_eur_per_cc = models.FloatField(null=True, blank=True)
    effective_duty_pct = models.FloatField(null=True, blank=True)
    customs_duty_eur = models.FloatField()
    customs_duty_rub = models.BigIntegerField()
    # Excise and import VAT apply to cars taxed outside the unified EAEU
    # rates (battery electric vehicles); zero for ICE/hybrid imports.
    excise_rub = models.BigIntegerField(default=0)
    import_vat_rub = models.BigIntegerField(default=0)
    is_under_160_hp = models.BooleanField(null=True, blank=True)
    # Utilization fee mode selected by the user (personal/commercial switch);
    # ``is_commercial_util`` stores the mode actually applied, which may be
    # commercial even for a personal selection when power is unknown or >160 hp.
    util_mode_selected_commercial = models.BooleanField(default=False)
    is_commercial_util = models.BooleanField(default=False)
    utilization_fee_rub = models.BigIntegerField()
    customs_clearance_fee_rub = models.BigIntegerField()
    freight_vladivostok_rub = models.BigIntegerField()
    broker_svh_sbkts_rub = models.BigIntegerField()
    meti_sanction_risk = models.BooleanField(default=False)

    class Meta:
        db_table = "lots_customs_calculations"

    def __str__(self) -> str:
        return f"Customs for {self.lot_id}"


class FarpostRepairSummary(models.Model):
    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="farpost_repair",
    )
    total_parts_from_rub = models.BigIntegerField(default=0)
    total_works_rub = models.BigIntegerField(default=0)
    grand_total_repair_rub = models.BigIntegerField(default=0)
    has_color_matched_parts = models.BooleanField(default=False)
    included_in_turnkey_hint_ru = models.CharField(
        max_length=200,
        default="Сумма уже включена в расчёт под ключ",
    )

    class Meta:
        db_table = "lots_farpost_repairs"

    def __str__(self) -> str:
        return f"Farpost for {self.lot_id}"


class DamagedPartItem(models.Model):
    repair = models.ForeignKey(
        FarpostRepairSummary,
        on_delete=models.CASCADE,
        related_name="parts",
    )
    panel_id = models.CharField(max_length=30, choices=BodyPanel.choices)
    defect_code = models.CharField(max_length=10)
    part_name_ru = models.CharField(max_length=200)
    subtitle_ru = models.CharField(max_length=200, blank=True, null=True)
    price_from_rub = models.BigIntegerField(default=0)
    in_stock_vladivostok = models.BooleanField(default=False)
    is_statistical_fallback = models.BooleanField(default=False)

    class Meta:
        db_table = "lots_damaged_parts"
        ordering = ["panel_id"]

    def __str__(self) -> str:
        return self.part_name_ru


class ServiceWorkItem(models.Model):
    repair = models.ForeignKey(
        FarpostRepairSummary,
        on_delete=models.CASCADE,
        related_name="service_works",
    )
    work_type = models.CharField(max_length=20, choices=WorkType.choices)
    label_ru = models.CharField(max_length=200)
    amount_rub = models.BigIntegerField(default=0)
    zero_cost_reason_ru = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = "lots_service_works"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.label_ru


class WiseCostLadder(models.Model):
    lot = models.OneToOneField(
        Lot,
        on_delete=models.CASCADE,
        related_name="wise_cost_ladder",
    )
    car_bid_jpy = models.PositiveBigIntegerField()
    car_bid_rub = models.BigIntegerField()
    turnkey_cost_rub = models.BigIntegerField()
    market_price_rf_rub = models.BigIntegerField()
    net_benefit_rub = models.BigIntegerField()
    benefit_percentage = models.FloatField()

    class Meta:
        db_table = "lots_wise_cost_ladders"

    def __str__(self) -> str:
        return f"WiseCost for {self.lot_id}"


class WiseCostStep(models.Model):
    ladder = models.ForeignKey(
        WiseCostLadder,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    step_number = models.IntegerField()
    name_ru = models.CharField(max_length=200)
    amount_rub = models.BigIntegerField()
    original_currency = models.CharField(max_length=10, blank=True, null=True)
    original_amount = models.FloatField(null=True, blank=True)
    is_optional = models.BooleanField(default=False)

    class Meta:
        db_table = "lots_wise_cost_steps"
        ordering = ["step_number"]
        unique_together = [("ladder", "step_number")]

    def __str__(self) -> str:
        return f"{self.step_number}. {self.name_ru}"
