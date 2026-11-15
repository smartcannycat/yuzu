"""Read public Farpost listing pages and validate compatible local parts."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from scrapling import Selector

from apps.lots.integrations.http_client import (
    HttpBudgetExhaustedError,
    HttpFetchResponse,
    HttpTransportError,
    ProxyPool,
    ResilientHttpSession,
    decode_html_bytes,
    wait_for_request_slot,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    import httpx

_FARPOST_THROTTLE_KEY = "yuzu:farpost:throttle"
_FARPOST_URL = "https://www.farpost.ru/vladivostok/zapchasti/"
_MIN_SANE_PART_PRICE_RUB = 1000
_MAX_RESPONSE_BYTES = 3_000_000
_PAGE_SIZE = 50

_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.5,en;q=0.3",
}


class FarpostFetchError(RuntimeError):
    """Source failed, blocked the request or returned unrecognized markup."""


class FarpostRateLimitedError(FarpostFetchError):
    """Source responded with HTTP 429 or an anti-bot verification redirect/page."""


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


_ACCESSORIES = re.compile(
    r"обшивк|ручк|петл[яи]|молдинг|уплотнител|стеклопод[ъь]емник|замок|"
    r"проводк|накладк|зеркал|заглушк|креплен|комплект|пара\b|"
    r"решетк|усилител|абсорбер|кронштейн|подкрыл|брызговик|"
    r"фара|фонар|повторител|жабо|трапец|ограничител|форточк|"
    r"коврик|полк[аи]|шторк|упор|эмблем|шильдик|омывател|моторчик",
    re.I,
)
_ASSEMBLY_SUFFIX_RE = re.compile(
    r"(?:\bв\s+сборе\b.*|\b(?:с|со|без|под)\s+(?:обшивк|ручк|петл|молдинг|уплотнител|"
    r"стеклопод[ъь]емник|замк|замок|проводк|накладк|зеркал|заглушк|креплен|решетк|"
    r"усилител|абсорбер|кронштейн|подкрыл|брызговик|фара|фонар|повторител|омывател|"
    r"туманк|парктроник|датчик|камер|форточк|ограничител|моторчик|эмблем|шильдик|"
    r"шторк|упор|трапец|стекл)\w*.*)",
    re.I,
)
_NON_WINDSHIELD_GLASS = re.compile(r"^\s*стекл[оа]\b|стекло\s+двер|дверн\w*\s+стекл", re.I)
_NEW_OR_AFTERMARKET = re.compile(
    r"\b(?:нова(?:я|ый|ое|ые)|нов(?:ый|ая|ое)|дубликат\w*|аналог\w*|"
    r"sat|tyg|api|тайван\w*|китай\w*)\b",
    re.I,
)
_DAMAGE = re.compile(r"вмятин|залом|тычк|трещин|под ремонт|поврежден|дефект|разбит", re.I)
_UNAVAILABLE = re.compile(
    r"под заказ|нет в наличии|ожидается|товар находится в другом|доставка из", re.I
)

_MAKE_ALIASES: dict[str, tuple[str, ...]] = {
    "toyota": ("toyota", "тойота"),
    "honda": ("honda", "хонда"),
    "nissan": ("nissan", "ниссан"),
    "mazda": ("mazda", "мазда"),
    "subaru": ("subaru", "субару"),
    "suzuki": ("suzuki", "сузуки"),
    "mitsubishi": ("mitsubishi", "митсубиси", "мицубиси"),
    "daihatsu": ("daihatsu", "дайхатсу"),
    "lexus": ("lexus", "лексус"),
    "mercedes": ("mercedes", "mercedesbenz", "мерседес", "мерседесбенц"),
    "mercedesbenz": ("mercedesbenz", "mercedes", "мерседес", "мерседесбенц"),
    "bmw": ("bmw", "бмв"),
    "audi": ("audi", "ауди"),
    "volkswagen": ("volkswagen", "vw", "фольксваген"),
    "mini": ("mini", "мини"),
    "hyundai": ("hyundai", "хендай", "хундай", "хендэ"),
    "kia": ("kia", "киа"),
    "volvo": ("volvo", "вольво"),
    "porsche": ("porsche", "порше"),
    "landrover": ("landrover", "лендровер"),
    "ford": ("ford", "форд"),
    "chevrolet": ("chevrolet", "шевроле"),
    "geely": ("geely", "джили"),
    "chery": ("chery", "чери"),
    "haval": ("haval", "хавал", "хавейл"),
}

_SISTER_MAKES: dict[str, frozenset[str]] = {
    "toyota": frozenset({"toyota", "lexus", "daihatsu"}),
    "lexus": frozenset({"lexus", "toyota"}),
    "daihatsu": frozenset({"daihatsu", "toyota"}),
    "nissan": frozenset({"nissan", "infiniti"}),
    "infiniti": frozenset({"infiniti", "nissan"}),
    "honda": frozenset({"honda", "acura"}),
    "acura": frozenset({"acura", "honda"}),
    "hyundai": frozenset({"hyundai", "kia", "genesis"}),
    "kia": frozenset({"kia", "hyundai", "genesis"}),
    "genesis": frozenset({"genesis", "hyundai", "kia"}),
}

_MODEL_ALIASES: dict[str, tuple[str, ...]] = {
    "freed": ("freed", "фрид"),
    "freedspike": ("freedspike", "freed", "фридспайк", "фрид"),
    "fit": ("fit", "фит"),
    "vezel": ("vezel", "везел"),
    "corolla": ("corolla", "королла"),
    "corollafielder": ("corollafielder", "fielder", "филдер", "короллафилдер"),
    "corollatouring": ("corollatouring", "короллатуринг"),
    "prius": ("prius", "приус"),
    "priusalpha": ("priusalpha", "приусальфа"),
    "aqua": ("aqua", "аква"),
    "vitz": ("vitz", "витц"),
    "yaris": ("yaris", "ярис"),
    "yariscross": ("yariscross", "ярискросс"),
    "tank": ("tank", "танк"),
    "roomy": ("roomy", "руми"),
    "raize": ("raize", "райз"),
    "rocky": ("rocky", "рокки"),
    "rush": ("rush", "раш"),
    "probox": ("probox", "пробокс"),
    "succeed": ("succeed", "саксид"),
    "stepwgn": ("stepwgn", "степвагон", "степвагн"),
    "note": ("note", "ноут", "нот"),
    "roox": ("roox", "рукс"),
    "serena": ("serena", "серена"),
    "xtrail": ("xtrail", "икстрейл"),
    "rav4": ("rav4", "рав4"),
    "harrier": ("harrier", "харриер"),
    "alphard": ("alphard", "альфард"),
    "vellfire": ("vellfire", "веллфайр"),
    "voxy": ("voxy", "вокси"),
    "noah": ("noah", "ноах"),
    "camry": ("camry", "камри"),
    "crown": ("crown", "краун"),
    "wish": ("wish", "виш"),
    "estima": ("estima", "эстима"),
    "chr": ("chr", "схр"),
    "landcruiser": ("landcruiser", "лендкрузер", "крузер"),
    "landcruiserprado": ("landcruiserprado", "prado", "прадо"),
    "sienta": ("sienta", "сиента"),
    "insight": ("insight", "инсайт"),
    "shuttle": ("shuttle", "шатл"),
    "odyssey": ("odyssey", "одиссей"),
    "civic": ("civic", "цивик"),
    "nbox": ("nbox", "нбокс"),
    "nwgn": ("nwgn", "нвгн"),
    "impreza": ("impreza", "импреза"),
    "levorg": ("levorg", "леворг"),
    "forester": ("forester", "форестер"),
    "xv": ("xv", "хв"),
    "legacy": ("legacy", "легаси"),
    "outback": ("outback", "аутбек"),
    "delica": ("delica", "делика"),
    "delicad5": ("delicad5", "delica", "деликад5", "делика"),
    "outlander": ("outlander", "аутлендер"),
    "eclipsecross": ("eclipsecross", "эклипскросс"),
    "demio": ("demio", "демио"),
    "axela": ("axela", "аксела"),
    "cx5": ("cx5", "сх5"),
    "swift": ("swift", "свифт"),
    "jimny": ("jimny", "джимни"),
    "solio": ("solio", "солио"),
    "hustler": ("hustler", "хастлер"),
    "spacia": ("spacia", "спейсия"),
    "wagonr": ("wagonr", "вагонр"),
    "tanto": ("tanto", "танто"),
}

_LEFT_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])(?:л\.?(?![a-zа-я0-9])|лев|слева\b)|[пз][/\\.]л\b|\b(?:lh|fl|rl)\b)",
    re.I,
)
_RIGHT_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])(?:прав|пр\.?(?![a-zа-я0-9])|справа\b)|[пз][/\\.]п\b|\b(?:rh|fr|rr)\b)",
    re.I,
)
_FRONT_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])(?:перед|пер\.?(?![a-zа-я0-9])|спереди\b)|п[/\\.]л\b|п[/\\.]п\b|\b(?:front|fl|fr)\b)",
    re.I,
)
_REAR_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])(?:зад|сзади\b)|з[/\\.]л\b|з[/\\.]п\b|\b(?:rear|rl|rr)\b)",
    re.I,
)
_FENDER_RE = re.compile(r"\bкрыл(?:о|а|у|е|ья|ьев)\b", re.I)
_LITER_TOKEN_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*л\.?(?![a-zа-я0-9])", re.I)


def _strip_liter_tokens(value: str) -> str:
    """Remove engine displacement tokens (e.g. '1.5 л') so 'л' is not misread as 'левая'."""
    return _LITER_TOKEN_RE.sub(" ", value)


def _compact(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", value.casefold().replace("ё", "е"))


def _contains_code(text: str, code: str) -> bool:
    # Highlight spans and vendor formatting may put whitespace inside body codes.
    pattern = r"(?<![a-z0-9])" + r"\s*".join(map(re.escape, code.lower())) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text.lower()))


_COMPOUND_ALIAS_PATTERNS: dict[str, str] = {
    "mercedesbenz": r"mercedes[\s-]*benz",
    "мерседесбенц": r"мерседес[\s-]*бенц",
    "landrover": r"land[\s-]*rover",
    "лендровер": r"ленд[\s-]*ровер",
}
_MAKE_CONFLICT_PATTERNS: dict[str, re.Pattern[str]] = {
    make_name: re.compile(
        r"(?<![a-zа-я0-9])(?:"
        + "|".join(_COMPOUND_ALIAS_PATTERNS.get(v, re.escape(v)) for v in variants)
        + r")(?![a-zа-я0-9])",
        re.I,
    )
    for make_name, variants in _MAKE_ALIASES.items()
}


def _has_conflicting_make(text: str, make_key: str) -> bool:
    allowed = _SISTER_MAKES.get(make_key, frozenset({make_key}))
    normalized = text.casefold().replace("ё", "е")
    for other_make, pattern in _MAKE_CONFLICT_PATTERNS.items():
        if other_make in allowed:
            continue
        if pattern.search(normalized):
            return True
    return False


def _matches_make_and_model(
    text: str, criteria: PartCriteria, *, has_exact_body_code: bool = False
) -> bool:
    compact_text = _compact(text)
    make_key = _compact(criteria.make)
    model_key = _compact(criteria.model)
    make_variants = _MAKE_ALIASES.get(make_key, (make_key,))
    model_variants = _MODEL_ALIASES.get(model_key, (model_key,))
    make_matched = any(v and v in compact_text for v in make_variants)
    model_matched = any(v and v in compact_text for v in model_variants)
    if make_matched and model_matched:
        return True
    if has_exact_body_code and (make_matched or model_matched):
        return not _has_conflicting_make(text, make_key)
    return False


_TAILGATE_RE = re.compile(
    r"(?:5(?:-?я)?|пят(?:ая|ой))\s*двер|двер\w*\s*(?:5(?:-?я)?|багаж)",
    re.I,
)


def _matches_part_name(name: str, criteria: PartCriteria) -> bool:
    lowered = name.casefold()
    if criteria.panel_id == "windshield":
        return "стекл" in lowered and ("лобов" in lowered or "ветров" in lowered)
    if criteria.panel_id == "tailgate":
        side_clean = _strip_liter_tokens(name)
        has_side_door = bool(_LEFT_RE.search(side_clean) or _RIGHT_RE.search(side_clean))
        return (
            "багажник" in lowered
            or "дверь задка" in lowered
            or bool(_TAILGATE_RE.search(lowered))
            or ("задн" in lowered and "двер" in lowered and not has_side_door)
        )
    if criteria.panel_id in {"front_left_fender", "front_right_fender"}:
        return bool(_FENDER_RE.search(lowered))
    if criteria.part_name == "дверь":
        return "двер" in lowered
    return criteria.part_name.casefold() in lowered


def _matches_side_and_position(name: str, criteria: PartCriteria) -> bool:
    cleaned_name = _strip_liter_tokens(name)
    if criteria.side:
        want_left = criteria.side.casefold().startswith("лев")
        has_left = bool(_LEFT_RE.search(cleaned_name))
        has_right = bool(_RIGHT_RE.search(cleaned_name))
        if want_left and (not has_left or has_right):
            return False
        if not want_left and (not has_right or has_left):
            return False
    if criteria.position and criteria.panel_id != "windshield":
        pos = criteria.position.casefold()
        if pos.startswith("перед"):
            if not _FRONT_RE.search(cleaned_name) or _REAR_RE.search(cleaned_name):
                return False
        elif pos.startswith("зад"):
            if not _REAR_RE.search(cleaned_name) or _FRONT_RE.search(cleaned_name):
                return False
        elif pos[:5] not in cleaned_name.casefold():
            return False
    return True


def matches_paint_code(text: str, paint_code: str) -> bool:
    """Return True when text explicitly confirms the factory paint code."""
    if not paint_code:
        return False
    code_pat = r"[ \t]*".join(map(re.escape, paint_code))
    context_pattern = (
        r"(?:цвет|код\s+краски|окрас|paint|color)"
        r"(?:(?!\b(?:не|другой|пробег|цена)\b)[^.;\n]){0,24}?"
        + r"(?<![a-zа-я0-9])"
        + code_pat
        + r"(?![a-zа-я0-9])"
    )
    if re.search(context_pattern, text, re.I):
        return True
    # Longer alphanumeric factory codes (e.g., NH883P, YR607M) rarely collide with part/body IDs.
    has_mixed_alnum = bool(re.search(r"[a-z]", paint_code, re.I) and re.search(r"\d", paint_code))
    if len(paint_code) >= 4 and has_mixed_alnum:
        return bool(re.search(r"(?<![a-zа-я0-9])" + code_pat + r"(?![a-zа-я0-9])", text, re.I))
    return False


_matches_paint_code = matches_paint_code


def _is_accessory_listing(name: str) -> bool:
    """Reject standalone trim/mounts while keeping complete doors or bumpers sold in assembly."""
    head = _ASSEMBLY_SUFFIX_RE.sub("", name).strip()
    return bool(_ACCESSORIES.search(head))


def _throttle_wait(deadline: float, interval_sec: float, jitter_sec: float = 0.0) -> None:
    try:
        wait_for_request_slot(
            _FARPOST_THROTTLE_KEY,
            interval_sec,
            jitter_sec,
            deadline=deadline,
        )
    except HttpBudgetExhaustedError as exc:
        raise FarpostFetchError("Farpost search budget exhausted") from exc


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


def parse_listing_page(html: str, criteria: PartCriteria, *, source_url: str) -> ParseResult:
    page = Selector(html)
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
            return ParseResult(offers=[], exact_feed_count=0)
        raise FarpostFetchError("Farpost did not confirm local stock filtering")

    rows = page.css(".bull-item")
    if not rows:
        if not event_valid:
            raise FarpostFetchError("Unrecognized Farpost listing markup")
        if exact_feed_count == 0:
            return ParseResult(offers=[], exact_feed_count=0)
        raise FarpostFetchError("Farpost returned no recognizable listing rows")

    offers: dict[str, PartOffer] = {}
    recognizable = False
    for row in rows:
        link_nodes = row.css('[data-role="bulletin-link"]')
        if not link_nodes:
            continue
        recognizable = True
        price_nodes = row.css(".price-block__final-price")
        if not price_nodes:
            continue
        link = link_nodes[0]
        name = link.get_all_text(separator=" ", strip=True)
        ann_nodes = row.css(".bull-item__annotation") or row.css(".bull-item__annotation-row")
        annotation_text = (
            " ".join(n.get_all_text(separator=" ", strip=True) for n in ann_nodes).strip()
            if ann_nodes
            else ""
        )
        text = f"{name} {annotation_text}".strip()
        path = str(link.attrib.get("href", ""))
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
        is_glass_for_non_glass = criteria.panel_id != "windshield" and bool(
            _NON_WINDSHIELD_GLASS.search(name)
        )
        if (
            _is_accessory_listing(name)
            or is_glass_for_non_glass
            or _DAMAGE.search(clean)
            or _UNAVAILABLE.search(text)
            or _NEW_OR_AFTERMARKET.search(text)
        ):
            continue
        has_body_code = bool(criteria.body_code and _contains_code(text, criteria.body_code))
        if not has_body_code:
            continue
        if not _matches_make_and_model(text, criteria, has_exact_body_code=has_body_code):
            continue
        if not _matches_part_name(name, criteria):
            continue
        if not _matches_side_and_position(name, criteria):
            continue
        matched = matches_paint_code(text, criteria.paint_code)
        if criteria.paint_code and not matched:
            continue
        quoted = _extract_price_quote(price_nodes[0])
        amount = re.fullmatch(r"\s*([\d\s\xa0]+)\s*₽\s*", quoted)
        if amount is None:
            continue
        value = int(re.sub(r"\D", "", amount[1]))
        offer_id = str(row.attrib.get("data-good-id") or row.attrib.get("data-bulletin-id") or "")
        if value < _MIN_SANE_PART_PRICE_RUB or not offer_id:
            continue
        snippet = annotation_text[:600]
        offers[offer_id] = PartOffer(offer_id, url, name, value, matched, snippet=snippet)
    if not recognizable:
        raise FarpostFetchError("Farpost listing structure changed")
    sorted_offers = sorted(offers.values(), key=lambda offer: (offer.price_rub, offer.offer_id))
    return ParseResult(offers=sorted_offers, exact_feed_count=exact_feed_count)


def parse_offers(html: str, criteria: PartCriteria, *, source_url: str) -> list[PartOffer]:
    return parse_listing_page(html, criteria, source_url=source_url).offers


class FarpostClient:
    def __init__(
        self,
        *,
        timeout_sec: float = 8.0,
        request_interval_sec: float = 0.0,
        request_jitter_sec: float = 0.0,
        proxy_ban_sec: float = 120.0,
        proxy_urls: Sequence[str] = (),
        transport: httpx.BaseTransport | None = None,
    ):
        self.timeout_sec = timeout_sec
        self.request_interval_sec = request_interval_sec
        self.request_jitter_sec = request_jitter_sec
        self.proxy_ban_sec = proxy_ban_sec
        self.transport = transport
        self._proxy_rotator = (
            ProxyPool(proxy_urls, domain="www.farpost.ru", ban_cooldown_sec=proxy_ban_sec)
            if proxy_urls
            else None
        )
        self._session: ResilientHttpSession | None = None

    def _build_session(self) -> ResilientHttpSession:
        return ResilientHttpSession(
            headers=_DEFAULT_HEADERS,
            timeout_sec=self.timeout_sec,
            impersonate="chrome",
            domain="www.farpost.ru",
            proxy_rotator=self._proxy_rotator,
            transport=self.transport,
        )

    def __enter__(self) -> FarpostClient:
        if self._session is None:
            self._session = self._build_session()
            self._session.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._session is not None:
            self._session.__exit__(*args)
            self._session = None

    def _fetch_html(
        self,
        session: ResilientHttpSession,
        criteria: PartCriteria,
        deadline: float,
        *,
        page: int = 1,
    ) -> tuple[str, str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FarpostFetchError("Farpost search budget exhausted")
        params: dict[str, str | int] = {
            "query": criteria.query,
            "goodPresentState": "present",
            "condition[]": "used",
            "sortBy": "pricea",
        }
        if page > 1:
            params["page"] = page
        response: HttpFetchResponse = session.get(
            _FARPOST_URL,
            params=params,
            timeout=min(self.timeout_sec, remaining),
            max_bytes=_MAX_RESPONSE_BYTES,
        )
        if response.status_code == 429 or urlparse(response.url).path.startswith("/verify"):
            session.mark_proxy_blocked(
                response.proxy_key,
                url=_FARPOST_URL,
                cooldown_sec=self.proxy_ban_sec,
            )
            raise FarpostRateLimitedError("Farpost rate limited or anti-bot verification requested")
        if response.status_code >= 400:
            raise FarpostFetchError(f"Farpost returned HTTP {response.status_code}")
        if time.monotonic() > deadline:
            raise FarpostFetchError("Farpost search budget exhausted")
        return decode_html_bytes(response.content, response.headers), response.url

    def _fetch_and_parse_page(
        self,
        criteria: PartCriteria,
        *,
        deadline: float,
        page: int = 1,
    ) -> ParseResult:
        max_attempts = min(len(self._proxy_rotator), 3) if self._proxy_rotator else 1
        last_rate_err: FarpostRateLimitedError | None = None
        last_transport_err: HttpTransportError | None = None
        for attempt in range(max_attempts):
            if self.transport is None:
                _throttle_wait(deadline, self.request_interval_sec, self.request_jitter_sec)
            active_session = self._session
            try:
                if active_session is not None:
                    html, final_url = self._fetch_html(
                        active_session, criteria, deadline, page=page
                    )
                else:
                    with self._build_session() as session:
                        active_session = session
                        html, final_url = self._fetch_html(session, criteria, deadline, page=page)
                return parse_listing_page(html, criteria, source_url=final_url)
            except FarpostRateLimitedError as exc:
                last_rate_err = exc
                if attempt < max_attempts - 1 and deadline - time.monotonic() > 1.0:
                    continue
                raise
            except HttpTransportError as exc:
                if active_session is not None:
                    active_session.mark_proxy_blocked(
                        exc.proxy_key,
                        url=_FARPOST_URL,
                        cooldown_sec=self.proxy_ban_sec,
                    )
                last_transport_err = exc
                if attempt < max_attempts - 1 and deadline - time.monotonic() > 1.0:
                    continue
                raise FarpostFetchError(f"Farpost request failed: {exc}") from exc
        if last_rate_err is not None:
            raise last_rate_err
        raise FarpostFetchError(f"Farpost request failed: {last_transport_err}")

    def search_with_metadata(self, criteria: PartCriteria, *, deadline: float) -> ParseResult:
        if time.monotonic() >= deadline:
            raise FarpostFetchError("Farpost search budget exhausted")
        result = self._fetch_and_parse_page(criteria, deadline=deadline, page=1)
        if (
            not result.offers
            and result.exact_feed_count is not None
            and result.exact_feed_count > _PAGE_SIZE
            and deadline - time.monotonic() > min(self.timeout_sec, 3.0)
        ):
            try:
                page2 = self._fetch_and_parse_page(criteria, deadline=deadline, page=2)
            except FarpostRateLimitedError:
                raise
            except FarpostFetchError:
                return result
            return ParseResult(
                offers=page2.offers,
                exact_feed_count=result.exact_feed_count,
            )
        return result

    def search(self, criteria: PartCriteria, *, deadline: float) -> list[PartOffer]:
        return self.search_with_metadata(criteria, deadline=deadline).offers
