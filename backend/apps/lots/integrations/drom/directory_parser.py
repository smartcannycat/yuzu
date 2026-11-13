import re

from bs4 import BeautifulSoup

from apps.lots.integrations.drom.html_utils import extract_bulls_list_ssr_payload

_MAX_LABEL_LENGTH = 60
_IGNORED_SALES_SLUGS = frozenset(
    {
        "bez-probega",
        "benzin",
        "diesel",
        "dizel",
        "gibrid",
        "hybrid",
        "electro",
        "gbo",
        "all",
        "new",
        "used",
        "suv",
        "suv-3d",
        "suv-5d",
        "pickup",
        "sedan",
        "hatchback",
        "hatchback-3d",
        "hatchback-5d",
        "liftback",
        "wagon",
        "minivan",
        "coupe",
        "open",
        "4wd",
        "akpp",
        "mkpp",
        "variator",
        "robot",
        "cvt",
        "mt",
        "at",
        "engine",
        "frame",
        "spec",
        "reviews",
        "prices",
    }
)
_IGNORED_SALES_PREFIXES = ("color-", "do-", "ot-", "year-", "page")
_IGNORED_CATALOG_BRAND_SLUGS = frozenset({"chinese", "lcv", "all", "search"})
_IGNORED_CATALOG_MODEL_SLUGS = frozenset(
    {"engine", "frame", "spec", "reviews", "prices", "used", "all"}
)
_IGNORED_LABEL_PREFIXES = ("двигатели ", "кузова ", "автомобили ")
_SEO_CATEGORY_FRAGMENT_RE = re.compile(
    r"\b(?:джип|хэтчбек|седан|универсал|пикап|минивэн|лифтбек|купе|открытый|"
    r"с\s+пробегом|с\s+гбо|двигател[ьяей]|кузов[аы])\b",
    re.IGNORECASE,
)
_CATALOG_BRAND_LINK_RE = re.compile(
    r"^(?:https://www\.drom\.ru)?/catalog/([a-z0-9_-]+)/$",
    re.IGNORECASE,
)


def _is_seo_label(label: str) -> bool:
    lower = label.strip().lower()
    if not lower or len(lower) > _MAX_LABEL_LENGTH:
        return True
    if lower.startswith(_IGNORED_LABEL_PREFIXES):
        return True
    return bool(_SEO_CATEGORY_FRAGMENT_RE.search(lower))


def _extract_directory_links(
    soup: BeautifulSoup,
    link_re: re.Pattern[str],
    *,
    ignored_slugs: frozenset[str] = frozenset(),
    ignored_prefixes: tuple[str, ...] = (),
    whitelist_names: list[str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    whitelist_lookup = (
        {name.strip().lower(): name.strip() for name in whitelist_names if name.strip()}
        if whitelist_names
        else None
    )
    names: list[str] = list(whitelist_lookup.values()) if whitelist_lookup else []
    seen_names: set[str] = {n.lower() for n in names}
    slug_map: dict[str, str] = {}

    for link in soup.find_all("a", href=True):
        match = link_re.match(str(link["href"]))
        if not match:
            continue
        slug = match.group(1).lower()
        if slug in ignored_slugs or (ignored_prefixes and slug.startswith(ignored_prefixes)):
            continue
        label = link.get_text(" ", strip=True)
        if _is_seo_label(label):
            continue
        label_key = label.lower()
        if whitelist_lookup is not None and label_key not in whitelist_lookup:
            continue
        slug_map.setdefault(label_key, slug)
        if label_key not in seen_names:
            seen_names.add(label_key)
            names.append(label)

    return names, slug_map


def _extract_ssr_models(
    soup: BeautifulSoup,
    link_re: re.Pattern[str],
) -> tuple[list[str], dict[str, str]]:
    payload = extract_bulls_list_ssr_payload(soup)
    if payload is None:
        return [], {}
    models_groups = (payload.get("filter") or {}).get("models")
    if not isinstance(models_groups, list):
        return [], {}
    names: list[str] = []
    seen: set[str] = set()
    ssr_slugs: dict[str, str] = {}
    for group in models_groups:
        if not isinstance(group, dict):
            continue
        for item in (group.get("top") or []) + (group.get("regular") or []):
            if not isinstance(item, dict) or not item.get("name"):
                continue
            name = str(item["name"]).strip()
            name_key = name.lower()
            if not name or _is_seo_label(name):
                continue
            if name_key not in seen:
                seen.add(name_key)
                names.append(name)
            raw_url = item.get("url") or item.get("href")
            if isinstance(raw_url, str):
                match = link_re.match(raw_url.strip())
                if match:
                    ssr_slugs.setdefault(name_key, match.group(1).lower())
    return names, ssr_slugs


def parse_brand_models_from_html(html: str, make_slug: str) -> tuple[list[str], dict[str, str]]:
    """Extract model names and slug map from a Drom brand page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    escaped_make = re.escape(make_slug.strip("/").lower())
    link_re = re.compile(rf"^https://auto\.drom\.ru/{escaped_make}/([a-z0-9_-]+)/$", re.IGNORECASE)
    ssr_names, ssr_slugs = _extract_ssr_models(soup, link_re)
    names, slug_map = _extract_directory_links(
        soup,
        link_re,
        ignored_slugs=_IGNORED_SALES_SLUGS,
        ignored_prefixes=_IGNORED_SALES_PREFIXES,
        whitelist_names=ssr_names or None,
    )
    for k, v in ssr_slugs.items():
        slug_map.setdefault(k, v)
    return names, slug_map


def parse_catalog_brands_from_html(html: str) -> tuple[list[str], dict[str, str]]:
    """Extract brand names and catalog URL slugs from https://www.drom.ru/catalog/."""
    soup = BeautifulSoup(html, "html.parser")
    return _extract_directory_links(
        soup,
        _CATALOG_BRAND_LINK_RE,
        ignored_slugs=_IGNORED_CATALOG_BRAND_SLUGS,
    )


def parse_catalog_models_from_html(html: str, make_slug: str) -> tuple[list[str], dict[str, str]]:
    """Extract model names and catalog URL slugs from https://www.drom.ru/catalog/{make_slug}/."""
    soup = BeautifulSoup(html, "html.parser")
    escaped_make = re.escape(make_slug.strip("/").lower())
    link_re = re.compile(
        rf"^(?:https://www\.drom\.ru)?/catalog/{escaped_make}/([a-z0-9_-]+)/$",
        re.IGNORECASE,
    )
    return _extract_directory_links(
        soup,
        link_re,
        ignored_slugs=_IGNORED_CATALOG_MODEL_SLUGS,
    )
