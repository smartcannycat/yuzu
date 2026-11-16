"""Farpost repair estimate, damaged parts, and STO service work models."""

from __future__ import annotations

from django.db import models

from apps.core.enums import BodyPanel, PartSourceKind, WorkType
from apps.lots.models.lot import Lot


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
    source_kind = models.CharField(
        max_length=32,
        choices=PartSourceKind.choices,
        blank=True,
        default="",
    )
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
