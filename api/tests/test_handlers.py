"""Unit tests for the public read handlers."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from importlib import reload
from typing import Any, cast

import pytest

from api.handlers import dynamodb as dynamodb_module
from api.handlers import get_product, get_site_config


class FakeDynamoResource:
    def __init__(self, table: Any) -> None:
        self.table = table
        self.table_names: list[str] = []

    def Table(self, table_name: str) -> Any:
        self.table_names.append(table_name)
        return self.table() if callable(self.table) else self.table


class FakeBoto3:
    def __init__(self, resource: FakeDynamoResource) -> None:
        self.dynamo_resource = resource
        self.resource_services: list[str] = []

    def resource(self, service_name: str) -> FakeDynamoResource:
        self.resource_services.append(service_name)
        return self.dynamo_resource


class FakeProductsTable:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.query_arguments: dict[str, Any] | None = None

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.query_arguments = kwargs
        return {"Items": self.items}


class FakeSiteConfigTable:
    def __init__(self, item: dict[str, Any] | None) -> None:
        self.item = item
        self.get_item_arguments: dict[str, Any] | None = None

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        self.get_item_arguments = kwargs
        return {"Item": self.item} if self.item is not None else {}


@pytest.fixture(autouse=True)
def fake_slug_key_condition(monkeypatch: pytest.MonkeyPatch) -> None:
    dynamodb_module.clear_table_cache()
    monkeypatch.setattr(dynamodb_module, "_TABLE_CACHE", {})
    monkeypatch.setattr(
        get_product,
        "slug_key_condition",
        lambda slug: {"slug": slug},
    )


def _body(response: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(response["body"]))


def _published_product(**extra: Any) -> dict[str, Any]:
    return {
        "productId": "prod_101",
        "slug": "sample-product",
        "status": "PUBLISHED",
        "sku": "KF-101",
        "name": "Sample product",
        "brand": "Kedar",
        "category": "snacks",
        "businessType": ["Cafe"],
        "quantities": ["500 g"],
        "description": "Public description",
        "image": {
            "card": "media/products/prod_101/card-v1.webp",
            "main": "media/products/prod_101/main-v1.webp",
            "internal": "incoming/private.png",
        },
        "updatedAt": "2026-10-06T00:00:00Z",
        "version": 3,
        "createdBy": "admin@example.com",
        "updatedBy": "admin@example.com",
        **extra,
    }


@pytest.mark.parametrize(
    ("handler_function", "table_env_name", "fake_table", "event"),
    [
        (
            get_product.handler,
            "PRODUCTS_TABLE_NAME",
            FakeProductsTable([_published_product()]),
            {"pathParameters": {"slug": "sample-product"}},
        ),
        (
            get_site_config.handler,
            "SITE_CONFIG_TABLE_NAME",
            FakeSiteConfigTable({"configKey": "site"}),
            {},
        ),
    ],
)
def test_handler_caches_table_object_between_calls(
    monkeypatch: pytest.MonkeyPatch,
    handler_function: Callable[[dict[str, Any], object], dict[str, Any]],
    table_env_name: str,
    fake_table: FakeProductsTable | FakeSiteConfigTable,
    event: dict[str, Any],
) -> None:
    monkeypatch.setenv(table_env_name, f"test-{table_env_name.lower()}")
    resource = FakeDynamoResource(fake_table)
    boto3 = FakeBoto3(resource)
    monkeypatch.setattr(
        dynamodb_module,
        "import_module",
        lambda module_name: boto3 if module_name == "boto3" else None,
    )

    first_response = handler_function(event, None)
    second_response = handler_function(event, None)

    assert first_response["statusCode"] == 200
    assert second_response["statusCode"] == 200
    assert boto3.resource_services == ["dynamodb"]
    assert resource.table_names == [f"test-{table_env_name.lower()}"]


def test_clear_table_cache_forces_table_recreation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCTS_TABLE_NAME", "test-products")
    resource = FakeDynamoResource(lambda: FakeProductsTable([]))
    boto3 = FakeBoto3(resource)
    monkeypatch.setattr(
        dynamodb_module,
        "import_module",
        lambda module_name: boto3 if module_name == "boto3" else None,
    )

    first_table = dynamodb_module.create_products_table()
    assert dynamodb_module.create_products_table() is first_table
    dynamodb_module.clear_table_cache()
    second_table = dynamodb_module.create_products_table()

    assert second_table is not first_table
    assert boto3.resource_services == ["dynamodb", "dynamodb"]
    assert resource.table_names == ["test-products", "test-products"]


def test_importing_handlers_without_lambda_environment_is_lazy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    imported_modules: list[str] = []

    def track_import(module_name: str) -> None:
        imported_modules.append(module_name)

    monkeypatch.setattr(dynamodb_module, "import_module", track_import)
    monkeypatch.setattr(get_product, "import_module", track_import)

    reload(get_product)
    reload(get_site_config)

    assert imported_modules == []


def test_product_handler_returns_only_public_allowlist() -> None:
    table = FakeProductsTable([_published_product()])
    response = get_product.handler(
        {"pathParameters": {"slug": "sample-product"}},
        None,
        table=table,
    )

    assert response["statusCode"] == 200
    assert response["headers"] == {
        "Content-Type": "application/json",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "public, max-age=0, must-revalidate",
    }
    body = _body(response)
    assert body == {
        "id": "prod_101",
        "slug": "sample-product",
        "sku": "KF-101",
        "name": "Sample product",
        "brand": "Kedar",
        "category": "snacks",
        "businessType": ["Cafe"],
        "quantities": ["500 g"],
        "description": "Public description",
        "image": {
            "card": "media/products/prod_101/card-v1.webp",
            "main": "media/products/prod_101/main-v1.webp",
        },
        "updatedAt": "2026-10-06T00:00:00Z",
    }


def test_product_handler_lowercases_slug_and_uses_plain_index_query() -> None:
    table = FakeProductsTable([_published_product()])
    response = get_product.handler(
        {"pathParameters": {"slug": "SAMPLE-PRODUCT"}},
        None,
        table=table,
    )

    assert response["statusCode"] == 200
    assert table.query_arguments is not None
    assert table.query_arguments == {
        "IndexName": "slug-index",
        "KeyConditionExpression": {"slug": "sample-product"},
    }


def test_published_product_wins_when_draft_has_same_slug() -> None:
    table = FakeProductsTable(
        [
            _published_product(productId="draft_101", status="DRAFT"),
            _published_product(productId="prod_101", status="PUBLISHED"),
        ]
    )
    response = get_product.handler(
        {"pathParameters": {"slug": "sample-product"}},
        None,
        table=table,
    )

    assert response["statusCode"] == 200
    assert _body(response)["id"] == "prod_101"


@pytest.mark.parametrize(
    "slug",
    [
        "bad.slug",
        "two--hyphens",
        "-leading",
        "trailing-",
        "",
    ],
)
def test_invalid_product_slug_returns_generic_not_found(slug: str) -> None:
    table = FakeProductsTable([])
    response = get_product.handler(
        {"pathParameters": {"slug": slug}},
        None,
        table=table,
    )

    assert response["statusCode"] == 404
    assert _body(response) == {"error": "not_found"}
    assert response["headers"]["Cache-Control"] == "no-store"
    assert table.query_arguments is None


@pytest.mark.parametrize(
    "item",
    [
        None,
        _published_product(status="DRAFT"),
        _published_product(status="UNPUBLISHED"),
        _published_product(status="ARCHIVED"),
    ],
)
def test_missing_or_nonpublished_product_returns_same_not_found(item: Any) -> None:
    table = FakeProductsTable([] if item is None else [item])
    response = get_product.handler(
        {"pathParameters": {"slug": "sample-product"}},
        None,
        table=table,
    )

    assert response["statusCode"] == 404
    assert _body(response) == {"error": "not_found"}
    assert response["headers"]["Cache-Control"] == "no-store"


def test_product_decimal_values_are_json_numbers_and_missing_image_is_omitted() -> None:
    item = _published_product(
        image=None,
        quantities=[Decimal("0.5"), Decimal("1")],
    )
    response = get_product.handler(
        {"pathParameters": {"slug": "sample-product"}},
        None,
        table=FakeProductsTable([item]),
    )

    assert response["statusCode"] == 200
    body = _body(response)
    assert body["quantities"] == [0.5, 1]
    assert "image" not in body


def test_site_config_returns_only_allowlisted_shape_and_converts_decimal() -> None:
    table = FakeSiteConfigTable(
        {
            "configKey": "site",
            "offerBanner": {
                "enabled": True,
                "text": "Offer",
                "link": "/offers",
                "adminNote": "private",
            },
            "categories": [
                {
                    "id": "cat_1",
                    "name": "Snacks",
                    "slug": "snacks",
                    "sortOrder": Decimal("12"),
                    "isActive": True,
                    "internal": "private",
                }
            ],
            "whatsapp": {
                "number": "+911234567890",
                "display": "+91 12345 67890",
                "messageTemplate": "Hi {name}{pack} ({sku})",
                "generalMessage": "Hello",
                "secret": "private",
                "extraRawField": "must-not-leak",
            },
            "privateField": "private",
        }
    )
    response = get_site_config.handler({}, None, table=table)

    assert response["statusCode"] == 200
    assert response["headers"] == {
        "Content-Type": "application/json",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "public, max-age=0, must-revalidate",
    }
    assert _body(response) == {
        "offerBanner": {
            "enabled": True,
            "text": "Offer",
            "link": "/offers",
        },
        "categories": [
            {
                "id": "cat_1",
                "name": "Snacks",
                "slug": "snacks",
                "sortOrder": 12,
                "isActive": True,
            }
        ],
        "whatsapp": {
            "number": "+911234567890",
            "display": "+91 12345 67890",
            "messageTemplate": "Hi {name}{pack} ({sku})",
            "generalMessage": "Hello",
        },
    }
    assert set(_body(response)["whatsapp"]) == {
        "number",
        "display",
        "messageTemplate",
        "generalMessage",
    }
    assert table.get_item_arguments == {"Key": {"configKey": "site"}}


def test_missing_site_config_returns_generic_not_found() -> None:
    response = get_site_config.handler({}, None, table=FakeSiteConfigTable(None))

    assert response["statusCode"] == 404
    assert _body(response) == {"error": "not_found"}
    assert response["headers"]["Cache-Control"] == "no-store"


def test_site_config_omits_missing_optional_fields_and_filters_invalid_types() -> None:
    response = get_site_config.handler(
        {},
        None,
        table=FakeSiteConfigTable(
            {
                "configKey": "site",
                "offerBanner": {"enabled": "true", "text": None, "link": "/"},
                "categories": [
                    {"id": "cat_2", "sortOrder": Decimal("1.5")},
                    "not-a-category",
                ],
                "whatsapp": {
                    "number": 123,
                    "display": "Display",
                    "messageTemplate": "Template",
                    "generalMessage": "General",
                    "secret": "private",
                },
                "unexpected": "private",
            }
        ),
    )

    assert response["statusCode"] == 200
    assert _body(response) == {
        "offerBanner": {"link": "/"},
        "categories": [{"id": "cat_2", "sortOrder": 1.5}],
        "whatsapp": {
            "display": "Display",
            "messageTemplate": "Template",
            "generalMessage": "General",
        },
    }
