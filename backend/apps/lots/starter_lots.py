"""Seed real parsed benchmark lots for newly registered users."""

import json
from copy import deepcopy
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.lots.lifecycle import compute_lot_expires_at
from apps.lots.media import attach_starter_sheet_media
from apps.lots.models import (
    AnomalyAlert,
    CrossAuditReport,
    CurrencyRatesSnapshot,
    CustomsCalculation,
    DamagedPartItem,
    FarpostRepairSummary,
    Lot,
    LotDefect,
    LotRiskFlags,
    MarketComparisonInfo,
    PastAuctionRecord,
    SafetyCheckItem,
    SafetyChecklist,
    ServiceWorkItem,
    TrafficLightVerdict,
    WiseCostLadder,
    WiseCostStep,
)
from apps.users.models import User

_STARTER_DATA_PATH = Path(__file__).resolve().parent / "starter_assets" / "starter_lots.json"


def _parse_iso_date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


@lru_cache
def _load_starter_fixtures() -> dict[tuple[str, str], dict[str, Any]]:
    raw: dict[str, dict[str, Any]] = json.loads(_STARTER_DATA_PATH.read_text(encoding="utf-8"))
    fixtures: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in raw.values():
        item = deepcopy(entry)
        lot_fields = item["lot_fields"]
        lot_fields["auction_date"] = _parse_iso_date(lot_fields.get("auction_date"))
        for record in item.get("audit_history") or []:
            record["auction_date"] = _parse_iso_date(record.get("auction_date"))
        fixtures[(lot_fields["make"], lot_fields["model"])] = item
    return fixtures


_STARTER_FIXTURES: dict[tuple[str, str], dict[str, Any]] = _load_starter_fixtures()


def _create_lot_relations(
    lot: Lot,
    now,
    *,
    fixture: dict[str, Any],
    customs_model=CustomsCalculation,
) -> None:
    for defect_data in fixture.get("defects") or []:
        LotDefect.objects.create(lot=lot, **defect_data)

    LotRiskFlags.objects.create(lot=lot, **fixture["risk_flags"])
    TrafficLightVerdict.objects.create(lot=lot, **fixture["verdict"])
    MarketComparisonInfo.objects.create(lot=lot, **fixture["market"])

    audit_obj = CrossAuditReport.objects.create(lot=lot, verified_at=now, **fixture["audit"])
    for anomaly_data in fixture.get("audit_anomalies") or []:
        AnomalyAlert.objects.create(audit=audit_obj, **anomaly_data)
    for history_data in fixture.get("audit_history") or []:
        PastAuctionRecord.objects.create(audit=audit_obj, **history_data)

    checklist = SafetyChecklist.objects.create(lot=lot, **fixture["safety"])
    for item_data in fixture.get("safety_items") or []:
        SafetyCheckItem.objects.create(checklist=checklist, **item_data)

    customs_obj = customs_model.objects.create(lot=lot, **fixture["customs"])
    if customs_model is CustomsCalculation:
        CurrencyRatesSnapshot.objects.create(customs=customs_obj, **fixture["rates"])
    else:
        CurrencyRatesSnapshot.objects.create(customs_id=customs_obj.pk, **fixture["rates"])

    repair = FarpostRepairSummary.objects.create(lot=lot, **fixture["farpost"])
    for part_data in fixture.get("farpost_parts") or []:
        DamagedPartItem.objects.create(repair=repair, **part_data)
    for work_data in fixture.get("farpost_works") or []:
        ServiceWorkItem.objects.create(repair=repair, **work_data)

    ladder = WiseCostLadder.objects.create(lot=lot, **fixture["wise_cost"])
    for step_data in fixture.get("wise_cost_steps") or []:
        WiseCostStep.objects.create(ladder=ladder, **step_data)


def _seed_lot_from_fixture(user: User, now, fixture: dict[str, Any]) -> Lot:
    lot_fields = dict(fixture["lot_fields"])
    if not lot_fields.get("auction_bid_jpy") and isinstance(
        lot_fields.get("baseline_economics"), dict
    ):
        bid = lot_fields["baseline_economics"].get("bid_jpy")
        if bid is not None:
            lot_fields["auction_bid_jpy"] = int(bid)
    expires_at = compute_lot_expires_at(now, lot_fields.get("auction_date"))
    lot = Lot.objects.create(
        user=user,
        completed_at=now,
        expires_at=expires_at,
        **lot_fields,
    )
    _create_lot_relations(lot, now, fixture=fixture)
    attach_starter_sheet_media(
        lot,
        scan_file=str(fixture.get("scan_file") or ""),
        thumb_file=str(fixture.get("thumb_file") or ""),
    )
    return lot


def seed_starter_lots(user: User) -> None:
    """Create real parsed starter lots with JPEG auction sheets for a newly registered user."""
    now = timezone.now()
    for fixture in _load_starter_fixtures().values():
        _seed_lot_from_fixture(user, now, fixture)


@transaction.atomic
def backfill_starter_lots(*, defer_fields=(), customs_model=CustomsCalculation) -> int:
    """Repair legacy starter lots missing related detail records."""
    now = timezone.now()
    repaired = 0
    for fixture in _load_starter_fixtures().values():
        fields = fixture["lot_fields"]
        lots = Lot.objects.filter(
            completed_at__isnull=False,
            batch_item__isnull=True,
            verdict_detail__isnull=True,
            make=fields["make"],
            model=fields["model"],
            frame_id=fields["frame_id"],
        )
        for lot in lots.defer(*defer_fields).iterator():
            for field, value in fields.items():
                setattr(lot, field, value)
            lot.save(update_fields=[*fields, "updated_at"])
            _create_lot_relations(
                lot,
                now,
                fixture=fixture,
                customs_model=customs_model,
            )
            if not lot.sheet_scan or not lot.sheet_thumbnail:
                attach_starter_sheet_media(
                    lot,
                    scan_file=str(fixture.get("scan_file") or ""),
                    thumb_file=str(fixture.get("thumb_file") or ""),
                )
            repaired += 1
    return repaired
