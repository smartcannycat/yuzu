"""Read public Farpost listing pages and validate compatible local parts."""

import json
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from apps.core.redis_utils import acquire_distributed_interval_slot

_FARPOST_THROTTLE_KEY = "yuzu:farpost:throttle"
_MIN_SANE_PART_PRICE_RUB = 1000
_MAX_RESPONSE_BYTES = 3_000_000

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.5,en;q=0.3",
}

_local_throttle_lock = threading.Lock()
_local_next_request_at = 0.0


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


_ACCESSORIES = re.compile(
    r"обшивк|ручк|петл[яи]|молдинг|уплотнител|стеклопод[ъь]емник|замок|"
    r"проводк|накладк|зеркал|заглушк|креплен|комплект|пара\b|"
    r"решетк|усилител|абсорбер|кронштейн|подкрыл|брызговик|"
    r"фара|фонар|повторител|жабо|трапец|ограничител|форточк|"
    r"коврик|полк[аи]|шторк|упор|эмблем|шильдик|омывател|моторчик",
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
}
_MODEL_ALIASES: dict[str, tuple[str, ...]] = {
    "freed": ("freed", "фрид"),
    "fit": ("fit", "фит"),
    "vezel": ("vezel", "везел"),
    "corolla": ("corolla", "королла"),
    "corollafielder": ("corollafielder", "fielder", "филдер", "короллафилдер"),
    "corollatouring": ("corollatouring", "короллатуринг"),
    "prius": ("prius", "приус"),
    "aqua": ("aqua", "аква"),
    "vitz": ("vitz", "витц"),
    "yaris": ("yaris", "ярис"),
    "stepwgn": ("stepwgn", "степвагон", "степвагн"),
    "note": ("note", "ноут", "нот"),
    "serena": ("serena", "серена"),
    "xtrail": ("xtrail", "икстрейл"),
    "rav4": ("rav4", "рав4"),
    "harrier": ("harrier", "харриер"),
    "alphard": ("alphard", "альфард"),
    "vellfire": ("vellfire", "веллфайр"),
    "voxy": ("voxy", "вокси"),
    "noah": ("noah", "ноах"),
    "camry": ("camry", "камри"),
    "sienta": ("sienta", "сиента"),
    "insight": ("insight", "инсайт"),
    "nbox": ("nbox", "нбокс"),
    "impreza": ("impreza", "импреза"),
    "levorg": ("levorg", "леворг"),
    "forester": ("forester", "форестер"),
    "demio": ("demio", "демио"),
    "axela": ("axela", "аксела"),
    "cx5": ("cx5", "сх5"),
    "swift": ("swift", "свифт"),
    "spacia": ("spacia", "спейсия"),
    "tanto": ("tanto", "танто"),
}

_LEFT_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])л\.?(?![a-zа-я0-9])|лев|[пз][/\\.]л\b|\b(?:lh|fl|rl)\b)", re.I
)
_RIGHT_RE = re.compile(r"(?:прав|пр\.?(?![a-zа-я0-9])|[пз][/\\.]п\b|\b(?:rh|fr|rr)\b)", re.I)
_FRONT_RE = re.compile(
    r"(?:перед|пер\.?(?![a-zа-я0-9])|п[/\\.]л\b|п[/\\.]п\b|\b(?:front|fl|fr)\b)", re.I
)
_REAR_RE = re.compile(r"(?:зад|з[/\\.]л\b|з[/\\.]п\b|\b(?:rear|rl|rr)\b)", re.I)


def _compact(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", value.casefold().replace("ё", "е"))


def _contains_code(text: str, code: str) -> bool:
    # Highlight spans and vendor formatting may put whitespace inside body codes.
    pattern = r"(?<![a-z0-9])" + r"\s*".join(map(re.escape, code.lower())) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text.lower()))


def _matches_make_and_model(text: str, criteria: PartCriteria) -> bool:
    compact_text = _compact(text)
    make_key = _compact(criteria.make)
    model_key = _compact(criteria.model)
    make_variants = _MAKE_ALIASES.get(make_key, (make_key,))
    model_variants = _MODEL_ALIASES.get(model_key, (model_key,))
    return any(v and v in compact_text for v in make_variants) and any(
        v and v in compact_text for v in model_variants
    )


_TAILGATE_RE = re.compile(
    r"(?:5(?:-?я)?|пят(?:ая|ой))\s*двер|двер\w*\s*(?:5(?:-?я)?|багаж)",
    re.I,
)


def _matches_part_name(name: str, criteria: PartCriteria) -> bool:
    lowered = name.casefold()
    if criteria.panel_id == "windshield":
        return "стекл" in lowered and ("лобов" in lowered or "ветров" in lowered)
    if criteria.panel_id == "tailgate":
        has_side_door = bool(_LEFT_RE.search(name) or _RIGHT_RE.search(name))
        return (
            "багажник" in lowered
            or "дверь задка" in lowered
            or bool(_TAILGATE_RE.search(lowered))
            or ("задн" in lowered and "двер" in lowered and not has_side_door)
        )
    return criteria.part_name.casefold() in lowered


def _matches_side_and_position(name: str, criteria: PartCriteria) -> bool:
    if criteria.side:
        want_left = criteria.side.casefold().startswith("лев")
        has_left = bool(_LEFT_RE.search(name))
        has_right = bool(_RIGHT_RE.search(name))
        if want_left and (not has_left or has_right):
            return False
        if not want_left and (not has_right or has_left):
            return False
    if criteria.position and criteria.panel_id != "windshield":
        pos = criteria.position.casefold()
        if pos.startswith("перед"):
            if not _FRONT_RE.search(name) or _REAR_RE.search(name):
                return False
        elif pos.startswith("зад"):
            if not _REAR_RE.search(name) or _FRONT_RE.search(name):
                return False
        elif pos[:5] not in name.casefold():
            return False
    return True


def _matches_paint_code(text: str, paint_code: str) -> bool:
    if not paint_code:
        return False
    code_pat = re.escape(paint_code)
    context_pattern = (
        r"(?:цвет|код\s+краски|окрас|paint|color)[^.;\n]{0,30}?"
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


def _throttle_wait(deadline: float, interval_sec: float) -> None:
    global _local_next_request_at
    if interval_sec <= 0:
        return
    wait_sec = acquire_distributed_interval_slot(_FARPOST_THROTTLE_KEY, interval_sec)
    if wait_sec is None:
        with _local_throttle_lock:
            now = time.monotonic()
            scheduled = max(now, _local_next_request_at)
            wait_sec = scheduled - now
            _local_next_request_at = scheduled + interval_sec
    if wait_sec > 0:
        if time.monotonic() + wait_sec >= deadline:
            raise FarpostFetchError("Farpost search budget exhausted")
        time.sleep(wait_sec)


def parse_offers(html: str, criteria: PartCriteria, *, source_url: str) -> list[PartOffer]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if re.search(r"вы не робот|captcha|подозрительный трафик", title + soup.get_text(" "), re.I):
        raise FarpostRateLimitedError("Farpost returned an anti-bot challenge")
    # Require explicit server-rendered confirmation of the requested inventory filter.
    local_filter = soup.select_one('input[name="goodPresentState"][value="present"][checked]')
    rows = soup.select(".bull-item")
    event = soup.select_one("script#ctr-viewdir-event")
    if local_filter is None or urlparse(source_url).path.split("/")[1:2] != ["vladivostok"]:
        raise FarpostFetchError("Farpost did not confirm local stock filtering")
    if not rows:
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
        is_glass_for_non_glass = criteria.panel_id != "windshield" and bool(
            _NON_WINDSHIELD_GLASS.search(name)
        )
        if (
            _ACCESSORIES.search(name)
            or is_glass_for_non_glass
            or _DAMAGE.search(clean)
            or _UNAVAILABLE.search(text)
            or _NEW_OR_AFTERMARKET.search(text)
        ):
            continue
        if not _matches_make_and_model(text, criteria):
            continue
        if not criteria.body_code or not _contains_code(text, criteria.body_code):
            continue
        if not _matches_part_name(name, criteria):
            continue
        if not _matches_side_and_position(name, criteria):
            continue
        # Unknown colors never count as a match and do not remove painting costs.
        matched = _matches_paint_code(text, criteria.paint_code)
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
        if value < _MIN_SANE_PART_PRICE_RUB or not offer_id:
            continue
        offers[offer_id] = PartOffer(offer_id, url, name, value, matched)
    if not recognizable:
        raise FarpostFetchError("Farpost listing structure changed")
    return sorted(offers.values(), key=lambda offer: (offer.price_rub, offer.offer_id))


class FarpostClient:
    def __init__(
        self,
        *,
        timeout_sec: float = 8.0,
        request_interval_sec: float = 0.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.timeout_sec = timeout_sec
        self.request_interval_sec = request_interval_sec
        self.transport = transport
        self._session: httpx.Client | None = None

    def __enter__(self) -> "FarpostClient":
        if self._session is None:
            self._session = httpx.Client(
                transport=self.transport,
                headers=_DEFAULT_HEADERS,
                follow_redirects=True,
            )
        return self

    def __exit__(self, *args: object) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def _fetch_html(
        self, client: httpx.Client, criteria: PartCriteria, deadline: float
    ) -> tuple[str, str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FarpostFetchError("Farpost search budget exhausted")
        response = client.get(
            "https://www.farpost.ru/vladivostok/zapchasti/",
            params={
                "query": criteria.query,
                "goodPresentState": "present",
                "condition[]": "used",
                "sortBy": "pricea",
            },
            timeout=min(self.timeout_sec, remaining),
        )
        if response.status_code == 429 or urlparse(str(response.url)).path.startswith("/verify"):
            raise FarpostRateLimitedError("Farpost rate limited or anti-bot verification requested")
        response.raise_for_status()
        if time.monotonic() > deadline:
            raise FarpostFetchError("Farpost search budget exhausted")
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise FarpostFetchError("Farpost page exceeds the size limit")
        head = response.content[:4000].lower()
        encoding = "cp1251" if b"windows-1251" in head else "utf-8"
        return response.content.decode(encoding, errors="replace"), str(response.url)

    def search(self, criteria: PartCriteria, *, deadline: float) -> list[PartOffer]:
        if time.monotonic() >= deadline:
            raise FarpostFetchError("Farpost search budget exhausted")
        if self.transport is None:
            _throttle_wait(deadline, self.request_interval_sec)
        try:
            if self._session is not None:
                html, final_url = self._fetch_html(self._session, criteria, deadline)
            else:
                with httpx.Client(
                    transport=self.transport,
                    headers=_DEFAULT_HEADERS,
                    follow_redirects=True,
                ) as client:
                    html, final_url = self._fetch_html(client, criteria, deadline)
        except httpx.HTTPError as exc:
            raise FarpostFetchError(f"Farpost request failed: {exc}") from exc
        return parse_offers(html, criteria, source_url=final_url)
