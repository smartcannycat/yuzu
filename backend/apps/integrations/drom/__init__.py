from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.integrations.drom.service import DromMarketService

__all__ = ["DromMarketService"]


def __getattr__(name: str) -> Any:
    if name == "DromMarketService":
        from apps.integrations.drom.service import DromMarketService

        return DromMarketService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
