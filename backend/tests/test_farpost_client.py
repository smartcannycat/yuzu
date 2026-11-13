"""Listing parsing, compatibility filters and transport failures for BE-07."""

from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from apps.lots.integrations.farpost.client import (
    FarpostFetchError,
    PartCriteria,
    parse_offers,
)

URL = "https://www.farpost.ru/vladivostok/zapchasti/"
CRITERIA = PartCriteria(
    "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", "070"
)


def listing(
    title="Дверь передняя левая Toyota Corolla NRE210 цвет 070",
    *,
    price="18 000₽",
    annotation="Контрактная деталь",
    href="/vladivostok/zapchasti/door-123.html",
):
    return f'''<html><title>Автозапчасти</title>
    <input name="goodPresentState" value="present" checked>
    <div class="bull-item" data-good-id="123">
    <a data-role="bulletin-link" href="{href}">{title}</a>
    <div class="bull-item__annotation">{annotation}</div>
    <div class="price-block__final-price"><div data-role="price">{price}</div></div>
    </div></html>'''


def parse(html, criteria=CRITERIA):
    return parse_offers(html, criteria, source_url=URL)


def test_extracts_compatible_price_and_color():
    (offer,) = parse(listing())
    assert offer.price_rub == 18000
    assert offer.color_matched
    assert offer.offer_id == "123"


@pytest.mark.parametrize(
    "title,annotation",
    [
        ("Обшивка двери передняя левая Toyota Corolla NRE210 цвет 070", ""),
        ("Комплект дверей Toyota Corolla NRE210 передняя левая цвет 070", ""),
        ("Дверь задняя левая Toyota Corolla NRE210 цвет 070", ""),
        ("Дверь передняя правая Toyota Corolla NRE210 цвет 070", ""),
        ("Дверь передняя левая Toyota Corolla NRE211 цвет 070", ""),
        ("Дверь передняя левая Honda Fit NRE210 цвет 070", ""),
        ("Дверь передняя левая Toyota Corolla NRE210 цвет 070", "Есть залом"),
        ("Дверь передняя левая Toyota Corolla NRE210 цвет 070", "Под заказ"),
        ("Дверь передняя левая Toyota Corolla NRE210 цвет 070", "Доставка из Японии"),
        ("Дверь передняя левая Toyota Corolla NRE210 белая", ""),
        ("Дверь передняя левая Toyota Corolla NRE210 цвет 0700", ""),
    ],
)
def test_rejects_incompatible_or_unconfirmed_offers(title, annotation):
    assert parse(listing(title, annotation=annotation)) == []


def test_accepts_color_and_body_code_split_by_highlighting():
    offers = parse(
        listing("Дверь передняя левая Toyota Corolla NRE <span>210</span> цвет: <b>070</b>")
    )
    assert len(offers) == 1


def test_unknown_color_requires_painting():
    offers = parse(
        listing("Дверь передняя левая Toyota Corolla NRE210 белая"),
        replace(CRITERIA, paint_code=""),
    )
    assert offers and not offers[0].color_matched


@pytest.mark.parametrize("price", ["0₽", "-5₽", "1 000 $", "договорная"])
def test_invalid_prices_are_not_quotes(price):
    assert parse(listing(price=price)) == []


def test_nonlocal_and_external_links_are_excluded():
    assert parse(listing(href="/moscow/zapchasti/door-123.html")) == []
    assert parse(listing(href="https://example.com/vladivostok/zapchasti/123")) == []


def test_real_listing_excerpt_requires_confirmed_stock_filter():
    html = (Path(__file__).parent / "fixtures/farpost/live_listing_excerpt.html").read_text()
    with pytest.raises(FarpostFetchError, match="stock"):
        parse(html)
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one('input[name="goodPresentState"][value="present"]')["checked"] = ""
    offers = parse(str(soup))
    assert offers
    assert all(o.price_rub > 0 and o.color_matched for o in offers)


@pytest.mark.parametrize(
    "html",
    [
        "<title>Вы не робот?</title>",
        '<title>Parts</title><input name="goodPresentState" value="present" checked>',
        listing().replace('data-role="bulletin-link"', 'data-role="unknown"'),
    ],
)
def test_challenge_and_changed_markup_are_errors(html):
    with pytest.raises(FarpostFetchError):
        parse(html)


def test_explicit_empty_result_is_valid():
    html = """<input name="goodPresentState" value="present" checked>
    <script id="ctr-viewdir-event" type="application/json">{"exactFeedCount":0}</script>"""
    assert parse(html) == []
