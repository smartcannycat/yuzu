"""Lots domain models package.

Upload path helpers remain defined in this package module so historical migration
``0001_initial`` deconstruct paths (``apps.lots.models.*_upload_to``) stay unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.lots.models.batch import BatchItem as _BatchItem
    from apps.lots.models.lot import Lot as _Lot


def _batch_item_upload_to(instance: _BatchItem, filename: str) -> str:
    return f"batches/{instance.batch_id}/{filename}"


def _lot_scan_upload_to(instance: _Lot, filename: str) -> str:
    return f"lots/{instance.id or 'temp'}/scans/{filename}"


def _lot_thumb_upload_to(instance: _Lot, filename: str) -> str:
    return f"lots/{instance.id or 'temp'}/thumbs/{filename}"


from apps.lots.models.audit import (  # noqa: E402
    AnomalyAlert,
    CrossAuditReport,
    MarketComparisonInfo,
    PastAuctionRecord,
    SafetyCheckItem,
    SafetyChecklist,
)
from apps.lots.models.batch import Batch, BatchItem  # noqa: E402
from apps.lots.models.customs import (  # noqa: E402
    CurrencyRatesSnapshot,
    CustomsCalculation,
    WiseCostLadder,
    WiseCostStep,
)
from apps.lots.models.lot import Lot, LotDefect, LotRiskFlags, TrafficLightVerdict  # noqa: E402
from apps.lots.models.repairs import (  # noqa: E402
    DamagedPartItem,
    FarpostRepairSummary,
    ServiceWorkItem,
)

__all__ = [
    "AnomalyAlert",
    "Batch",
    "BatchItem",
    "CrossAuditReport",
    "CurrencyRatesSnapshot",
    "CustomsCalculation",
    "DamagedPartItem",
    "FarpostRepairSummary",
    "Lot",
    "LotDefect",
    "LotRiskFlags",
    "MarketComparisonInfo",
    "PastAuctionRecord",
    "SafetyCheckItem",
    "SafetyChecklist",
    "ServiceWorkItem",
    "TrafficLightVerdict",
    "WiseCostLadder",
    "WiseCostStep",
    "_batch_item_upload_to",
    "_lot_scan_upload_to",
    "_lot_thumb_upload_to",
]
