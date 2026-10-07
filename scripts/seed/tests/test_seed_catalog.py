"""Offline tests for parsing, mapping, and image preparation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from scripts.seed.seed_catalog import (
    SeedDataError,
    build_site_config,
    conditional_put,
    create_image_variants,
    map_products,
    parse_export_file,
    parse_export_text,
    rebuild_and_upload_index,
    slugify,
)

NOW = datetime(2026, 10, 7, 6, 20, tzinfo=UTC)


def _source_product(**overrides: Any) -> dict[str, Any]:
    return {
        "id": "KF-01",
        "name": "Amul Unsalted Butter",
        "quantities": ["100g", "500g"],
        "category": "Dairy",
        "brand": "Amul",
        "businessType": ["Bakery", "Cafe"],
        "description": "Butter for baking.",
        "image": "https://example.invalid/butter.jpg",
        "isTrending": True,
        **overrides,
    }


def _source_product_without(field: str) -> dict[str, Any]:
    product = _source_product()
    del product[field]
    return product


def _export_source(
    *,
    products: list[dict[str, Any]] | None = None,
    categories: list[str] | None = None,
) -> str:
    values = {
        "PRODUCTS": [_source_product()] if products is None else products,
        "CATEGORIES": ["Dairy"] if categories is None else categories,
        "WHATSAPP_NUMBER": "917842331013",
        "WHATSAPP_DISPLAY": "+91 78423 31013",
    }
    return "\n".join(
        f"export const {name} = {json.dumps(value)};"
        for name, value in values.items()
    )


def test_parse_actual_portal_export() -> None:
    export = parse_export_file(
        Path(__file__).resolve().parents[3]
        / "seed"
        / "kedar-export-2026-10-07.js"
    )

    assert len(export.products) == 11
    assert export.products[0]["id"] == "KF-01"
    assert export.categories == [
        "Dairy",
        "Baking Essentials",
        "Chocolate",
        "Beverages",
        "Flavours",
        "Frozen Items",
    ]
    assert export.whatsapp_number == "917842331013"
    assert export.whatsapp_display == "+91 78423 31013"


def test_parser_reports_missing_export_constant() -> None:
    source = _export_source().replace(
        'export const WHATSAPP_DISPLAY = "+91 78423 31013";',
        "",
    )

    with pytest.raises(SeedDataError, match="WHATSAPP_DISPLAY"):
        parse_export_text(source)


@pytest.mark.parametrize(
    ("product", "message"),
    [
        (_source_product_without("image"), "missing required field.*image"),
        (_source_product(id=""), "invalid id"),
        (_source_product(quantities="500g"), "quantities must be a string array"),
        (_source_product(isTrending=1), "isTrending must be a boolean"),
    ],
)
def test_parser_rejects_invalid_products(
    product: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(SeedDataError, match=message):
        parse_export_text(_export_source(products=[product]))


def test_parser_rejects_duplicate_ids_and_slugs() -> None:
    product = _source_product(slug="same-slug")
    with pytest.raises(SeedDataError, match="Duplicate product id"):
        parse_export_text(_export_source(products=[product, product.copy()]))

    first = _source_product(slug="same-slug")
    second = _source_product(id="KF-02", slug="same-slug")
    with pytest.raises(SeedDataError, match="Duplicate product slug"):
        parse_export_text(_export_source(products=[first, second]))


def test_parser_rejects_floating_point_values() -> None:
    product = _source_product()
    product["unexpected"] = 1.25

    with pytest.raises(SeedDataError, match="Floating-point value"):
        parse_export_text(_export_source(products=[product]))


def test_slugify_and_brand_then_sku_collision_resolution() -> None:
    assert slugify("  Café & Butter!  ") == "caf-butter"
    collision_products = [
        _source_product(name="Same Name", brand="Same Brand", id="KF-01"),
        _source_product(name="Same Name", brand="Same Brand", id="KF-02"),
        _source_product(name="Same Name", brand="Same Brand", id="KF-03"),
    ]
    reports: list[str] = []

    mapped = map_products(collision_products, NOW, report=reports.append)

    assert [product.item["slug"] for product in mapped] == [
        "same-name",
        "same-name-same-brand",
        "same-name-same-brand-kf-03",
    ]
    assert any("adding brand" in message for message in reports)
    assert any("adding SKU" in message for message in reports)


def test_product_id_is_deterministic_and_field_mapping_is_exact() -> None:
    export = parse_export_text(_export_source())
    first = map_products(export.products, NOW)[0]
    second = map_products(export.products, NOW)[0]
    expected_id = "prod_" + hashlib.sha1(
        b"KF-01",
        usedforsecurity=False,
    ).hexdigest()[:10]

    assert first.item == second.item
    assert first.item["productId"] == expected_id
    assert first.item == {
        "productId": expected_id,
        "sku": "KF-01",
        "slug": "amul-unsalted-butter",
        "name": "Amul Unsalted Butter",
        "brand": "Amul",
        "category": "Dairy",
        "businessType": ["Bakery", "Cafe"],
        "quantities": ["100g", "500g"],
        "description": "Butter for baking.",
        "isTrending": True,
        "sortRank": 10,
        "status": "PUBLISHED",
        "version": 1,
        "createdAt": "2026-10-07T06:20:00Z",
        "updatedAt": "2026-10-07T06:20:00Z",
        "createdBy": "seed",
        "updatedBy": "seed",
    }
    assert isinstance(first.item["businessType"], list)
    assert isinstance(first.item["quantities"], list)
    assert isinstance(first.item["sortRank"], int)
    _assert_no_floats(first.item)


def _assert_no_floats(value: Any) -> None:
    if isinstance(value, float):
        raise AssertionError("float was found in mapped product data")
    if isinstance(value, dict):
        for nested in value.values():
            _assert_no_floats(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_floats(nested)


def test_site_config_default_offer_and_exact_public_shape(tmp_path: Path) -> None:
    config = build_site_config(
        ["Dairy", "Baking Essentials"],
        "917842331013",
        "+91 78423 31013",
        offer_path=tmp_path / "missing-site-offer.json",
    )

    assert config == {
        "configKey": "site",
        "offerBanner": {"enabled": False, "text": "", "link": "/catalogue"},
        "categories": [
            {
                "id": "dairy",
                "name": "Dairy",
                "slug": "dairy",
                "sortOrder": 10,
                "isActive": True,
            },
            {
                "id": "baking-essentials",
                "name": "Baking Essentials",
                "slug": "baking-essentials",
                "sortOrder": 20,
                "isActive": True,
            },
        ],
        "whatsapp": {
            "number": "917842331013",
            "display": "+91 78423 31013",
            "messageTemplate": (
                "Hi Kedar Foods! I am interested in bulk rates for "
                "{name}{pack} (SKU: {sku})?"
            ),
            "generalMessage": (
                "Hi Kedar Foods! I'd like to enquire about bulk wholesale rates."
            ),
        },
    }
    _assert_no_floats(config)


def test_site_config_reads_optional_offer_file(tmp_path: Path) -> None:
    offer_path = tmp_path / "site-offer.json"
    offer_path.write_text(
        json.dumps({"enabled": True, "text": "Special", "link": "/offers"}),
        encoding="utf-8",
    )

    config = build_site_config(
        [],
        "number",
        "display",
        offer_path=offer_path,
    )

    assert config["offerBanner"] == {
        "enabled": True,
        "text": "Special",
        "link": "/offers",
    }


class ConditionalFailure(Exception):
    response = {
        "Error": {
            "Code": "ConditionalCheckFailedException",
            "Message": "Item already exists",
        }
    }


class FakeDynamoClient:
    def __init__(self, should_fail: bool) -> None:
        self.should_fail = should_fail
        self.requests: list[dict[str, Any]] = []

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(kwargs)
        if self.should_fail and "ConditionExpression" in kwargs:
            raise ConditionalFailure("already exists")
        return {}


class FakeProductsTable:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = pages
        self.requests: list[dict[str, Any]] = []

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(kwargs)
        return self.pages[len(self.requests) - 1]


class FakeS3Client:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(kwargs)
        return {}


def test_conditional_write_skips_existing_item_without_overwrite() -> None:
    client = FakeDynamoClient(should_fail=True)

    result = conditional_put(
        client,
        {"productId": "prod_1"},
        "productId",
        overwrite=False,
    )

    assert result == "skipped"
    assert client.requests[0]["ConditionExpression"] == "attribute_not_exists(#pk)"
    assert client.requests[0]["ExpressionAttributeNames"] == {"#pk": "productId"}


def test_overwrite_put_has_no_conditional_expression() -> None:
    client = FakeDynamoClient(should_fail=True)

    result = conditional_put(
        client,
        {"productId": "prod_1"},
        "productId",
        overwrite=True,
    )

    assert result == "created"
    assert "ConditionExpression" not in client.requests[0]
    assert "ExpressionAttributeNames" not in client.requests[0]


def test_index_rebuild_scans_all_pages_and_uploads_public_json() -> None:
    table = FakeProductsTable(
        [
            {
                "Items": [_source_product_as_item("prod_1", "first")],
                "LastEvaluatedKey": {"productId": "prod_1"},
            },
            {
                "Items": [
                    _source_product_as_item("prod_2", "second", status="DRAFT"),
                    _source_product_as_item("prod_3", "third"),
                ]
            },
        ]
    )
    s3 = FakeS3Client()

    index = rebuild_and_upload_index(
        table,
        s3,
        "products",
        "data-bucket",
        NOW,
    )

    assert [item["id"] for item in index["items"]] == ["prod_1", "prod_3"]
    assert table.requests == [
        {},
        {"ExclusiveStartKey": {"productId": "prod_1"}},
    ]
    request = s3.requests[0]
    assert request["Bucket"] == "data-bucket"
    assert request["Key"] == "data/catalog-index.json"
    assert request["ContentType"] == "application/json"
    assert request["CacheControl"] == "public, max-age=60"
    assert json.loads(request["Body"]) == index


def _source_product_as_item(
    product_id: str,
    slug: str,
    *,
    status: str = "PUBLISHED",
) -> dict[str, Any]:
    return {
        "productId": product_id,
        "sku": product_id,
        "slug": slug,
        "name": slug.title(),
        "brand": "Brand",
        "category": "Category",
        "businessType": ["Cafe"],
        "quantities": ["1 kg"],
        "isTrending": False,
        "sortRank": 10,
        "status": status,
    }


@pytest.mark.parametrize(
    ("size", "expected_widths"),
    [
        ((2000, 1000), (480, 1200)),
        ((300, 200), (300, 300)),
    ],
)
def test_image_variants_resize_without_upscaling(
    size: tuple[int, int],
    expected_widths: tuple[int, int],
) -> None:
    source = Image.new("RGB", size, color="red")

    variants = create_image_variants(source)

    assert variants["card"].width == expected_widths[0]
    assert variants["main"].width == expected_widths[1]
    assert variants["card"].height == round(size[1] * expected_widths[0] / size[0])
    assert variants["main"].height == round(size[1] * expected_widths[1] / size[0])
    assert variants["card"].data.startswith(b"RIFF")
    assert variants["card"].data[8:12] == b"WEBP"
