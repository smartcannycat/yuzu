"""Process-local shared cookie store and single-flight login locks for Aleado."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

type SessionKey = tuple[str, str]
type CookieTuple = tuple[str, str, str, str]

_STORE_LOCK = threading.Lock()
_LOGIN_LOCKS: dict[SessionKey, threading.Lock] = {}
_SHARED_COOKIES: dict[SessionKey, tuple[int, list[CookieTuple]]] = {}

FINDLOTS_SEARCH_PARAMS: dict[str, str] = {
    "p": "project/findlots",
    "ld": "",
    "s": "",
    "o": "d",
    "vs": "20",
    "pg": "1",
    "rows": "20",
    "date_check": "1",
    "auction_check": "1",
    "photo_check": "1",
    "company_check": "1",
    "model_check": "1",
    "grade_check": "1",
    "year_check": "1",
    "transmission_check": "1",
    "displacement_check": "1",
    "mileage_check": "1",
    "model_type_check": "1",
    "start_price_check": "1",
    "end_price_check": "1",
    "result_check": "1",
    "scores_check": "1",
    "mrk": "2",
    "exch": "jpy",
    "type_pos": "contains",
}


def clear_shared_sessions() -> None:
    """Drop all cached Aleado cookie jars and per-account login locks."""
    with _STORE_LOCK:
        _SHARED_COOKIES.clear()
        _LOGIN_LOCKS.clear()


def get_login_lock(key: SessionKey) -> threading.Lock:
    """Return the process-wide single-flight login lock for ``(base_url, username)``."""
    with _STORE_LOCK:
        lock = _LOGIN_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOGIN_LOCKS[key] = lock
        return lock


def load_shared_cookies(key: SessionKey) -> tuple[int, list[CookieTuple]]:
    """Return ``(generation, cookie_tuples)`` currently stored for ``key``."""
    with _STORE_LOCK:
        gen, cookies = _SHARED_COOKIES.get(key, (0, []))
        return gen, list(cookies)


def save_shared_cookies(key: SessionKey, cookies: httpx.Cookies) -> int:
    """Persist cookies from ``cookies`` and bump the session generation counter."""
    items: list[CookieTuple] = [
        (cookie.name, cookie.value or "", cookie.domain or "", cookie.path or "/")
        for cookie in cookies.jar
    ]
    with _STORE_LOCK:
        prev_gen = _SHARED_COOKIES.get(key, (0, []))[0]
        next_gen = prev_gen + 1
        _SHARED_COOKIES[key] = (next_gen, items)
        return next_gen


def apply_cookies(target: httpx.Cookies, items: list[CookieTuple]) -> None:
    """Replace ``target`` cookie jar contents with serialized ``items``."""
    target.clear()
    for name, value, domain, path in items:
        target.set(name, value, domain=domain, path=path)


def init_client_cookies(key: SessionKey, target: httpx.Cookies) -> int:
    """Seed a fresh client cookie jar from the shared store when already authenticated."""
    generation, items = load_shared_cookies(key)
    if generation > 0 and items:
        apply_cookies(target, items)
    return generation


def ensure_session(
    key: SessionKey,
    current_generation: int,
    target: httpx.Cookies,
    login_fn: Callable[[], None],
) -> int:
    """Ensure ``target`` holds authenticated cookies using a single-flight login."""
    stored_gen, stored_items = load_shared_cookies(key)
    if stored_gen > 0 and stored_items:
        if stored_gen != current_generation:
            apply_cookies(target, stored_items)
        return stored_gen

    with get_login_lock(key):
        stored_gen, stored_items = load_shared_cookies(key)
        if stored_gen > 0 and stored_items:
            apply_cookies(target, stored_items)
            return stored_gen
        login_fn()
        return save_shared_cookies(key, target)


def reauthenticate(
    key: SessionKey,
    failed_generation: int,
    target: httpx.Cookies,
    login_fn: Callable[[], None],
) -> int:
    """Refresh expired shared session once under lock; peers adopt newer cookies."""
    with get_login_lock(key):
        stored_gen, stored_items = load_shared_cookies(key)
        if stored_gen > failed_generation and stored_items:
            apply_cookies(target, stored_items)
            return stored_gen
        target.clear()
        login_fn()
        return save_shared_cookies(key, target)
