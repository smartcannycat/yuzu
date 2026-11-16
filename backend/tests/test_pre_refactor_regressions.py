"""Regression tests for pre-refactor functional and domain fixes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from django.utils import timezone

from apps.core.enums import (
    AgeCorridor,
    ChecklistItemStatus,
    FuelType,
    OdometerStatus,
    PowerHpSource,
    SystemKey,
    TrafficLightColor,
    WorkType,
)
from apps.lots.customs import meti_sanction_risk
from apps.lots.economics import _resolve_start_bid_jpy
from apps.lots.integrations.aleado.parser import AleadoLotRow
from apps.lots.integrations.aleado.service import (
    AleadoCrossAuditService,
    _candidate_is_own_lot,
    _evaluate_rules,
    _VerifiedRow,
    clean_model_code,
)
from apps.lots.integrations.currency.client import CbrfClient
from apps.lots.integrations.currency.domain import BaseRates
from apps.lots.integrations.currency.service import CurrencyRatesService
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.filtering import _truncate_drom_url
from apps.lots.integrations.drom.power import DromPowerResolver
from apps.lots.integrations.drom.schemas import DromBlockedError, DromSearchCriteria
from apps.lots.integrations.drom.service import DromMarketService, _SearchStep
from apps.lots.integrations.drom.slugs import DromSlugResolver, ResolvedDromSlug
from apps.lots.integrations.farpost.matrix import _operations, _work_label, repair_matrix
from apps.lots.integrations.farpost.parser import _contains_code
from apps.lots.integrations.farpost.service import estimate_repair
from apps.lots.integrations.ml.parser import _sheet_to_lot_fields
from apps.lots.integrations.ml.schemas import NormalizedSheet, ParserResponse
from apps.lots.models import (
    CurrencyRatesSnapshot,
    CustomsCalculation,
    Lot,
    LotDefect,
    LotRiskFlags,
    MarketComparisonInfo,
    PastAuctionRecord,
    WiseCostLadder,
)
from apps.lots.queries import _build_normalized_sheet
from apps.lots.recalc import recalculate_lot
from apps.lots.safety import build_safety_checklist
from apps.lots.schemas import RecalculateRequest
from apps.users.models import User


@pytest.mark.django_db
def test_recalculate_updates_verdict_and_returns_power_on_first_call() -> None:
    user = User.objects.create_user(email="recalc@example.com", password="Password123!")
    lot = Lot.objects.create(
        user=user,
        lot_number="555",
        make="Toyota",
        model="Vitz",
        frame_id="NSP130-1000001",
        first_reg_year=2021,
        first_reg_month=5,
        engine_cc=1300,
        fuel_type=FuelType.GASOLINE,
        power_hp=99,
        power_hp_source=PowerHpSource.DROM_CATALOG,
        is_under_160_hp=True,
        overall_grade="4.5",
        auction_bid_jpy=500_000,
        market_price_rf_rub=1_500_000,
        turnkey_cost_rub=900_000,
        net_benefit_rub=600_000,
        benefit_percentage=66.7,
        verdict=TrafficLightColor.GREEN,
        verdict_headline="Можно брать",
        completed_at=timezone.now(),
    )
    customs = CustomsCalculation.objects.create(
        lot=lot,
        age_corridor=AgeCorridor.THREE_TO_FIVE_YEARS,
        engine_cc=1300,
        customs_duty_eur=1950.0,
        customs_duty_rub=195_000,
        utilization_fee_rub=5_200,
        customs_clearance_fee_rub=3_100,
        is_commercial_util=False,
        util_mode_selected_commercial=False,
        is_under_160_hp=True,
        broker_svh_sbkts_rub=99_000,
        freight_vladivostok_rub=80_000,
    )
    CurrencyRatesSnapshot.objects.create(
        customs=customs,
        eur_rub_cbrf=100.0,
        usd_rub_cbrf=90.0,
        jpy_rub_bank=0.60,
        cbrf_date="16.11.2026",
    )
    WiseCostLadder.objects.create(
        lot=lot,
        car_bid_jpy=500_000,
        car_bid_rub=300_000,
        turnkey_cost_rub=900_000,
        market_price_rf_rub=1_500_000,
        net_benefit_rub=600_000,
        benefit_percentage=66.7,
    )
    MarketComparisonInfo.objects.create(
        lot=lot,
        market_price_rf_rub=1_500_000,
        analogs_count=5,
    )

    res = recalculate_lot(
        user,
        lot.id,
        RecalculateRequest(bid_jpy=5_000_000, custom_power_hp=120),
    )
    assert res.net_benefit_rub < 0
    assert res.verdict.verdict == TrafficLightColor.RED
    assert res.power_hp == 120
    assert res.power_hp_source == PowerHpSource.MANUAL
    assert res.is_under_160_hp is True


@pytest.mark.django_db
def test_safety_checklist_separates_airbag_from_flood_or_fire() -> None:
    user = User.objects.create_user(email="safety@example.com", password="Password123!")
    lot = Lot.objects.create(user=user, make="Honda", model="Fit", odometer_status="confirmed")
    LotRiskFlags.objects.create(lot=lot, airbag_deployed=True, is_flooded=False)

    checklist = build_safety_checklist(lot)
    by_key = {item.system_key: item for item in checklist.items.all()}
    assert by_key[SystemKey.AIRBAGS_SRS].status == ChecklistItemStatus.CRITICAL
    assert by_key[SystemKey.FLOOD_OR_FIRE].status == ChecklistItemStatus.OK


def test_meti_sanction_risk_flags_large_engine_with_missing_or_other_fuel() -> None:
    assert meti_sanction_risk(None, 3500) is True
    assert meti_sanction_risk(FuelType.OTHER, 2500) is True
    assert meti_sanction_risk(FuelType.OTHER, 1500) is False


@pytest.mark.django_db
def test_start_bid_allows_low_explicit_bid_and_ignores_missing_passport() -> None:
    user = User.objects.create_user(email="bid@example.com", password="Password123!")
    kei = Lot.objects.create(user=user, make="Suzuki", model="Alto", auction_bid_jpy=150_000)
    assert _resolve_start_bid_jpy(kei) == 150_000

    missing_year = Lot.objects.create(
        user=user,
        make="Honda",
        model="Vezel",
        market_price_rf_rub=2_000_000,
        fuel_type=FuelType.GASOLINE,
        engine_cc=1500,
        first_reg_year=None,
    )
    assert _resolve_start_bid_jpy(missing_year) is None


@pytest.mark.django_db
def test_partial_ocr_sheet_serializes_with_safe_fallbacks_and_validates_month() -> None:
    fields = _sheet_to_lot_fields(
        NormalizedSheet(make="Honda", model="Fit", first_reg_month=13),
        ParserResponse(status="partial"),
        [],
    )
    assert fields["first_reg_month"] is None
    assert any("13" in w for w in fields["ocr_warnings"])

    user = User.objects.create_user(email="partial@example.com", password="Password123!")
    lot = Lot.objects.create(
        user=user,
        lot_number="10",
        auction_house="USS",
        make="Honda",
        model="Fit",
        frame_id="GE6-1000001",
        overall_grade="4",
        model_code=None,
        chassis_number=None,
        frame_id_confidence=None,
        odometer_status=None,
        transmission=None,
    )
    LotRiskFlags.objects.create(lot=lot)
    normalized = _build_normalized_sheet(lot)
    assert normalized.model_code == ""
    assert normalized.chassis_number == ""
    assert normalized.transmission == "не указана"
    assert normalized.odometer_status == OdometerStatus.UNKNOWN


def test_aleado_fixes_for_single_letter_codes_own_lot_and_rules() -> None:
    note = Lot(frame_id="E12-123456", model_code="")
    assert clean_model_code(note) == "E12"
    touring = Lot(frame_id="", model_code="3BA-NRE210W-AWXNB")
    assert clean_model_code(touring) == "NRE210W"

    lot = Lot(
        lot_number="100",
        auction_house="",
        auction_branch="",
        overall_grade="4.5",
        mileage_km=30_000,
    )
    other_row = AleadoLotRow(
        trading_date=datetime(2025, 1, 10, tzinfo=UTC),
        lot_number="100",
        auction_house="USS Tokyo",
        model_name="Note",
        grade="RB",
        year=2020,
        mileage_km=95_000,
        displacement_cc=1200,
        transmission="AT",
        color="white",
        model_type="E12",
        start_price_jpy=150_000,
        result="sold",
        internal_id="1",
        photo_url=None,
    )
    assert _candidate_is_own_lot(other_row, lot) is False

    alerts = _evaluate_rules(lot, [_VerifiedRow(row=other_row)])
    types = {alert.type for alert in alerts}
    assert types == {"grade_regression", "odometer_rollback"}


@pytest.mark.django_db
def test_aleado_excludes_undated_rows_and_does_not_save_start_price_as_closing() -> None:
    user = User.objects.create_user(email="aleado@example.com", password="Password123!")
    lot = Lot.objects.create(
        user=user,
        make="Nissan",
        model="Note",
        frame_id="E12-123456",
        model_code="DBA-E12",
        lot_number="99",
        auction_house="USS",
        first_reg_year=2020,
        overall_grade="4",
        mileage_km=40_000,
    )

    class _Client:
        def search_lots(self, *_args, **_kwargs):
            return [
                AleadoLotRow(
                    trading_date=None,
                    lot_number="501",
                    auction_house="TAA",
                    model_name="Note",
                    grade="4",
                    year=2020,
                    mileage_km=40_000,
                    displacement_cc=1200,
                    transmission="AT",
                    color="white",
                    model_type="E12",
                    start_price_jpy=220_000,
                    result="available",
                    internal_id="501",
                    photo_url=None,
                ),
                AleadoLotRow(
                    trading_date=datetime(2025, 2, 1, tzinfo=UTC),
                    lot_number="502",
                    auction_house="JU",
                    model_name="Note",
                    grade="4",
                    year=2020,
                    mileage_km=40_000,
                    displacement_cc=1200,
                    transmission="AT",
                    color="white",
                    model_type="E12",
                    start_price_jpy=220_000,
                    result="sold",
                    internal_id="502",
                    photo_url=None,
                ),
            ]

        def fetch_lot_detail(self, *_args):
            raise AssertionError("Not expected")

    class _Ml:
        def read_chassis_number(self, *_args):
            raise AssertionError("Not expected")

    service = AleadoCrossAuditService(client=_Client(), ml_client=_Ml())
    service._verify_candidates = lambda _lot, rows: [_VerifiedRow(row=r) for r in rows]
    outcome = service.audit_lot(lot)
    assert outcome.times_auctioned == 1
    assert PastAuctionRecord.objects.filter(audit__lot=lot).count() == 1
    assert PastAuctionRecord.objects.get(audit__lot=lot).closing_price_jpy is None


@pytest.mark.django_db
def test_farpost_matrix_glass_codes_and_body_code_suffix_matching() -> None:
    matrix = repair_matrix()
    assert _operations({"G"}, matrix) == {WorkType.PDR_AND_POLISH: 1500}
    assert _operations({"P2"}, matrix) == {WorkType.PAINT: 11000}
    assert _operations({"R"}, matrix) == {}
    assert _operations({"C3"}, matrix) == {WorkType.BODYWORK: 37500}
    assert "Ремонт скола" in _work_label(WorkType.PDR_AND_POLISH, "Лобовое стекло", "windshield")
    assert _contains_code("Бампер задний Toyota Corolla Touring NRE210W", "NRE210") is True

    user = User.objects.create_user(email="fp@example.com", password="Password123!")
    lot = Lot.objects.create(user=user, make="Toyota", model="Corolla", frame_id="NRE210-1")
    LotDefect.objects.create(
        lot=lot,
        panel_id="windshield",
        panel_ru="Лобовое стекло",
        defect_types=["G"],
        raw_code="G",
        description_ru="Скол",
    )
    estimate = estimate_repair(lot, client=object())  # type: ignore[arg-type]
    assert estimate.grand_total_repair_rub == 1500
    assert "Ремонт скола" in estimate.service_works[0].label_ru


def test_drom_preserves_frametype_on_rf_and_truncates_query_before_slug() -> None:
    slug = ResolvedDromSlug("toyota", "corolla", frame_type_id=3)
    url = DromMarketService._build_step_url(
        DromSearchCriteria(make="Toyota", model="Corolla Touring", year=2020),
        slug,
        _SearchStep(
            region_scope="rf",
            region_label_ru="РФ",
            year_tolerance=0,
            relax_specs=True,
            is_fallback=True,
            fallback_reason_ru=None,
        ),
    )
    assert "frametype%5B%5D=3" in url

    truncated = _truncate_drom_url(
        "https://auto.drom.ru/",
        "toyota",
        "corolla_touring",
        "&".join(f"p{i}=abcdefghij1234567890" for i in range(30)),
    )
    assert truncated.startswith("https://auto.drom.ru/toyota/corolla_touring/bez-probega/")
    assert len(truncated) <= 500


@pytest.mark.django_db
def test_drom_power_reraises_blocked_without_caching_partial_specs() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        url = str(request.url)
        if url.endswith("/catalog/toyota/corolla/"):
            return httpx.Response(
                200,
                text=(
                    '<a href="/catalog/toyota/corolla/g_1/">NRE210</a>'
                    '<a href="/catalog/toyota/corolla/g_2/">NRE210</a>'
                ),
            )
        if url.endswith("/catalog/toyota/corolla/g_1/"):
            return httpx.Response(200, text="<tr><td>1.2 л, 116 л.с.</td><td>NRE210W</td></tr>")
        return httpx.Response(403, text="Forbidden")

    client = DromHttpClient(transport=httpx.MockTransport(handler))
    resolver = DromPowerResolver(client, DromSlugResolver(client))
    with pytest.raises(DromBlockedError):
        resolver._fetch_generation_specs(
            [
                "https://www.drom.ru/catalog/toyota/corolla/g_1/",
                "https://www.drom.ru/catalog/toyota/corolla/g_2/",
            ]
        )


@pytest.mark.django_db
def test_currency_spread_formatting_avoids_scientific_notation() -> None:
    class _Cache:
        def read_fresh(self):
            return (
                BaseRates(
                    eur_rub=Decimal("100"),
                    usd_rub=Decimal("90"),
                    jpy_rub=Decimal("0.6"),
                    cbrf_date="16.11.2026",
                ),
                datetime.now(UTC) - timedelta(seconds=10),
            )

    service = CurrencyRatesService(
        cache=_Cache(),  # type: ignore[arg-type]
        client=CbrfClient(api_url="https://www.cbr-xml-daily.ru/daily_json.js"),
        fallback_config=BaseRates(
            eur_rub=Decimal("95"),
            usd_rub=Decimal("85"),
            jpy_rub=Decimal("0.55"),
            cbrf_date="16.11.2026",
        ),
        spread=Decimal("0.10"),
        ttl=timedelta(hours=12),
    )
    res = service.get_currency_rates()
    assert "10%" in res.jpy_rate_source
    assert "1E+1" not in res.jpy_rate_source
