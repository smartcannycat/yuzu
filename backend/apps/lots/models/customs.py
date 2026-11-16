"""Customs duties, currency rate snapshots, and turnkey Wise Cost ladder models."""

from __future__ import annotations

from django.db import models

from apps.core.enums import AgeCorridor, DutyCalculationMode
from apps.lots.models.lot import Lot


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
