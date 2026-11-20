"""Domain exceptions for the lots bounded context (HTTP-agnostic)."""

from __future__ import annotations


class LotDomainError(Exception):
    """Base domain exception raised by lots business logic and lifecycle operations."""

    def __init__(self, detail: str, *, title: str | None = None) -> None:
        self.detail = detail
        self.title = title or detail
        super().__init__(detail)


class LotNotFoundDomainError(LotDomainError):
    """Raised when an owned completed lot does not exist or was deleted."""


class RecalcDomainError(LotDomainError):
    """Raised when recalculation or simulation reset cannot proceed."""
