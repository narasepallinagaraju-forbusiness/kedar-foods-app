"""Unit tests for the public catalogue index builder."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from api.handlers.catalog_index import build_catalog_index

NOW = datetime(2026, 10, 7, 6, 20, tzinfo=UTC)


def _product(**overrides: Any) -> dict[str, Any]:
    return {
        "productId": "prod_0000000001",
        "sku": "KF-01",
        "slug": "sample-product",
        "name": "Sample Product",
        "brand": "Sample Brand",
        "category": "Dairy",
        "businessType": ["Cafe", "Bakery"],
        "quantities": ["500 g", "1 kg"],
        "image": {
            "card": "media/products/prod_0000000001/card-v1.webp",
            "main": "media/products/prod_0000000001/main-v1.webp",
        },
        "isTrending": True,
        "sortRank": 10,
        "status": "PUBLISHED",
        "description": "Private long description",
        "version": 4,
        "createdBy": "seed",
        "updatedBy": "seed",
        **overrides,
    }


def test_catalog_index_includes_only_published_products() -> None:
    index = build_catalog_index(
        [
            _product(),
            _product(productId="prod_draft", status="DRAFT"),
            _product(productId="prod_archived", status="ARCHIVED"),
        ],
        NOW,
    )

    assert [item["id"] for item in index["items"]] == ["prod_0000000001"]


def test_index_items_have_exact_public_fields_and_card_thumbnail_only() -> None:
    item = build_catalog_index([_product()], NOW)["items"][0]

    assert set(item) == {
        "id",
        "sku",
        "slug",
        "name",
        "brand",
        "category",
        "businessType",
        "quantities",
        "thumbnailKey",
        "isTrending",
        "searchText",
        "sortRank",
    }
    assert item["thumbnailKey"] == "media/products/prod_0000000001/card-v1.webp"
    assert "image" not in item
    assert "description" not in item
    assert "status" not in item
    assert "version" not in item
    assert "createdBy" not in item
    assert "updatedBy" not in item
    assert "main-v1.webp" not in str(item)


def test_search_text_is_lowercase_name_brand_and_category() -> None:
    item = build_catalog_index([_product()], NOW)["items"][0]

    assert item["searchText"] == "sample product sample brand dairy"


def test_index_is_sorted_by_sort_rank_then_name() -> None:
    index = build_catalog_index(
        [
            _product(productId="prod_z", name="Zulu", sortRank=Decimal("20")),
            _product(productId="prod_b", name="Beta", sortRank=10),
            _product(productId="prod_a", name="Alpha", sortRank=Decimal("10")),
        ],
        NOW,
    )

    assert [item["id"] for item in index["items"]] == [
        "prod_a",
        "prod_b",
        "prod_z",
    ]


def test_decimal_sort_rank_converts_to_int_and_naive_timestamp_is_utc() -> None:
    index = build_catalog_index(
        [_product(sortRank=Decimal("12"))],
        datetime(2026, 10, 7, 6, 20),
    )

    assert index["items"][0]["sortRank"] == 12
    assert isinstance(index["items"][0]["sortRank"], int)
    assert index["version"] == "2026-10-07T06:20:00Z"


def test_missing_image_omits_thumbnail_key() -> None:
    item = build_catalog_index([_product(image=None)], NOW)["items"][0]

    assert "thumbnailKey" not in item


def test_empty_products_returns_versioned_empty_index() -> None:
    assert build_catalog_index([], NOW) == {
        "version": "2026-10-07T06:20:00Z",
        "items": [],
    }
