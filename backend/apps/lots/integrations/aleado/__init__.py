"""Aleado.com cross-audit integration (BE-08).

Searches past auctions of the same model code (body type) on Aleado and
builds a real cross-audit report with trading history and anomaly alerts.
"""

from apps.lots.integrations.aleado.client import (
    AleadoAuthError,
    AleadoClient,
    AleadoParseError,
    AleadoUnavailableError,
)
from apps.lots.integrations.aleado.parser import AleadoLotDetail, AleadoLotRow
from apps.lots.integrations.aleado.service import AleadoCrossAuditService, CrossAuditOutcome

__all__ = [
    "AleadoAuthError",
    "AleadoClient",
    "AleadoCrossAuditService",
    "AleadoLotDetail",
    "AleadoLotRow",
    "AleadoParseError",
    "AleadoUnavailableError",
    "CrossAuditOutcome",
]
