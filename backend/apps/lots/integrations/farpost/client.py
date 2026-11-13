"""Read public Farpost listing pages and validate compatible local parts."""

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


class FarpostFetchError(RuntimeError):
    """Source failed, blocked the request or returned unrecognized markup."""


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


_ACCESSORIES = re.compile(
    r"обшивк|ручк|петл[яи]|молдинг|уплотнител|стеклопод[ъь]емник|замок|"
    r"проводк|накладк|зеркал|заглушк|креплен|комплект|пара\b",
    re.I,
)
_DAMAGE = re.compile(r"вмятин|залом|тычк|трещин|под ремонт|поврежден|дефект|разбит", re.I)
_UNAVAILABLE = re.compile(
    r"под заказ|нет в наличии|ожидается|товар находится в другом|доставка из", re.I
)


def _compact(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", value.casefold().replace("ё", "е"))


def _contains_code(text: str, code: str) -> bool:
    # Highlight spans and vendor formatting may put whitespace inside body codes.
    pattern = r"(?<![a-z0-9])" + r"\s*".join(map(re.escape, code.lower())) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text.lower()))


def parse_offers(html: str, criteria: PartCriteria, *, source_url: str) -> list[PartOffer]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if re.search(r"вы не робот|captcha|подозрительный трафик", title + soup.get_text(" "), re.I):
        raise FarpostFetchError("Farpost returned an anti-bot challenge")
    # Require explicit server-rendered confirmation of the requested inventory filter.
    local_filter = soup.select_one('input[name="goodPresentState"][value="present"][checked]')
    rows = soup.select(".bull-item")
    event = soup.select_one("script#ctr-viewdir-event")
    if local_filter is None or urlparse(source_url).path.split("/")[1:2] != ["vladivostok"]:
        raise FarpostFetchError("Farpost did not confirm local stock filtering")
    if not rows:
        import json

        try:
            count = json.loads(event.string or "")["exactFeedCount"] if event else None
        except (ValueError, TypeError, KeyError) as exc:
            raise FarpostFetchError("Unrecognized Farpost listing markup") from exc
        if count == 0:
            return []
        raise FarpostFetchError("Farpost returned no recognizable listing rows")
    offers: dict[str, PartOffer] = {}
    recognizable = False
    for row in rows:
        link = row.select_one('[data-role="bulletin-link"]')
        price = row.select_one(".price-block__final-price")
        if link is None or price is None:
            continue
        recognizable = True
        name = link.get_text(" ", strip=True)
        annotation = row.select_one(".bull-item__annotation")
        text = name + " " + (annotation.get_text(" ", strip=True) if annotation else "")
        path = str(link.get("href", ""))
        url = urljoin(source_url, path)
        parsed = urlparse(url)
        listing_path = parsed.path.removeprefix("/ni/")
        if not listing_path.startswith("/"):
            listing_path = "/" + listing_path
        if parsed.hostname != "www.farpost.ru" or not listing_path.startswith(
            "/vladivostok/zapchasti/"
        ):
            continue
        clean = re.sub(r"без (?:повреждений|дефектов|вмятин|трещин)", "", text, flags=re.I)
        if _ACCESSORIES.search(name) or _DAMAGE.search(clean) or _UNAVAILABLE.search(text):
            continue
        if not re.search(r"контракт|б\s*/\s*у|с распила", text, re.I):
            continue
        if any(_compact(value) not in _compact(text) for value in (criteria.make, criteria.model)):
            continue
        if not criteria.body_code or not _contains_code(text, criteria.body_code):
            continue
        if criteria.part_name.casefold() not in name.casefold():
            continue
        if criteria.side and criteria.side[:3] not in name.casefold():
            continue
        if criteria.position and criteria.position[:5] not in name.casefold():
            continue
        # Unknown colors never count as a match and do not remove painting costs.
        matched = bool(
            criteria.paint_code
            and re.search(
                r"(?:цвет|код\s+краски|paint)\s*[:=]?\s*"
                + re.escape(criteria.paint_code)
                + r"(?![a-zа-я0-9])",
                text,
                re.I,
            )
        )
        if criteria.paint_code and not matched:
            continue
        quoted = BeautifulSoup(str(price.get("data-price", "")), "html.parser").get_text(
            " ", strip=True
        )
        if not quoted:
            node = price.select_one('[data-role="price"]')
            quoted = node.get_text(" ", strip=True) if node else ""
        amount = re.fullmatch(r"\s*([\d\s\xa0]+)\s*₽\s*", quoted)
        if amount is None:
            continue
        value = int(re.sub(r"\D", "", amount[1]))
        offer_id = str(row.get("data-good-id") or row.get("data-bulletin-id") or "")
        if value <= 0 or not offer_id:
            continue
        offers[offer_id] = PartOffer(offer_id, url, name, value, matched)
    if not recognizable:
        raise FarpostFetchError("Farpost listing structure changed")
    return sorted(offers.values(), key=lambda offer: (offer.price_rub, offer.offer_id))
