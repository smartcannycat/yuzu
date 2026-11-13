from dataclasses import dataclass, field


class DromFetchError(RuntimeError):
    """Raised when an HTTP request to Drom fails unexpectedly."""


class DromBlockedError(DromFetchError):
    """Raised when Drom / QRATOR rejects requests with 403 or 429."""


class DromNotFoundError(DromFetchError):
    """Raised when a Drom listing or catalog URL returns HTTP 404."""


@dataclass(frozen=True, slots=True)
class DromSearchCriteria:
    make: str
    model: str
    year: int | None = None
    engine_cc: int | None = None
    drive_type: str | None = None
    transmission: str | None = None
    fuel_type: str | None = None
    model_code: str | None = None


@dataclass(frozen=True, slots=True)
class DromListing:
    bull_id: str | None
    title: str
    price_rub: int
    url: str | None = None
    description: str = ""
    location: str = ""
    sold: bool = False
    car_state: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    is_nearby_city: bool = False


@dataclass(frozen=True, slots=True)
class DromCatalogSpec:
    model_code: str
    power_hp: int
    engine_cc: int | None = None
    fuel_type: str | None = None
    drive_type: str | None = None
    year_start: int | None = None
    year_end: int | None = None


@dataclass(frozen=True, slots=True)
class DromPowerResult:
    power_hp: int | None
    power_hp_source: str | None

    @property
    def is_under_160_hp(self) -> bool | None:
        if self.power_hp is None:
            return None
        return self.power_hp <= 160


@dataclass(frozen=True, slots=True)
class DromMarketResult:
    market_price_rf_rub: int
    analogs_count: int
    price_min_rub: int | None
    price_max_rub: int | None
    search_region_ru: str
    excludes_under_order: bool
    filtered_out_under_order_count: int
    is_fallback: bool
    fallback_reason_ru: str | None
    drom_search_url: str
    power_hp: int | None = None
    power_hp_source: str | None = None
    is_under_160_hp: bool | None = None
