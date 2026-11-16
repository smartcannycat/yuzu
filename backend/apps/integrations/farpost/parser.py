"""HTML parsing for Farpost used-parts listings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from scrapling import Selector

from apps.integrations.farpost.matchers import (
    contains_code,
    is_disqualified_listing,
    matches_make_and_model,
    matches_paint_code,
    matches_part_name,
    matches_side_and_position,
)

_MIN_SANE_PART_PRICE_RUB = 1000
_contains_code = contains_code
_matches_paint_code = matches_paint_code

__all__ = [
    "FarpostFetchError",
    "FarpostRateLimitedError",
    "ParseResult",
    "PartCriteria",
    "PartOffer",
    "_contains_code",
    "_matches_paint_code",
    "matches_paint_code",
    "parse_listing_page",
    "parse_offers",
]


class FarpostFetchError(RuntimeError):
    """Source failed, blocked the request or returned unrecognized markup."""


class FarpostRateLimitedError(FarpostFetchError):
    """Source responded with HTTP 403/429 or an anti-bot verification redirect/page."""

    def __init__(self, message: str, *, triggers_global_cooldown: bool = True) -> None:
        super().__init__(message)
        self.triggers_global_cooldown = triggers_global_cooldown


@dataclass(frozen=True)
class PartCriteria:
    make: str
    model: str
    body_code: str
    panel_id: str
    part_name: str
    side: str = ""
    position: str = ""
    paint_code: str = ""

    @property
    def query(self) -> str:
        return " ".join(
            filter(
                None,
                (
                    self.make,
                    self.model,
                    self.body_code,
                    self.part_name,
                    self.side,
                    self.position,
                    self.paint_code,
                ),
            )
        )


@dataclass(frozen=True)
class PartOffer:
    offer_id: str
    url: str
    title: str
    price_rub: int
    color_matched: bool
    snippet: str = ""


@dataclass(frozen=True)
class ParseResult:
    offers: list[PartOffer]
    exact_feed_count: int | None


def _extract_exact_feed_count(page: Selector) -> tuple[int | None, bool]:
    events = page.css("script#ctr-viewdir-event")
    if not events:
        return None, False
    try:
        payload = json.loads(events[0].text or "")
        return int(payload["exactFeedCount"]), True
    except (ValueError, TypeError, KeyError):
        return None, False


def _extract_price_quote(price_node: Selector) -> str:
    data_price = str(price_node.attrib.get("data-price", ""))
    if data_price:
        quoted = Selector(data_price).get_all_text(separator=" ", strip=True)
        if quoted:
            return quoted
    inner = price_node.css('[data-role="price"]')
    if inner:
        return inner[0].get_all_text(separator=" ", strip=True)
    return price_node.get_all_text(separator=" ", strip=True)


def _validate_listing_page(page: Selector, source_url: str) -> tuple[list[Selector], int | None]:
    """Validate challenge/local-stock invariants and return listing row nodes or empty."""
    title_nodes = page.css("title")
    title = title_nodes[0].get_all_text(separator=" ", strip=True) if title_nodes else ""
    body_text = page.get_all_text(separator=" ", strip=True)
    if re.search(r"вы не робот|captcha|подозрительный трафик", f"{title} {body_text}", re.I):
        raise FarpostRateLimitedError("Farpost returned an anti-bot challenge")
    if urlparse(source_url).path.split("/")[1:2] != ["vladivostok"]:
        raise FarpostFetchError("Farpost did not confirm local stock filtering")

    exact_feed_count, event_valid = _extract_exact_feed_count(page)
    local_filter = page.css('input[name="goodPresentState"][value="present"][checked]')
    if not local_filter:
        # When exactFeedCount == 0, Farpost unchecks goodPresentState and shows relaxed suggestions.
        if event_valid and exact_feed_count == 0:
            return [], 0
        raise FarpostFetchError("Farpost did not confirm local stock filtering")

    rows = page.css(".bull-item")
    if not rows:
        if not event_valid:
            raise FarpostFetchError("Unrecognized Farpost listing markup")
        if exact_feed_count == 0:
            return [], 0
        raise FarpostFetchError("Farpost returned no recognizable listing rows")
    return rows, exact_feed_count


def _parse_listing_row(
    row: Selector, criteria: PartCriteria, *, source_url: str
) -> tuple[bool, PartOffer | None]:
    """Return `(is_recognizable_row, offer_or_none)` for a single Farpost feed row."""
    link_nodes = row.css('[data-role="bulletin-link"]')
    if not link_nodes:
        return False, None
    price_nodes = row.css(".price-block__final-price")
    if not price_nodes:
        return True, None
    link = link_nodes[0]
    name = link.get_all_text(separator=" ", strip=True)
    ann_nodes = row.css(".bull-item__annotation") or row.css(".bull-item__annotation-row")
    annotation_text = (
        " ".join(n.get_all_text(separator=" ", strip=True) for n in ann_nodes).strip()
        if ann_nodes
        else ""
    )
    text = f"{name} {annotation_text}".strip()
    url = urljoin(source_url, str(link.attrib.get("href", "")))
    parsed = urlparse(url)
    listing_path = parsed.path.removeprefix("/ni/")
    if not listing_path.startswith("/"):
        listing_path = "/" + listing_path
    if parsed.hostname != "www.farpost.ru" or not listing_path.startswith(
        "/vladivostok/zapchasti/"
    ):
        return True, None
    if is_disqualified_listing(name, text, criteria):
        return True, None
    has_body_code = bool(criteria.body_code and contains_code(text, criteria.body_code))
    if not has_body_code or not matches_make_and_model(
        text, criteria, has_exact_body_code=has_body_code
    ):
        return True, None
    if not matches_part_name(name, criteria) or not matches_side_and_position(name, criteria):
        return True, None
    matched = matches_paint_code(text, criteria.paint_code)
    if criteria.paint_code and not matched:
        return True, None
    quoted = _extract_price_quote(price_nodes[0])
    amount = re.fullmatch(r"\s*([\d\s\xa0]+)\s*₽\s*", quoted)
    if amount is None:
        return True, None
    value = int(re.sub(r"\D", "", amount[1]))
    offer_id = str(row.attrib.get("data-good-id") or row.attrib.get("data-bulletin-id") or "")
    if value < _MIN_SANE_PART_PRICE_RUB or not offer_id:
        return True, None
    return True, PartOffer(offer_id, url, name, value, matched, snippet=annotation_text[:600])


def parse_listing_page(html: str, criteria: PartCriteria, *, source_url: str) -> ParseResult:
    """Parse a Farpost search HTML page and filter compatible local used-part offers."""
    page = Selector(html)
    rows, exact_feed_count = _validate_listing_page(page, source_url)
    if not rows:
        return ParseResult(offers=[], exact_feed_count=exact_feed_count)

    offers: dict[str, PartOffer] = {}
    recognizable = False
    for row in rows:
        row_ok, offer = _parse_listing_row(row, criteria, source_url=source_url)
        recognizable = recognizable or row_ok
        if offer is not None:
            offers[offer.offer_id] = offer
    if not recognizable:
        raise FarpostFetchError("Farpost listing structure changed")
    sorted_offers = sorted(offers.values(), key=lambda offer: (offer.price_rub, offer.offer_id))
    return ParseResult(offers=sorted_offers, exact_feed_count=exact_feed_count)


def parse_offers(html: str, criteria: PartCriteria, *, source_url: str) -> list[PartOffer]:
    return parse_listing_page(html, criteria, source_url=source_url).offers
