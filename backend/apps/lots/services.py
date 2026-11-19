"""Public facade for the lots domain services."""

from apps.integrations.drom import DromMarketService
from apps.lots.api.batches import (
    append_batch_items,
    create_batch,
    get_batch_progress,
)
from apps.lots.api.queries import (
    _build_customs_out,
    _build_lot_detail,
    _build_lot_summary,
    bulk_delete_lots,
    get_lot_detail,
    get_lot_media_response,
    get_lots_list,
    recalculate_lot,
    reset_lot_simulation,
    update_lot_lifecycle,
)
from apps.lots.calculator.economics import (
    _missing_customs_inputs,
    _resolve_start_bid_jpy,
    recompute_lot_economics,
)
from apps.lots.lifecycle import (
    archive_expired_lots_for_user,
    compute_lot_expires_at,
    delete_lot,
)
from apps.lots.pipeline import (
    _step_drom_market,
    recover_batches_on_startup,
    run_batch_pipeline,
)
from apps.lots.starter_lots import (
    backfill_starter_lots,
    seed_starter_lots,
)

__all__ = [
    "DromMarketService",
    "_build_customs_out",
    "_build_lot_detail",
    "_build_lot_summary",
    "_missing_customs_inputs",
    "_resolve_start_bid_jpy",
    "_step_drom_market",
    "append_batch_items",
    "archive_expired_lots_for_user",
    "backfill_starter_lots",
    "bulk_delete_lots",
    "compute_lot_expires_at",
    "create_batch",
    "delete_lot",
    "get_batch_progress",
    "get_lot_detail",
    "get_lot_media_response",
    "get_lots_list",
    "recalculate_lot",
    "recompute_lot_economics",
    "recover_batches_on_startup",
    "reset_lot_simulation",
    "run_batch_pipeline",
    "seed_starter_lots",
    "update_lot_lifecycle",
]
