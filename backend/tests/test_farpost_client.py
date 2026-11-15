"""Listing parsing, compatibility filters and transport failures for BE-07."""

import time
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from apps.lots.integrations.farpost.client import (
    FarpostClient,
    FarpostFetchError,
    FarpostRateLimitedError,
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


def test_client_requests_local_used_parts_and_decodes_cp1251():
    def handler(request):
        assert request.url.params["goodPresentState"] == "present"
        assert request.url.params["condition[]"] == "used"
        assert "NRE210" in request.url.params["query"]
        html = listing().replace("<title>", '<meta charset="windows-1251"><title>')
        return httpx.Response(200, content=html.encode("cp1251", errors="xmlcharrefreplace"))

    client = FarpostClient(transport=httpx.MockTransport(handler))
    assert client.search(CRITERIA, deadline=time.monotonic() + 20)[0].price_rub == 18000


@pytest.mark.parametrize("status", [403, 429, 500])
def test_http_errors_are_not_empty_results(status):
    client = FarpostClient(transport=httpx.MockTransport(lambda _request: httpx.Response(status)))
    with pytest.raises(FarpostFetchError):
        client.search(CRITERIA, deadline=time.monotonic() + 20)


def test_exhausted_budget_does_not_request():
    def handler(request):
        pytest.fail("Network must not be called after the lot deadline")

    client = FarpostClient(transport=httpx.MockTransport(handler))
    with pytest.raises(FarpostFetchError, match="budget"):
        client.search(CRITERIA, deadline=time.monotonic() - 1)


def test_new_or_unknown_condition_is_not_a_contract_part():
    assert parse(listing(annotation="Новая деталь")) == []


def test_network_timeout_is_a_source_error():
    def handler(request):
        raise httpx.ReadTimeout("source timed out")

    client = FarpostClient(transport=httpx.MockTransport(handler))
    with pytest.raises(FarpostFetchError, match="request failed"):
        client.search(CRITERIA, deadline=time.monotonic() + 20)


def test_farpost_noindex_link_wrapper_preserves_local_offer():
    offers = parse(listing(href="/ni/vladivostok/zapchasti/door-123.html"))
    assert len(offers) == 1


@pytest.mark.parametrize(
    "title,annotation",
    [
        ("Решетка переднего бампера Toyota Corolla NRE210", ""),
        ("Усилитель переднего бампера Toyota Corolla NRE210", ""),
        ("Стекло передней левой двери Toyota Corolla NRE210 цвет 070", ""),
        ("Дверь передняя левая Toyota Corolla NRE210 цвет 070", "Дубликат SAT, Тайвань"),
    ],
)
def test_rejects_expanded_accessories_and_aftermarket(title, annotation):
    assert parse(listing(title, annotation=annotation), replace(CRITERIA, paint_code="")) == []


def test_rejects_stub_prices_below_threshold():
    assert parse(listing(price="500₽")) == []


def test_accepts_used_listing_without_literal_kontrakt_and_abbreviations():
    offers = parse(
        listing(
            "Дверь п/л Toyota Corolla NRE210 цвет ПЕРЛАМУТР 070",
            annotation="Отличное состояние",
        )
    )
    assert len(offers) == 1
    assert offers[0].color_matched


def test_accepts_cyrillic_make_model_one_digit_body_and_paint_code():
    criteria = PartCriteria(
        "Honda", "Freed", "GB5", "front_left_door", "дверь", "левая", "передняя", "NH883P"
    )
    offers = parse(
        listing("Дверь передняя левая Хонда Фрид GB5 NH883P", annotation=""),
        criteria,
    )
    assert len(offers) == 1
    assert offers[0].color_matched


def test_trim_grades_do_not_trigger_side_or_position_false_positives():
    criteria_right = PartCriteria(
        "Toyota", "Aqua", "NHP10", "front_right_door", "дверь", "правая", "передняя", ""
    )
    assert (
        parse(listing("Дверь передняя левая Toyota Aqua NHP10 L", annotation=""), criteria_right)
        == []
    )
    criteria_rear = PartCriteria(
        "Toyota", "Vitz", "KSP130", "rear_left_door", "дверь", "левая", "задняя", ""
    )
    assert (
        parse(listing("Дверь передняя левая Toyota Vitz KSP130 F", annotation=""), criteria_rear)
        == []
    )


def test_tailgate_and_windshield_synonyms_without_false_door_matches():
    tailgate = PartCriteria("Honda", "Freed", "GB5", "tailgate", "багажник", "", "", "")
    assert len(parse(listing("Дверь 5-я Honda Freed GB5", annotation=""), tailgate)) == 1
    assert parse(listing("Дверь задняя левая Honda Freed GB5", annotation=""), tailgate) == []

    windshield = PartCriteria("Honda", "Fit", "GE6", "windshield", "стекло", "", "лобовое", "")
    assert len(parse(listing("Ветровое стекло Honda Fit GE6", annotation=""), windshield)) == 1


def test_verify_redirect_and_429_raise_rate_limited_and_context_manager_reuses_cookies():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "verify" in str(request.url):
            return httpx.Response(200, text="<title>Проверка</title>")
        if len(requests) == 1:
            return httpx.Response(
                200,
                text=listing(),
                headers={"Set-Cookie": "ring=abc123; Path=/"},
            )
        return httpx.Response(302, headers={"Location": "https://www.farpost.ru/verify"})

    with FarpostClient(transport=httpx.MockTransport(handler)) as client:
        assert len(client.search(CRITERIA, deadline=time.monotonic() + 20)) == 1
        with pytest.raises(FarpostRateLimitedError):
            client.search(CRITERIA, deadline=time.monotonic() + 20)
    assert "ring=abc123" in requests[1].headers.get("cookie", "")


def test_unchecked_stock_filter_with_zero_exact_feed_returns_empty_without_error():
    html = """<html><title>Купить б/у бампер</title>
    <script id="ctr-viewdir-event" type="application/json">{"exactFeedCount":0}</script>
    <input name="goodPresentState" value="" checked>
    <div class="bull-item" data-good-id="999">
      <a data-role="bulletin-link" href="/vladivostok/zapchasti/bumper-999.html">
        Бампер передний Honda Freed GT5 NH883P
      </a>
      <div class="price-block__final-price"><div data-role="price">15 000₽</div></div>
    </div></html>"""
    result = parse(
        html,
        PartCriteria("Honda", "Freed", "GB5", "front_bumper", "бампер", "", "передний", "NH883P"),
    )
    assert result == []


def test_accepts_complete_parts_sold_in_assembly_and_rejects_standalone_accessories():
    door_in_assembly = listing(
        "Дверь передняя левая Toyota Corolla NRE210 в сборе с ручкой, замком и зеркалом",
        annotation="Контрактная, без повреждений",
    )
    assert len(parse(door_in_assembly, replace(CRITERIA, paint_code=""))) == 1

    bumper_with_grille = listing(
        "Бампер передний Honda Freed GB5 с решеткой и туманками",
        annotation="Контрактный, без дефектов",
    )
    freed = PartCriteria("Honda", "Freed", "GB5", "front_bumper", "бампер", "", "передний", "")
    assert len(parse(bumper_with_grille, freed)) == 1

    standalone_handle = listing(
        "Ручка двери передней левой Toyota Corolla NRE210",
        annotation="",
    )
    assert parse(standalone_handle, replace(CRITERIA, paint_code="")) == []


def test_relaxed_make_or_model_when_exact_body_code_matches_and_blocks_foreign_make():
    # Missing brand word ("Toyota") when model + exact body_code match
    no_make = listing("Дверь передняя левая Corolla NRE210 цвет 070", annotation="")
    assert len(parse(no_make)) == 1

    # Missing model word ("Impreza") when make + exact body_code match
    subaru = PartCriteria(
        "Subaru", "Impreza", "GP2", "front_left_fender", "крыло", "левое", "переднее", ""
    )
    no_model = listing("Крыло переднее левое Subaru GP2", annotation="")
    assert len(parse(no_model, subaru)) == 1

    # Farpost sister manufacturer tag on Lexus LS500
    lexus = PartCriteria("Lexus", "LS500", "VXFA50", "front_bumper", "бампер", "", "передний", "")
    ls500 = listing("Бампер Lexus LS500 5211950F20 VXFA50, передний", annotation="Toyota")
    assert len(parse(ls500, lexus)) == 1

    # Conflicting make still rejected even if body code appears in compatibility list
    foreign_make = listing(
        "Дверь передняя левая Honda NRE210 цвет 070",
        annotation="",
    )
    assert parse(foreign_make) == []


def test_plural_fender_wordform_and_snippet_preserved():
    subaru = PartCriteria(
        "Subaru", "Impreza", "GP2", "front_left_fender", "крыло", "левое", "переднее", ""
    )
    html = listing(
        "Крылья Subaru Impreza GP2, переднее левое",
        annotation="Цвет NH883P в идеале",
    )
    offers = parse(html, subaru)
    assert len(offers) == 1
    assert "NH883P" in offers[0].snippet


def test_client_fetches_second_page_only_when_page1_filtered_empty_and_feed_exceeds_50():
    pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "1")
        pages.append(page)
        if page == "1":
            return httpx.Response(
                200,
                text="""<html><title>Запчасти</title>
                <input name="goodPresentState" value="present" checked>
                <script id="ctr-viewdir-event">{"exactFeedCount":116}</script>
                <div class="bull-item" data-good-id="1">
                  <a data-role="bulletin-link" href="/vladivostok/zapchasti/1.html">
                    Крыло Subaru Impreza GJ2 переднее левое
                  </a>
                  <div class="price-block__final-price"><div data-role="price">2 000₽</div></div>
                </div></html>""",
            )
        return httpx.Response(
            200,
            text="""<html><title>Запчасти</title>
            <input name="goodPresentState" value="present" checked>
            <script id="ctr-viewdir-event">{"exactFeedCount":116}</script>
            <div class="bull-item" data-good-id="2">
              <a data-role="bulletin-link" href="/vladivostok/zapchasti/2.html">
                Крыло Subaru Impreza GP2 переднее левое
              </a>
              <div class="price-block__final-price"><div data-role="price">4 500₽</div></div>
            </div></html>""",
        )

    criteria = PartCriteria(
        "Subaru", "Impreza", "GP2", "front_left_fender", "крыло", "левое", "переднее", ""
    )
    client = FarpostClient(transport=httpx.MockTransport(handler))
    result = client.search_with_metadata(criteria, deadline=time.monotonic() + 20)
    assert pages == ["1", "2"]
    assert len(result.offers) == 1
    assert result.offers[0].price_rub == 4500
    assert result.exact_feed_count == 116


def test_client_rotates_proxies_on_verify_challenge():
    attempts: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # MockTransport verifies retry count cleanly while session tracks used proxies.
        attempts.append(str(request.url))
        if len(attempts) == 1:
            return httpx.Response(302, headers={"Location": "https://www.farpost.ru/verify"})
        if "verify" in str(request.url):
            return httpx.Response(200, text="<title>Проверка</title>")
        return httpx.Response(200, text=listing())

    client = FarpostClient(
        proxy_urls=["http://user:secret@p1:8080", "http://user:secret@p2:8080"],
        transport=httpx.MockTransport(handler),
    )
    offers = client.search(replace(CRITERIA, paint_code=""), deadline=time.monotonic() + 20)
    assert len(offers) == 1
    assert len(attempts) == 3  # 1st attempt + redirect -> /verify, then 2nd proxy attempt


def test_shipping_and_liter_words_do_not_trigger_side_false_positives():
    left_with_shipping = listing(
        "Дверь передняя левая Toyota Corolla NRE210 отправка в регионы",
        annotation="",
    )
    assert len(parse(left_with_shipping, replace(CRITERIA, paint_code=""))) == 1

    right_criteria = replace(CRITERIA, panel_id="front_right_door", side="правая", paint_code="")
    right_with_liters = listing(
        "Дверь передняя правая Toyota Corolla NRE210 1.5 л.",
        annotation="",
    )
    assert len(parse(right_with_liters, right_criteria)) == 1

    ambiguous_with_shipping = listing(
        "Дверь передняя Toyota Corolla NRE210 отправка в регионы",
        annotation="",
    )
    assert parse(ambiguous_with_shipping, right_criteria) == []


def test_assembly_so_and_window_vent_are_accepted_while_accessories_rejected():
    door_with_vent = listing(
        "Дверь передняя левая Toyota Corolla NRE210 со стеклоподъемником и форточкой",
        annotation="",
    )
    assert len(parse(door_with_vent, replace(CRITERIA, paint_code=""))) == 1

    standalone_vent = listing(
        "Форточка двери передней левой Toyota Corolla NRE210",
        annotation="",
    )
    assert parse(standalone_vent, replace(CRITERIA, paint_code="")) == []


def test_conflicting_make_ignores_substrings_and_catches_short_brands():
    ok_substrings = listing(
        "Дверь передняя левая Corolla NRE210",
        annotation="Минимальные сколы, под Display Audio",
    )
    assert len(parse(ok_substrings, replace(CRITERIA, paint_code=""))) == 1

    kia_conflict = listing(
        "Дверь передняя левая Kia Corolla NRE210",
        annotation="",
    )
    assert parse(kia_conflict, replace(CRITERIA, paint_code="")) == []


def test_paint_code_rejects_negations_and_handles_split_spans():
    from apps.lots.integrations.farpost.client import matches_paint_code

    assert not matches_paint_code("Цвет другой (не 070)", "070")
    assert not matches_paint_code("Цвет красный, пробег 070 тыс", "070")

    freed = PartCriteria(
        "Honda", "Freed", "GB5", "front_left_door", "дверь", "левая", "передняя", "NH883P"
    )
    split_span_html = listing(
        "Дверь передняя левая Honda Freed GB5 NH<span>883P</span>", annotation=""
    )
    offers = parse(split_span_html, freed)
    assert len(offers) == 1
    assert offers[0].color_matched is True


def test_page2_error_falls_back_to_empty_and_unpriced_rows_are_recognized():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(503)
        return httpx.Response(
            200,
            text="""<html><title>Запчасти</title>
            <input name="goodPresentState" value="present" checked>
            <script id="ctr-viewdir-event">{"exactFeedCount":116}</script>
            <div class="bull-item" data-good-id="1">
              <a data-role="bulletin-link" href="/vladivostok/zapchasti/1.html">
                Крыло Subaru Impreza GJ2 переднее левое
              </a>
              <div class="price-block__final-price"><div data-role="price">2 000₽</div></div>
            </div></html>""",
        )

    subaru = PartCriteria(
        "Subaru", "Impreza", "GP2", "front_left_fender", "крыло", "левое", "переднее", ""
    )
    client = FarpostClient(transport=httpx.MockTransport(handler))
    res = client.search_with_metadata(subaru, deadline=time.monotonic() + 20)
    assert res.offers == []
    assert res.exact_feed_count == 116

    unpriced_html = """<html><title>Запчасти</title>
    <input name="goodPresentState" value="present" checked>
    <script id="ctr-viewdir-event">{"exactFeedCount":5}</script>
    <div class="bull-item" data-good-id="11">
      <a data-role="bulletin-link" href="/vladivostok/zapchasti/11.html">
        Дверь передняя левая Toyota Corolla NRE210
      </a>
    </div></html>"""
    assert parse(unpriced_html, replace(CRITERIA, paint_code="")) == []


def test_proxy_rotation_isolates_cookies_across_proxies():
    seen_cookies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "verify" in str(request.url):
            return httpx.Response(200, text="<title>Проверка</title>")
        seen_cookies.append(request.headers.get("cookie", ""))
        if len(seen_cookies) == 1:
            return httpx.Response(
                302,
                headers={
                    "Location": "https://www.farpost.ru/verify",
                    "Set-Cookie": "tainted_verify=1; Path=/",
                },
            )
        return httpx.Response(200, text=listing())

    with FarpostClient(
        proxy_urls=["http://p1:8080", "http://p2:8080"],
        transport=httpx.MockTransport(handler),
    ) as client:
        offers = client.search(replace(CRITERIA, paint_code=""), deadline=time.monotonic() + 20)
    assert len(offers) == 1
    assert seen_cookies == ["", ""]
