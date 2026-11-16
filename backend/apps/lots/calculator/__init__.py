"""Pure financial calculation, scoring, safety checklist, and simulation package."""

from apps.lots.calculator.baseline import (
    DEFAULT_BID_SLIDER_MAX_JPY,
    DEFAULT_BID_SLIDER_MIN_JPY,
    EV_MISSING_POWER_WARNING,
    MAX_DYNAMIC_BID_SLIDER_MAX_JPY,
    StoredRatesSnapshot,
    build_baseline_snapshot,
    compute_bid_slider_max_jpy,
    ensure_dynamic_bid_slider_max,
    ensure_lot_baseline,
    extract_rates,
    is_simulation_modified,
)
from apps.lots.calculator.customs import (
    CurrencyRatesInput,
    CustomsInput,
    CustomsResult,
    LadderInput,
    LadderResult,
    StartBidInput,
    StartBidResult,
    build_wise_cost_ladder,
    calculate_customs,
    derive_start_bid_from_market,
    meti_sanction_risk,
)
from apps.lots.calculator.economics import (
    _missing_customs_inputs,
    _resolve_start_bid_jpy,
    recompute_lot_economics,
)
from apps.lots.calculator.recalc import (
    RecalcOutcome,
    execute_recalculate,
    execute_reset_simulation,
)
from apps.lots.calculator.safety import build_cross_audit_baseline, build_safety_checklist
from apps.lots.calculator.scoring import compute_verdict

__all__ = [
    "DEFAULT_BID_SLIDER_MAX_JPY",
    "DEFAULT_BID_SLIDER_MIN_JPY",
    "EV_MISSING_POWER_WARNING",
    "MAX_DYNAMIC_BID_SLIDER_MAX_JPY",
    "CurrencyRatesInput",
    "CustomsInput",
    "CustomsResult",
    "LadderInput",
    "LadderResult",
    "RecalcOutcome",
    "StartBidInput",
    "StartBidResult",
    "StoredRatesSnapshot",
    "_missing_customs_inputs",
    "_resolve_start_bid_jpy",
    "build_baseline_snapshot",
    "build_cross_audit_baseline",
    "build_safety_checklist",
    "build_wise_cost_ladder",
    "calculate_customs",
    "compute_bid_slider_max_jpy",
    "compute_verdict",
    "derive_start_bid_from_market",
    "ensure_dynamic_bid_slider_max",
    "ensure_lot_baseline",
    "execute_recalculate",
    "execute_reset_simulation",
    "extract_rates",
    "is_simulation_modified",
    "meti_sanction_risk",
    "recompute_lot_economics",
]
