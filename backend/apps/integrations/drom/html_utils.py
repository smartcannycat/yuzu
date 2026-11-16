import json
from typing import Any

from bs4 import BeautifulSoup

_SSR_SLUG_MARKERS = ('"__slug":"bulls-list-auto"', '"__slug": "bulls-list-auto"')


def extract_bulls_list_ssr_payload(html_or_soup: str | BeautifulSoup) -> dict[str, Any] | None:
    """Find and parse the embedded Drom bulls-list-auto SSR JSON script block."""
    soup = (
        html_or_soup
        if isinstance(html_or_soup, BeautifulSoup)
        else BeautifulSoup(html_or_soup, "html.parser")
    )
    for script in soup.find_all("script"):
        text = script.string or ""
        if not any(marker in text for marker in _SSR_SLUG_MARKERS):
            continue
        try:
            payload = json.loads(text)
        except ValueError:
            continue
        if isinstance(payload, dict):
            return payload
    return None
