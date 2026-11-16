"""Market comparison, cross-audit history, and safety checklist models."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.core.enums import (
    AnomalySeverity,
    ChecklistItemStatus,
    CrossAuditStatus,
    RiskLevel,
    SystemKey,
)
from apps.lots.models.lot import Lot


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
