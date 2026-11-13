import re

from bs4 import BeautifulSoup

from apps.lots.integrations.drom.html_utils import extract_bulls_list_ssr_payload

_MAX_LABEL_LENGTH = 60
_IGNORED_SALES_SLUGS = frozenset(
    {"bez-probega", "benzin", "diesel", "gibrid", "electro", "all", "new"}
)
_IGNORED_SALES_PREFIXES = ("color-", "do-", "ot-", "year-", "page")
_IGNORED_CATALOG_BRAND_SLUGS = frozenset({"chinese", "lcv", "all", "search"})
_CATALOG_BRAND_LINK_RE = re.compile(
    r"^(?:https://www\.drom\.ru)?/catalog/([a-z0-9_-]+)/$",
    re.IGNORECASE,
)


def _extract_directory_links(
    soup: BeautifulSoup,
    link_re: re.Pattern[str],
    *,
    ignored_slugs: frozenset[str] = frozenset(),
    ignored_prefixes: tuple[str, ...] = (),
    initial_names: list[str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    names: list[str] = list(initial_names or [])
    seen_names: set[str] = set(names)
    slug_map: dict[str, str] = {}

    for link in soup.find_all("a", href=True):
        match = link_re.match(str(link["href"]))
        if not match:
            continue
        slug = match.group(1).lower()
        if slug in ignored_slugs or (ignored_prefixes and slug.startswith(ignored_prefixes)):
            continue
        label = link.get_text(" ", strip=True)
        if not label or len(label) > _MAX_LABEL_LENGTH:
            continue
        slug_map.setdefault(label.lower(), slug)
        if label not in seen_names:
            seen_names.add(label)
            names.append(label)

    return names, slug_map


def _extract_ssr_model_names(soup: BeautifulSoup) -> list[str]:
    payload = extract_bulls_list_ssr_payload(soup)
    if payload is None:
        return []
    models_groups = (payload.get("filter") or {}).get("models")
    if not isinstance(models_groups, list):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for group in models_groups:
        if not isinstance(group, dict):
            continue
        for item in (group.get("top") or []) + (group.get("regular") or []):
            if not isinstance(item, dict) or not item.get("name"):
                continue
            name = str(item["name"]).strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def parse_brand_models_from_html(html: str, make_slug: str) -> tuple[list[str], dict[str, str]]:
    """Extract model names and slug map from a Drom brand page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    ssr_names = _extract_ssr_model_names(soup)
    escaped_make = re.escape(make_slug.strip("/").lower())
    link_re = re.compile(rf"^https://auto\.drom\.ru/{escaped_make}/([a-z0-9_-]+)/$", re.IGNORECASE)
    return _extract_directory_links(
        soup,
        link_re,
        ignored_slugs=_IGNORED_SALES_SLUGS,
        ignored_prefixes=_IGNORED_SALES_PREFIXES,
        initial_names=ssr_names,
    )


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
    return _extract_directory_links(soup, link_re)
