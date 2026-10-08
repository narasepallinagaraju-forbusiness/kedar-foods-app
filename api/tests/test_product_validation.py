"""Unit tests for admin product and offer validation."""

from __future__ import annotations

from typing import Any

import pytest

from api.handlers.product_validation import (
    ProductValidationError,
    product_id_from_sku,
    safe_link,
    slugify,
    unique_slug,
    validate_create_product,
    validate_offer,
    validate_update_product,
)

CATEGORIES = {"Dairy", "Chocolate"}


def _body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "sku": "KF-12",
        "name": "  Amul Cream  ",
        "brand": "Amul",
        "category": "Dairy",
        "businessType": ["Bakery", "Cafe"],
        "quantities": ["500g", " 1 kg "],
    }
    body.update(overrides)
    return body


def _fields(error: ProductValidationError) -> set[str]:
    return {item["field"] for item in error.errors}


def test_create_returns_cleaned_fields_and_hidden_default_status() -> None:
    clean = validate_create_product(_body(), CATEGORIES)

    assert clean["name"] == "Amul Cream"
    assert clean["quantities"] == ["500g", "1 kg"]
    assert clean["businessType"] == ["Bakery", "Cafe"]
    assert clean["status"] == "ARCHIVED"
    assert clean["sku"] == "KF-12"
    assert isinstance(clean["quantities"], list)


def test_create_accepts_published_status_and_optional_fields() -> None:
    clean = validate_create_product(
        _body(status="PUBLISHED", isTrending=True, sortRank=30, description=" x "),
        CATEGORIES,
    )

    assert clean["status"] == "PUBLISHED"
    assert clean["isTrending"] is True
    assert clean["sortRank"] == 30
    assert clean["description"] == "x"


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"sku": "kf-12"}, "sku"),
        ({"sku": "K"}, "sku"),
        ({"sku": None}, "sku"),
        ({"name": "A"}, "name"),
        ({"name": "x" * 121}, "name"),
        ({"name": "bad\x00name"}, "name"),
        ({"name": 5}, "name"),
        ({"brand": ""}, "brand"),
        ({"category": "Beverages"}, "category"),
        ({"businessType": []}, "businessType"),
        ({"businessType": ["Hotel"]}, "businessType"),
        ({"businessType": ["Cafe", "Cafe"]}, "businessType"),
        ({"quantities": []}, "quantities"),
        ({"quantities": ["1kg", "1kg"]}, "quantities"),
        ({"quantities": ["x" * 21]}, "quantities"),
        ({"quantities": [1]}, "quantities"),
        ({"quantities": [str(i) for i in range(13)]}, "quantities"),
        ({"description": "x" * 2001}, "description"),
        ({"isTrending": "yes"}, "isTrending"),
        ({"sortRank": 1.5}, "sortRank"),
        ({"sortRank": True}, "sortRank"),
        ({"sortRank": -1}, "sortRank"),
        ({"sortRank": 100_001}, "sortRank"),
        ({"status": "DRAFT"}, "status"),
        ({"image": {"card": "media/x.webp"}}, "image"),
        ({"slug": "chosen-slug"}, "slug"),
        ({"productId": "prod_1"}, "productId"),
    ],
)
def test_create_rejects_invalid_or_unknown_fields(
    overrides: dict[str, Any], field: str
) -> None:
    with pytest.raises(ProductValidationError) as raised:
        validate_create_product(_body(**overrides), CATEGORIES)

    assert field in _fields(raised.value)


def test_create_reports_every_problem_and_rejects_non_objects() -> None:
    with pytest.raises(ProductValidationError) as raised:
        validate_create_product({}, CATEGORIES)
    assert {"sku", "name", "brand", "category"} <= _fields(raised.value)

    with pytest.raises(ProductValidationError) as raised:
        validate_create_product([], CATEGORIES)
    assert _fields(raised.value) == {"body"}


def test_update_returns_fields_and_version_without_immutable_keys() -> None:
    body = _body(version=3)
    del body["sku"]

    clean, version = validate_update_product(body, CATEGORIES)

    assert version == 3
    assert clean["name"] == "Amul Cream"
    assert "sku" not in clean
    assert "sortRank" not in clean


@pytest.mark.parametrize(
    "overrides",
    [
        {"version": None},
        {"version": 0},
        {"version": 1.0},
        {"version": True},
        {"sku": "KF-13"},
        {"status": "PUBLISHED"},
        {"slug": "new-slug"},
        {"image": {}},
    ],
)
def test_update_rejects_bad_version_and_immutable_keys(
    overrides: dict[str, Any],
) -> None:
    body = _body(version=1)
    del body["sku"]
    body.update(overrides)

    with pytest.raises(ProductValidationError):
        validate_update_product(body, CATEGORIES)


def test_slug_and_product_id_are_deterministic() -> None:
    assert slugify("Amul Unsalted Butter!") == "amul-unsalted-butter"
    assert product_id_from_sku("KF-01") == "prod_bda83ddba6"
    assert product_id_from_sku("KF-01") == product_id_from_sku("KF-01")
    with pytest.raises(ValueError):
        slugify("***")


def test_unique_slug_adds_brand_then_sku() -> None:
    assert unique_slug("Cream", "Amul", "KF-12", lambda _s: False) == "cream"
    assert unique_slug("Cream", "Amul", "KF-12", {"cream"}.__contains__) == (
        "cream-amul"
    )
    assert unique_slug(
        "Cream", "Amul", "KF-12", {"cream", "cream-amul"}.__contains__
    ) == "cream-amul-kf-12"
    with pytest.raises(ValueError):
        unique_slug("Cream", "Amul", "KF-12", lambda _s: True)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/catalogue", "/catalogue"),
        ("https://example.com/x", "https://example.com/x"),
        ("//evil.com", None),
        ("/\\evil.com", None),
        ("javascript:alert(1)", None),
        ("http://example.com", None),
        ("https://", None),
        ("", None),
        (None, None),
        (5, None),
        ("/a b", None),
        ("/a\nb", None),
    ],
)
def test_safe_link_matches_customer_rule(value: object, expected: str | None) -> None:
    assert safe_link(value) == expected


def test_offer_accepts_valid_values_and_trims_text() -> None:
    assert validate_offer(
        {"enabled": True, "text": " 10% off ", "link": "/catalogue"}
    ) == {"enabled": True, "text": "10% off", "link": "/catalogue"}
    assert validate_offer({"enabled": False}) == {
        "enabled": False,
        "text": "",
        "link": "",
    }


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"enabled": "yes", "text": "x"}, "enabled"),
        ({"text": "x"}, "enabled"),
        ({"enabled": True, "text": ""}, "text"),
        ({"enabled": True, "text": "x" * 161}, "text"),
        ({"enabled": True, "text": "a\x00b"}, "text"),
        ({"enabled": True, "text": "x", "link": "//evil.com"}, "link"),
        ({"enabled": True, "text": "x", "link": "http://x.com"}, "link"),
        ({"enabled": True, "text": "x", "link": "/" + "a" * 200}, "link"),
        ({"enabled": True, "text": "x", "image": "p.png"}, "image"),
        ({"enabled": True, "text": "x", "startsAt": "2026-01-01"}, "startsAt"),
    ],
)
def test_offer_rejects_invalid_values(body: dict[str, Any], field: str) -> None:
    with pytest.raises(ProductValidationError) as raised:
        validate_offer(body)

    assert field in _fields(raised.value)


def test_offer_rejects_non_objects() -> None:
    with pytest.raises(ProductValidationError):
        validate_offer("on")


def test_offer_accepts_schedule_dates_and_drops_blank_ones() -> None:
    assert validate_offer(
        {
            "enabled": True,
            "text": "x",
            "startDate": "2026-10-01",
            "endDate": "2026-10-31",
        }
    ) == {
        "enabled": True,
        "text": "x",
        "link": "",
        "startDate": "2026-10-01",
        "endDate": "2026-10-31",
    }
    assert validate_offer({"enabled": False, "startDate": "", "endDate": None}) == {
        "enabled": False,
        "text": "",
        "link": "",
    }
    assert validate_offer(
        {"enabled": False, "startDate": "2026-10-05", "endDate": "2026-10-05"}
    )["endDate"] == "2026-10-05"


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"enabled": False, "startDate": "01-10-2026"}, "startDate"),
        ({"enabled": False, "endDate": "2026-02-30"}, "endDate"),
        ({"enabled": False, "startDate": 20261001}, "startDate"),
        (
            {"enabled": False, "startDate": "2026-10-10", "endDate": "2026-10-09"},
            "endDate",
        ),
    ],
)
def test_offer_rejects_bad_schedule(body: dict[str, Any], field: str) -> None:
    with pytest.raises(ProductValidationError) as raised:
        validate_offer(body)

    assert field in _fields(raised.value)
