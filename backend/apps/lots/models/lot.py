"""Core Lot entity, body defects, risk flags, and traffic-light verdict."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from apps.core.enums import (
    AuctionHouse,
    BodyPanel,
    DriveType,
    FrameIdConfidence,
    FuelType,
    LotArchiveReason,
    OdometerStatus,
    PowerHpSource,
    TrafficLightColor,
)
from apps.lots.models import _lot_scan_upload_to, _lot_thumb_upload_to
from apps.users.models import User

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Self


class LotQuerySet(models.QuerySet["Lot"]):
    """Reusable composable queries for completed non-deleted lots and lifecycle views."""

    def ready(self) -> Self:
        """Filter completed lots that have not been soft-deleted."""
        return self.filter(completed_at__isnull=False, deleted_at__isnull=True)

    def ready_for_user(self, user: User) -> Self:
        """Filter completed, non-deleted lots owned by ``user``."""
        return self.ready().filter(user=user)

    def effectively_active(self, now: datetime | None = None) -> Self:
        """Filter lots treated as active on read (including unexpired deadlines)."""
        current_time = now or timezone.now()
        return self.filter(
            models.Q(is_archived=False)
            & (
                models.Q(auto_archive_disabled=True)
                | models.Q(expires_at__isnull=True)
                | models.Q(expires_at__gt=current_time)
            )
        )

    def effectively_archived(self, now: datetime | None = None) -> Self:
        """Filter lots archived explicitly or logically expired as of ``now``."""
        current_time = now or timezone.now()
        return self.filter(
            models.Q(is_archived=True)
            | (
                models.Q(auto_archive_disabled=False)
                & models.Q(expires_at__isnull=False)
                & models.Q(expires_at__lte=current_time)
            )
        )

    def expired_unarchived(self, now: datetime | None = None) -> Self:
        """Filter completed active lots past ``expires_at`` awaiting background archival."""
        current_time = now or timezone.now()
        return self.ready().filter(
            is_archived=False,
            auto_archive_disabled=False,
            expires_at__isnull=False,
            expires_at__lte=current_time,
        )


def has_full_detail(lot: Lot) -> bool:
    """Return True when all related detail models required for full specification exist."""
    required_attrs = (
        "risk_flags",
        "verdict_detail",
        "market_info",
        "cross_audit",
        "safety_checklist",
        "customs_calc",
        "farpost_repair",
        "wise_cost_ladder",
    )
    if not all(hasattr(lot, name) for name in required_attrs):
        return False
    return hasattr(lot.customs_calc, "rates_snapshot")


class Lot(models.Model):
    objects = LotQuerySet.as_manager()
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

    bid_slider_min_jpy = models.PositiveIntegerField(default=100000)
    bid_slider_max_jpy = models.PositiveIntegerField(default=2500000)
    bid_slider_step_jpy = models.PositiveIntegerField(default=10000)
    is_repairs_included = models.BooleanField(default=True)
    baseline_economics = models.JSONField(null=True, blank=True)

    auction_date = models.CharField(max_length=20, blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_reason = models.CharField(
        max_length=20,
        choices=LotArchiveReason.choices,
        blank=True,
        null=True,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    auto_archive_disabled = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lots"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(
                fields=["user", "deleted_at", "is_archived"],
                name="lots_user_del_arch_idx",
            ),
            models.Index(
                fields=["user", "deleted_at", "expires_at"],
                name="lots_user_del_exp_idx",
            ),
            models.Index(fields=["frame_id"]),
            models.Index(fields=["verdict"]),
            models.Index(fields=["make"]),
            models.Index(fields=["model"]),
        ]

    def has_full_detail(self) -> bool:
        """Return True when all related detail models required for full specification exist."""
        return has_full_detail(self)

    def __str__(self) -> str:
        parts = [self.make, self.model]
        if self.lot_number:
            parts.append(f"#{self.lot_number}")
        return " ".join(p for p in parts if p) or str(self.id)


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
