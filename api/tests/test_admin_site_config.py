"""Tests for admin site-config (offer banner) routes."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from api.handlers.admin_auth import clear_admin_key_cache
from api.handlers.admin_site_config import handler

from .admin_fakes import SITE_CONFIG, FakeSiteConfigTable, FakeSsm

KEY = "k" * 40


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ADMIN_KEY_PARAMETER", "/test/admin-key")
    clear_admin_key_cache()
    yield
    clear_admin_key_cache()


def _call(
    table: FakeSiteConfigTable,
    route: str,
    body: Any = None,
    key: str | None = KEY,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "routeKey": route,
        "headers": {} if key is None else {"x-admin-key": key},
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return handler(event, None, table=table, ssm_client=FakeSsm())


def test_routes_require_the_admin_key() -> None:
    table = FakeSiteConfigTable(SITE_CONFIG)

    for route in ("GET /admin/site-config", "PUT /admin/site-config/offer"):
        assert _call(table, route, {"enabled": False}, key=None)["statusCode"] == 401
    assert table.item is not None
    assert table.item["offerBanner"]["enabled"] is False


def test_get_returns_stored_offer_only() -> None:
    table = FakeSiteConfigTable(SITE_CONFIG)

    response = _call(table, "GET /admin/site-config")

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"offerBanner": SITE_CONFIG["offerBanner"]}


def test_put_updates_only_the_offer() -> None:
    table = FakeSiteConfigTable(SITE_CONFIG)
    offer = {"enabled": True, "text": " Festival offer ", "link": "/catalogue"}

    response = _call(table, "PUT /admin/site-config/offer", offer)

    assert response["statusCode"] == 200
    assert table.item is not None
    assert table.item["offerBanner"] == {
        "enabled": True,
        "text": "Festival offer",
        "link": "/catalogue",
    }
    assert table.item["categories"] == SITE_CONFIG["categories"]


def test_put_keeps_the_stored_poster_and_stores_valid_dates() -> None:
    stored = {
        **SITE_CONFIG,
        "offerBanner": {
            "enabled": False,
            "text": "",
            "link": "",
            "image": "media/offer/poster-v9.webp",
        },
    }
    table = FakeSiteConfigTable(stored)
    offer = {
        "enabled": True,
        "text": "Sale",
        "startDate": "2026-10-01",
        "endDate": "2026-10-31",
    }

    response = _call(table, "PUT /admin/site-config/offer", offer)

    assert response["statusCode"] == 200
    assert table.item is not None
    assert table.item["offerBanner"]["image"] == "media/offer/poster-v9.webp"
    assert table.item["offerBanner"]["startDate"] == "2026-10-01"
    assert table.item["offerBanner"]["endDate"] == "2026-10-31"


@pytest.mark.parametrize(
    "body",
    [
        {"enabled": True, "text": "x", "link": "//evil.com"},
        {"enabled": True, "text": "x", "link": "/\\evil.com"},
        {"enabled": True, "text": ""},
        {"enabled": True, "text": "x" * 161},
        {"enabled": True, "text": "x", "image": "p.png"},
        {"text": "x"},
    ],
)
def test_put_rejects_invalid_offers(body: dict[str, Any]) -> None:
    table = FakeSiteConfigTable(SITE_CONFIG)

    response = _call(table, "PUT /admin/site-config/offer", body)

    assert response["statusCode"] == 400
    assert table.item is not None
    assert table.item["offerBanner"] == SITE_CONFIG["offerBanner"]


def test_missing_config_item_returns_404_and_unknown_route_404() -> None:
    table = FakeSiteConfigTable(None)

    assert _call(table, "GET /admin/site-config")["statusCode"] == 404
    assert (
        _call(table, "PUT /admin/site-config/offer", {"enabled": False})[
            "statusCode"
        ]
        == 404
    )
    assert _call(table, "GET /admin/other")["statusCode"] == 404


def test_missing_body_is_a_400() -> None:
    table = FakeSiteConfigTable(SITE_CONFIG)

    assert _call(table, "PUT /admin/site-config/offer")["statusCode"] == 400
