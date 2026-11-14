"""Tests for the Aleado cross-audit integration (BE-08).

Covers HTML parsers (fixtures recorded from the live site), the HTTP
client (lazy login, throttling, error mapping) and the cross-audit
service (history building, anomaly rules, persistence, pipeline
fallback).
"""

import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from django.core.files.base import ContentFile

from apps.core.enums import (
    BatchStatus,
    CrossAuditStatus,
    ItemProcessingStatus,
    RiskLevel,
    TaskStep,
)
from apps.lots.integrations.aleado import (
    AleadoAuthError,
    AleadoClient,
    AleadoLotRow,
    AleadoParseError,
    AleadoUnavailableError,
)
from apps.lots.integrations.aleado.parser import parse_lot_detail, parse_search_results
from apps.lots.integrations.aleado.service import (
    AleadoCrossAuditService,
    _build_outcome,
    _evaluate_rules,
    clean_model_code,
)
from apps.lots.integrations.ml.client import MlServiceClient
from apps.lots.models import Batch, BatchItem, CrossAuditReport, Lot
from apps.lots.pipeline import _step_cross_audit
from config.settings.config import AppSettings

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "aleado"


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _lot_row(**overrides: object) -> AleadoLotRow:
    base: dict[str, object] = {
        # Past trading date: rules apply only to verified past rows, so
        # rule-level fixtures use history dates by default.
        "trading_date": datetime(2025, 11, 10),
        "lot_number": "222",
        "auction_house": "TAA Hiroshima",
        "model_name": "FREED",
        "grade": "4",
        "year": 2017,
        "mileage_km": 25000,
        "displacement_cc": 1500,
        "transmission": "IAT",
        "color": "RED",
        "model_type": "GB5",
        "start_price_jpy": 100000,
        "result": "sold",
        "internal_id": "1",
        "photo_url": None,
    }
    base.update(overrides)
    return AleadoLotRow(**base)


def _verified_row(**overrides: object):
    from apps.lots.integrations.aleado.service import _VerifiedRow

    return _VerifiedRow(row=_lot_row(**overrides))


def _ml_client_with_chassis_read(
    frame_id: str | None, *, raw: str | None = None
) -> MlServiceClient:
    """ML client whose transport always returns the given chassis read."""
    payload = {
        "frame_id": frame_id,
        "raw": raw if raw is not None else frame_id,
        "confidence": "high" if frame_id else "low",
        "cached": False,
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return MlServiceClient(
        base_url="http://ml.test", timeout_sec=5.0, transport=httpx.MockTransport(handler)
    )


def _ml_client_failing() -> MlServiceClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ml service down")

    return MlServiceClient(
        base_url="http://ml.test", timeout_sec=5.0, transport=httpx.MockTransport(handler)
    )


# --- parser tests -----------------------------------------------------------


def test_parse_search_results_reads_total_and_rows() -> None:
    total, rows = parse_search_results(_fixture("search_gb5_2017.html"))

    assert total == 94
    assert len(rows) == 5
    first = rows[0]
    assert first.lot_number == "10034"
    assert first.auction_house == "MIRIVE Saitama"
    assert first.model_name == "FREED"
    assert first.grade == "R"
    assert first.year == 2017
    assert first.mileage_km == 25000
    assert first.displacement_cc == 1500
    assert first.transmission == "IAT"
    assert first.model_type == "GB5"
    assert first.start_price_jpy == 110000  # "110" thousand JPY hint
    assert first.result == "available"
    assert first.internal_id == "981967852"
    assert first.photo_url is not None and "p3.aleado.com/image" in first.photo_url
    assert first.trading_date == datetime(2026, 11, 18, 10, 28, 0)


def test_parse_search_results_missing_marker_raises() -> None:
    with pytest.raises(AleadoParseError):
        parse_search_results("<html><body>session expired</body></html>")


def test_parse_search_results_zero_price_hint_is_none() -> None:
    html = (
        '<html><body>Found total lots: <b><font color="red">1</font></b>'
        '<div id="priceLotS1" style="display:none">0</div>'
        '<tr class="ColorGreed2" id="cell_1"><td id="bid_number_1"><b>555</b></td>'
        '<td id="auction_1">USS Tokyo</td><td id="model_1">FREED</td>'
        '<td id="grade_1">4</td><td id="year_1">2017</td><td id="mileage_1">10 000</td>'
        '<td id="displacement_1">1500cc</td><td id="model_type_1">GB5</td>'
        "</tr></body></html>"
    )
    total, rows = parse_search_results(html)
    assert total == 1
    assert rows[0].start_price_jpy is None


def test_parse_lot_detail_reads_scores_chassis_and_mileage() -> None:
    detail = parse_lot_detail(_fixture("lot_detail_freed.html"))

    assert detail.scores == "R"
    assert detail.start_price_jpy == 110000
    assert detail.mileage_km == 25000
    assert detail.model_type == "GB5"
    assert detail.year == 2017
    assert detail.auction_house == "MIRIVE Saitama"
    assert detail.lot_number == "10034"
    assert detail.trading_datetime == datetime(2026, 11, 18, 10, 28, 0)
    assert detail.result == "available"
    assert detail.chassis_image_url is not None
    assert "p3.aleado.com/chassis/" in detail.chassis_image_url


# --- client tests -----------------------------------------------------------


def _client(handler, **kwargs) -> AleadoClient:
    return AleadoClient(transport=httpx.MockTransport(handler), **kwargs)


def _authed(fixture: str) -> str:
    """Wrap a fixture the way an authenticated Aleado page looks like."""
    return "<html><body>Sign out</body>" + fixture + "</body></html>"


def test_client_lazy_login_retries_after_login_page() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and "auth/login.php" in str(request.url):
            assert "username=test_account_id" in request.read().decode()
            return httpx.Response(
                302,
                headers={"Location": "/yahoo/0-catlist.html"},
                text="<html><body>catalog</body></html>",
            )
        if len(seen) < 3:
            return httpx.Response(200, text="<html><body>Login form</body></html>")
        return httpx.Response(200, text=_authed(_fixture("search_gb5_2017.html")))

    client = _client(handler, username="test_account_id", password="secret")
    with patch.object(client, "_is_authenticated", lambda _response: False):
        rows = client.search_lots("GB5", 2017)

    assert len(seen) == 4  # GET, POST login, GET retry, GET retry 2 (mock never authenticates)
    assert any(r.method == "POST" and "auth/login.php" in str(r.url) for r in seen)
    assert rows[0].lot_number == "10034"


def test_client_skips_login_when_already_authenticated() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=_authed(_fixture("search_gb5_2017.html")))

    rows = _client(handler, username="test_account_id", password="secret").search_lots("GB5", 2017)

    assert len(seen) == 1
    assert len(rows) == 5


def test_client_raises_auth_error_when_login_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            # A rejected login re-renders the login form itself.
            return httpx.Response(
                200,
                text="<html><title>Login to Auctions system</title></html>",
            )
        return httpx.Response(200, text="<html>Login page</html>")

    with pytest.raises(AleadoAuthError):
        _client(handler, username="u", password="p").search_lots("GB5", 2017)


def test_client_requires_credentials() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Login page</html>")

    with pytest.raises(AleadoAuthError):
        _client(handler).search_lots("GB5", 2017)


def test_client_maps_network_and_server_errors() -> None:
    def broken(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(AleadoUnavailableError):
        _client(broken, username="u", password="p").search_lots("GB5", 2017)

    def server_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="busy")

    with pytest.raises(AleadoUnavailableError):
        _client(server_error, username="u", password="p").search_lots("GB5", 2017)


def test_client_throttles_requests() -> None:
    sleeps: list[float] = []
    monotonic_values = iter([100.0, 100.0, 100.0, 100.0, 100.0, 100.0])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_authed(_fixture("search_gb5_2017.html")))

    # Reset the process-global throttle stamp left by other tests.
    AleadoClient._global_last_request_at = None
    client = _client(
        handler,
        username="u",
        password="p",
        request_interval_sec=1.5,
        sleep_fn=sleeps.append,
    )
    with patch(
        "apps.lots.integrations.aleado.client.time.monotonic", lambda: next(monotonic_values)
    ):
        client.search_lots("GB5", 2017)
        client.search_lots("GB5", 2017)

    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(1.5)


def test_client_fetches_lot_detail_and_chassis_image() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "chassis" in str(request.url):
            return httpx.Response(200, content=b"jpeg-bytes")
        return httpx.Response(200, text=_authed(_fixture("lot_detail_freed.html")))

    client = _client(handler, username="u", password="p")
    detail = client.get_lot_detail("981967852")
    assert detail.scores == "R"
    assert client.fetch_chassis_image(detail) == b"jpeg-bytes"


def test_client_fetch_chassis_image_requires_url() -> None:
    client = _client(lambda _r: httpx.Response(200), username="u", password="p")
    detail = parse_lot_detail(_fixture("lot_detail_freed.html"))
    broken = type(detail)(**{**detail.__dict__, "chassis_image_url": None})
    with pytest.raises(AleadoParseError):
        client.fetch_chassis_image(broken)


# --- service: rules ---------------------------------------------------------


@pytest.fixture
def freed_lot(user_factory, db) -> Lot:
    user = user_factory(email="aleado@example.com")
    return Lot.objects.create(
        user=user,
        make="HONDA",
        model="FREED",
        model_code="GB5",
        frame_id="GB5-1025108",
        frame_id_confidence="exact",
        first_reg_year=2017,
        mileage_km=25000,
        overall_grade="4",
        lot_number="10034",
        auction_house="MIRIVE",
        auction_branch="Saitama",
    )


def test_clean_model_code_variants(freed_lot: Lot) -> None:
    assert clean_model_code(freed_lot) == "GB5"
    freed_lot.frame_id = None
    freed_lot.model_code = "6BA-GB5"
    assert clean_model_code(freed_lot) == "GB5"
    freed_lot.model_code = "DAA-RU3"
    assert clean_model_code(freed_lot) == "RU3"
    freed_lot.model_code = None
    freed_lot.frame_id = "NRE210-2005418"
    assert clean_model_code(freed_lot) == "NRE210"


def test_rule_grade_regression_is_critical(freed_lot: Lot) -> None:
    alerts = _evaluate_rules(freed_lot, [_verified_row(grade="R", mileage_km=25000)])

    assert alerts[0].type == "grade_regression"
    assert alerts[0].severity == "critical"
    assert "TAA Hiroshima" in alerts[0].message_ru
    assert alerts[0].diff_details["chassis_match"] == "chassis_image_verified"


def test_rule_odometer_rollback_is_critical(freed_lot: Lot) -> None:
    alerts = _evaluate_rules(freed_lot, [_verified_row(grade="4", mileage_km=130000)])

    assert alerts[0].type == "odometer_rollback"
    assert alerts[0].severity == "critical"
    assert alerts[0].diff_details["past_mileage_km"] == 130000
    assert alerts[0].diff_details["current_mileage_km"] == 25000


def test_rule_grade_inflation_is_warning(freed_lot: Lot) -> None:
    alerts = _evaluate_rules(freed_lot, [_verified_row(grade="3.5", mileage_km=25000)])

    assert alerts[0].type == "grade_inflation"
    assert alerts[0].severity == "warning"


def test_rule_clean_history_has_no_alerts(freed_lot: Lot) -> None:
    assert _evaluate_rules(freed_lot, [_verified_row(grade="4", mileage_km=24000)]) == []


def test_rule_repaired_grade_with_numeric_past_is_regression(freed_lot: Lot) -> None:
    alerts = _evaluate_rules(freed_lot, [_verified_row(grade="RA", mileage_km=25000)])
    assert alerts[0].type == "grade_regression"


# --- service: outcome assembly ----------------------------------------------


def test_outcome_critical_status(freed_lot: Lot) -> None:
    alerts = _evaluate_rules(freed_lot, [_verified_row(grade="R", mileage_km=25000)])
    outcome = _build_outcome([_verified_row(grade="R")], alerts, includes_own_lot=False)

    assert outcome.status == CrossAuditStatus.ANOMALY_DETECTED
    assert outcome.risk_level == RiskLevel.CRITICAL
    assert outcome.has_critical_anomaly is True
    assert outcome.times_auctioned == 1


def test_outcome_warning_status(freed_lot: Lot) -> None:
    alerts = _evaluate_rules(freed_lot, [_verified_row(grade="3.5", mileage_km=25000)])
    outcome = _build_outcome([_verified_row(grade="3.5")], alerts, includes_own_lot=False)

    assert outcome.status == CrossAuditStatus.LIVE_ONLY
    assert outcome.risk_level == RiskLevel.WARNING
    assert outcome.has_critical_anomaly is False


def test_outcome_info_status(freed_lot: Lot) -> None:
    outcome = _build_outcome([_verified_row(grade="4")], [], includes_own_lot=False)

    assert outcome.status == CrossAuditStatus.LIVE_ONLY
    assert outcome.risk_level == RiskLevel.INFO
    assert outcome.has_critical_anomaly is False
    assert outcome.times_auctioned == 1
    assert outcome.history[0].auction_house == "TAA Hiroshima"
    assert outcome.history[0].closing_price_jpy == 100000


def test_outcome_empty_history_mentions_candidates_checked(freed_lot: Lot) -> None:
    outcome = _build_outcome([], [], includes_own_lot=False, candidates_checked=3)

    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert outcome.risk_level == RiskLevel.INFO
    assert outcome.times_auctioned == 0
    assert "проверено 3" in outcome.headline_ru


def test_outcome_future_verified_mentions_catalog(freed_lot: Lot) -> None:
    outcome = _build_outcome(
        [], [], includes_own_lot=False, future_verified_count=1, candidates_checked=2
    )

    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert "текущем каталоге Aleado" in outcome.headline_ru


def test_outcome_mentions_own_lot_in_catalog(freed_lot: Lot) -> None:
    outcome = _build_outcome([_verified_row()], [], includes_own_lot=True)
    assert "Aleado" in outcome.headline_ru


# --- service: full audit ----------------------------------------------------


_OWN_INTERNAL_ID = "981967852"  # lot 10034 MIRIVE Saitama (the audited lot)


def _search_handler(
    fixture: str, *, detail_fixture: str | None = None, detail_ids: set[str] | None = None
):
    """Aleado transport serving the search fixture and lot detail pages.

    ``detail_ids`` limits which internal ids get a detail page; chassis
    images are always served as tiny fake JPEGs.
    """
    detail_ids = detail_ids if detail_ids is not None else set(detail_ids or [])
    detail_requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "chassis" in url:
            return httpx.Response(200, content=b"fake-jpeg-bytes")
        if "p=project/lot" in url or "p=project%2Flot" in url:
            internal_id = url.split("id=")[-1].split("&")[0]
            detail_requests.append(internal_id)
            if internal_id not in detail_ids:
                return httpx.Response(200, text=_authed(_fixture(fixture)))
            return httpx.Response(
                200, text=_authed(_fixture(detail_fixture or "lot_detail_freed.html"))
            )
        return httpx.Response(200, text=_authed(_fixture(fixture)))

    handler.detail_requests = detail_requests  # type: ignore[attr-defined]
    return handler


def _service(
    fixture: str = "search_gb5_2017.html",
    ml_client: MlServiceClient | None = None,
    *,
    detail_fixture: str | None = None,
    detail_ids: set[str] | None = None,
) -> tuple[AleadoCrossAuditService, list[str]]:
    """Build a service whose Aleado transport counts detail requests."""
    handler = _search_handler(fixture, detail_fixture=detail_fixture, detail_ids=detail_ids)
    client = AleadoClient(
        username="test_account_id",
        password="secret",
        transport=httpx.MockTransport(handler),
    )
    service = AleadoCrossAuditService(client=client, ml_client=ml_client)
    return service, handler.detail_requests  # type: ignore[attr-defined]


def _service_with(
    ml_frame_id: str | None = "GB5-1025108",
    *,
    fixture: str = "search_gb5_2017.html",
    detail_fixture: str | None = None,
    detail_ids: set[str] | None = None,
    ml_client: MlServiceClient | None = None,
) -> tuple[AleadoCrossAuditService, list[str]]:
    """Build a service with a mock ML client returning ``ml_frame_id``."""
    if ml_client is None and ml_frame_id is not None:
        ml_client = _ml_client_with_chassis_read(ml_frame_id)
    return _service(fixture, ml_client, detail_fixture=detail_fixture, detail_ids=detail_ids)


@pytest.mark.django_db
def test_audit_lot_builds_history_and_persists(freed_lot: Lot) -> None:
    # The search fixture carries no chassis-matching cars; with chassis
    # verification nothing can be confirmed as history. A dedicated
    # scenario below (test_audit_lot_verifies_matching_chassis) covers
    # the verified-history path.
    service, detail_requests = _service_with(ml_frame_id=None)
    outcome = service.audit_lot(freed_lot)

    assert outcome.times_auctioned == 0
    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert outcome.risk_level == RiskLevel.INFO
    assert outcome.is_archive_available is True
    assert "проверено" in outcome.headline_ru
    assert len(detail_requests) > 0

    audit = CrossAuditReport.objects.get(lot=freed_lot)
    assert audit.source_name == "Aleado.com"
    assert audit.status == CrossAuditStatus.NOT_FOUND
    assert audit.times_auctioned == 0
    assert audit.history.count() == 0
    assert freed_lot.has_anomaly is False


@pytest.mark.django_db
def test_audit_lot_verifies_matching_chassis(freed_lot: Lot) -> None:
    """A candidate whose chassis image matches the lot frame id becomes history."""
    # distance-sorted first candidate gets a detail page whose chassis
    # OCR matches the audited frame id.
    service, detail_requests = _service_with(ml_frame_id="GB5-1025108")
    outcome = service.audit_lot(freed_lot)

    # All 4 non-own candidates verified as the same chassis -> history,
    # but they are future-dated (current catalog), so headline mentions
    # the catalog and no rules fired on them.
    assert outcome.times_auctioned == 0
    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert "текущем каталоге Aleado" in outcome.headline_ru
    assert len(detail_requests) == 4

    audit = CrossAuditReport.objects.get(lot=freed_lot)
    assert audit.history.count() == 0


@pytest.mark.django_db
def test_audit_lot_verified_past_history_triggers_rules(freed_lot: Lot) -> None:
    """Verified past rows feed history and anomaly rules."""
    past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "chassis" in url:
            return httpx.Response(200, content=b"fake-jpeg-bytes")
        if "p=project/lot" in url or "p=project%2Flot" in url:
            return httpx.Response(200, text=_authed(_fixture("lot_detail_freed.html")))
        html = _fixture("search_gb5_2017.html").replace("2026-11-17 00:00:00", past_date)
        return httpx.Response(200, text=_authed(html))

    client = AleadoClient(username="u", password="p", transport=httpx.MockTransport(handler))
    service = AleadoCrossAuditService(
        client=client, ml_client=_ml_client_with_chassis_read("GB5-1025108")
    )
    outcome = service.audit_lot(freed_lot)

    # The past TAA Hiroshima row (78 000 km vs our 25 000 km) is
    # chassis-verified and triggers the odometer rollback rule.
    assert outcome.times_auctioned == 1
    assert outcome.status == CrossAuditStatus.ANOMALY_DETECTED
    assert outcome.has_critical_anomaly is True
    assert outcome.anomalies[0].type == "odometer_rollback"
    assert outcome.anomalies[0].diff_details["chassis_match"] == "chassis_image_verified"
    assert freed_lot.has_anomaly is True

    audit = CrossAuditReport.objects.get(lot=freed_lot)
    assert audit.history.count() == 1
    assert audit.history.first().auction_house == "TAA Hiroshima"


@pytest.mark.django_db
def test_audit_lot_not_found_when_search_is_empty(freed_lot: Lot) -> None:
    empty_html = (
        "<html><body>Sign out</body>"
        '<div class="Header2">Found total lots: <b><font color="red">0</font></b>'
        "</body></html>"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=empty_html)

    client = AleadoClient(username="u", password="p", transport=httpx.MockTransport(handler))
    outcome = AleadoCrossAuditService(
        client=client, ml_client=_ml_client_with_chassis_read("GB5-1025108")
    ).audit_lot(freed_lot)

    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert outcome.risk_level == RiskLevel.INFO
    assert outcome.times_auctioned == 0
    report = CrossAuditReport.objects.get(lot=freed_lot)
    assert report.status == CrossAuditStatus.NOT_FOUND
    assert report.history.count() == 0


@pytest.mark.django_db
def test_audit_lot_marks_unavailable_on_source_failure(freed_lot: Lot) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Access denied</html>")

    client = AleadoClient(username="u", password="p", transport=httpx.MockTransport(handler))
    outcome = AleadoCrossAuditService(
        client=client, ml_client=_ml_client_with_chassis_read("GB5-1025108")
    ).audit_lot(freed_lot)

    assert outcome.status == CrossAuditStatus.UNAVAILABLE
    assert outcome.is_archive_available is False


@pytest.mark.django_db
def test_audit_lot_without_model_code_is_unavailable(freed_lot: Lot) -> None:
    freed_lot.frame_id = None
    freed_lot.model_code = None
    service, _detail_requests = _service()
    outcome = service.audit_lot(freed_lot)

    assert outcome.status == CrossAuditStatus.UNAVAILABLE


# --- service: chassis verification scenarios --------------------------------


@pytest.mark.django_db
def test_audit_lot_candidate_chassis_mismatch_is_not_history(freed_lot: Lot) -> None:
    """A candidate whose OCR chassis differs is excluded from history."""
    service, _detail_requests = _service_with(ml_frame_id="GB5-9999999")
    outcome = service.audit_lot(freed_lot)

    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert outcome.times_auctioned == 0
    report = CrossAuditReport.objects.get(lot=freed_lot)
    assert report.history.count() == 0


@pytest.mark.django_db
def test_audit_lot_grade_regression_on_verified_past_is_critical(freed_lot: Lot) -> None:
    """Chassis-verified past R-grade row triggers the CRITICAL rule."""
    past_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "chassis" in url:
            return httpx.Response(200, content=b"fake-jpeg-bytes")
        if "p=project/lot" in url or "p=project%2Flot" in url:
            return httpx.Response(200, text=_authed(_fixture("lot_detail_freed.html")))
        html = _fixture("search_gb5_2017.html").replace("2026-11-17 00:00:00", past_date)
        return httpx.Response(200, text=_authed(html))

    client = AleadoClient(username="u", password="p", transport=httpx.MockTransport(handler))
    service = AleadoCrossAuditService(
        client=client, ml_client=_ml_client_with_chassis_read("GB5-1025108")
    )
    outcome = service.audit_lot(freed_lot)

    assert outcome.status == CrossAuditStatus.ANOMALY_DETECTED
    assert outcome.risk_level == RiskLevel.CRITICAL


@pytest.mark.django_db
def test_audit_lot_unreadable_chassis_keeps_candidate_unverified(freed_lot: Lot) -> None:
    """OCR returning None/unreadable leaves the candidate unverified."""
    service, detail_requests = _service_with(ml_frame_id=None)
    outcome = service.audit_lot(freed_lot)

    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert outcome.times_auctioned == 0
    # Detail pages were still fetched for every candidate.
    assert len(detail_requests) == 4
    assert CrossAuditReport.objects.get(lot=freed_lot).history.count() == 0


@pytest.mark.django_db
def test_audit_lot_ml_client_failure_continues_audit(freed_lot: Lot) -> None:
    """An ML service outage keeps candidates unverified but does not fail the audit."""
    service, _detail_requests = _service_with(ml_client=_ml_client_failing())
    outcome = service.audit_lot(freed_lot)

    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert outcome.times_auctioned == 0
    report = CrossAuditReport.objects.get(lot=freed_lot)
    assert report.status == CrossAuditStatus.NOT_FOUND


@pytest.mark.django_db
def test_audit_lot_future_verified_date_mentions_catalog(freed_lot: Lot) -> None:
    """Verified future-dated rows are catalog presence, not history."""
    service, _detail_requests = _service_with(ml_frame_id="GB5-1025108")
    outcome = service.audit_lot(freed_lot)

    # All fixture rows are future-dated (2026-11-14..18 > now).
    assert outcome.times_auctioned == 0
    assert outcome.status == CrossAuditStatus.NOT_FOUND
    assert "текущем каталоге Aleado" in outcome.headline_ru
    assert CrossAuditReport.objects.get(lot=freed_lot).history.count() == 0


@pytest.mark.django_db
def test_audit_lot_candidate_without_internal_id_is_unverified(freed_lot: Lot) -> None:
    """Rows without an internal id are skipped without a detail request."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "chassis" in url:
            return httpx.Response(200, content=b"fake-jpeg-bytes")
        if "p=project/lot" in url or "p=project%2Flot" in url:
            return httpx.Response(200, text=_authed(_fixture("lot_detail_freed.html")))
        html = _fixture("search_gb5_2017.html").replace("id=981962227", "id=")
        return httpx.Response(200, text=_authed(html))

    client = AleadoClient(username="u", password="p", transport=httpx.MockTransport(handler))
    service = AleadoCrossAuditService(
        client=client, ml_client=_ml_client_with_chassis_read("GB5-1025108")
    )
    outcome = service.audit_lot(freed_lot)

    # No candidate verified (own lot excluded, others future-dated but
    # the id-less TAA row could never be verified).
    assert outcome.times_auctioned == 0


@pytest.mark.django_db
def test_audit_lot_verification_limit_caps_detail_requests(freed_lot: Lot, settings) -> None:
    """Only ALEADO_VERIFY_CANDIDATES candidates get detail requests."""
    settings.ALEADO_VERIFY_CANDIDATES = 3

    # Build a search page with 12 candidate rows (plus the own lot).
    rows_html_parts = []
    for index in range(1, 13):
        mileage = 30000 + index * 1000
        rows_html_parts.append(
            f'<div id="priceLotS{index}" style="display:none">100</div>'
            f'<tr class="ColorGreed2" id="cell_{index}">'
            f'<td id="date_{index}">2026-11-10 00:00:00</td>'
            f'<td id="bid_number_{index}">'
            f'<a href="/auctions/?p=project/lot&amp;id=99{index:02d}"><b>{index}</b></a></td>'
            f'<td id="auction_{index}">USS Tokyo</td>'
            f'<td id="model_{index}">FREED</td>'
            f'<td id="grade_{index}">4</td>'
            f'<td id="year_{index}">2017</td>'
            f'<td id="mileage_{index}">{mileage}</td>'
            f'<td id="displacement_{index}">1500cc</td>'
            f'<td id="model_type_{index}">GB5</td>'
            f'<td id="result_{index}">sold</td>'
            f'<td id="scores_{index}">4</td></tr>'
        )
    html = (
        "<html><body>Sign out</body>"
        '<div class="Header2">Found total lots: <b><font color="red">12</font></b>'
        + "".join(rows_html_parts)
        + "</body></html>"
    )

    detail_requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "chassis" in url:
            return httpx.Response(200, content=b"fake-jpeg-bytes")
        if "p=project/lot" in url or "p=project%2Flot" in url:
            internal_id = url.split("id=")[-1].split("&")[0]
            detail_requests.append(internal_id)
            return httpx.Response(200, text=_authed(_fixture("lot_detail_freed.html")))
        return httpx.Response(200, text=html)

    client = AleadoClient(username="u", password="p", transport=httpx.MockTransport(handler))
    service = AleadoCrossAuditService(
        client=client, ml_client=_ml_client_with_chassis_read("GB5-1025108")
    )
    outcome = service.audit_lot(freed_lot)

    # 12 candidates, only 3 closest by mileage verified. All verified
    # rows are past-dated -> 3 history records.
    assert len(detail_requests) == 3
    assert outcome.times_auctioned == 3


# --- pipeline fallback ------------------------------------------------------


@pytest.fixture
def pipeline_batch_item(user_factory, db) -> BatchItem:
    user = user_factory(email="pipeline-aleado@example.com")
    batch = Batch.objects.create(user=user, status=BatchStatus.PROCESSING)
    lot = Lot.objects.create(
        user=user,
        model_code="GB5",
        first_reg_year=2017,
        mileage_km=25000,
        overall_grade="4",
        lot_number="10034",
    )
    item = BatchItem.objects.create(
        batch=batch,
        lot=lot,
        file_index=0,
        original_filename="sheet.png",
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.CROSS_AUDIT,
    )
    item.original_file.save("sheet.png", ContentFile(b"fake-png-bytes"), save=True)
    item.refresh_from_db()
    return item


@pytest.mark.django_db
def test_pipeline_cross_audit_falls_back_to_baseline_on_aleado_failure(
    pipeline_batch_item: BatchItem,
) -> None:
    with patch("apps.lots.pipeline.AleadoCrossAuditService") as service_cls:
        service_cls.return_value.audit_lot.side_effect = AleadoUnavailableError("site down")
        assert _step_cross_audit(pipeline_batch_item) is True

    audit = CrossAuditReport.objects.get(lot=pipeline_batch_item.lot)
    assert audit.status == CrossAuditStatus.NOT_FOUND
    assert audit.times_auctioned == 0
    assert pipeline_batch_item.status == ItemProcessingStatus.PROCESSING


@pytest.mark.django_db
def test_pipeline_cross_audit_delegates_to_aleado(pipeline_batch_item: BatchItem) -> None:
    with patch("apps.lots.pipeline.AleadoCrossAuditService") as service_cls:
        assert _step_cross_audit(pipeline_batch_item) is True
    service_cls.return_value.audit_lot.assert_called_once()


# --- settings regression ----------------------------------------------------


def test_settings_export_aleado_options() -> None:
    from django.conf import settings as django_settings

    assert hasattr(django_settings, "ALEADO_USERNAME")
    assert hasattr(django_settings, "ALEADO_PASSWORD")
    assert hasattr(django_settings, "ALEADO_BASE_URL")
    assert hasattr(django_settings, "ALEADO_TIMEOUT_SEC")
    assert hasattr(django_settings, "ALEADO_REQUEST_INTERVAL_SEC")
    assert hasattr(django_settings, "ALEADO_VERIFY_CANDIDATES")


def test_app_settings_aleado_defaults() -> None:
    settings_obj = AppSettings(_env_file=None)
    assert settings_obj.ALEADO_BASE_URL == "https://auc.aleado.com"
    assert settings_obj.ALEADO_REQUEST_INTERVAL_SEC > 0
    assert settings_obj.ALEADO_TIMEOUT_SEC > 0
    assert settings_obj.ALEADO_VERIFY_CANDIDATES == 10


def test_app_settings_aleado_rejects_invalid_numbers() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AppSettings(_env_file=None, ALEADO_TIMEOUT_SEC=0)
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None, ALEADO_REQUEST_INTERVAL_SEC=-1)


@pytest.mark.django_db
def test_chassis_image_url_outside_allowlist_is_blocked(_make_batch_item=None) -> None:
    """SSRF guard: chassis URLs from parsed HTML must be allowlisted."""
    from apps.lots.integrations.aleado.client import (
        AleadoClient,
        AleadoParseError,
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "chassis" in str(request.url):
            return httpx.Response(200, content=b"\xff\xd8fakejpeg")
        return httpx.Response(200, content=_fixture("lot_detail_freed.html"))

    client = AleadoClient(
        base_url="https://auc.aleado.com",
        username="test_account_id",
        password="secret",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _s: None,
    )
    detail = client.get_lot_detail("981966376")
    assert detail.chassis_image_url is not None

    # Rewrite the URL to an internal address, as a compromised page would.
    evil = dataclasses.replace(detail, chassis_image_url="http://169.254.169.254/latest/meta-data/")
    with pytest.raises(AleadoParseError):
        client.fetch_chassis_image(evil)

    # The allowlisted https host still works.
    good = dataclasses.replace(detail, chassis_image_url="https://p3.aleado.com/chassis/ok")
    assert client.fetch_chassis_image(good) == b"\xff\xd8fakejpeg"
    assert calls[-1] == "https://p3.aleado.com/chassis/ok"


@pytest.mark.django_db
def test_oversized_html_response_is_rejected() -> None:
    """DoS guard: responses beyond the size cap must not reach the parser."""
    from apps.lots.integrations.aleado.client import AleadoUnavailableError

    def handler(_request: httpx.Request) -> httpx.Response:
        # Content-Length above the 3 MB HTML cap.
        return httpx.Response(
            200,
            headers={"Content-Length": str(5 * 1024 * 1024)},
            content=b"x",
        )

    client = AleadoClient(
        base_url="https://auc.aleado.com",
        username="test_account_id",
        password="secret",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _s: None,
    )
    with pytest.raises(AleadoUnavailableError):
        client.search_lots("GB5", 2017)


@pytest.mark.django_db
def test_photo_url_from_untrusted_host_is_dropped() -> None:
    """Stored-XSS guard: non-allowlisted photo URLs must not reach the DB."""
    from datetime import datetime

    from apps.lots.integrations.aleado.parser import AleadoLotRow
    from apps.lots.integrations.aleado.service import _build_outcome, _VerifiedRow

    past_row = AleadoLotRow(
        trading_date=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        lot_number="222",
        auction_house="TAA Hiroshima",
        model_name="HONDA FREED G",
        grade="R",
        year=2017,
        mileage_km=78000,
        displacement_cc=1500,
        transmission="IAT",
        color="RED",
        model_type="GB5",
        start_price_jpy=100_000,
        result="1",
        internal_id="111",
        photo_url="javascript:alert(1)",
    )
    outcome = _build_outcome(
        [_VerifiedRow(row=past_row)],
        [],
        includes_own_lot=False,
    )
    assert outcome.history[0].sheet_archive_url is None

    safe_row = dataclasses.replace(past_row, photo_url="https://p3.aleado.com/image/auto/1.jpg")
    outcome = _build_outcome(
        [_VerifiedRow(row=safe_row)],
        [],
        includes_own_lot=False,
    )
    assert outcome.history[0].sheet_archive_url == "https://p3.aleado.com/image/auto/1.jpg"
