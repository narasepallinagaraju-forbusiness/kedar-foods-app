"""Tests for admin product routes using in-memory fakes."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from api.handlers.admin_auth import clear_admin_key_cache
from api.handlers.admin_products import handler
from api.handlers.product_validation import product_id_from_sku

from .admin_fakes import (
    SITE_CONFIG,
    FakeProductsTable,
    FakeS3,
    FakeSiteConfigTable,
    FakeSsm,
)

KEY = "k" * 40
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ADMIN_KEY_PARAMETER", "/test/admin-key")
    monkeypatch.setenv("DATA_BUCKET_NAME", "data-bucket")
    clear_admin_key_cache()
    yield
    clear_admin_key_cache()


def _stored(sku: str = "KF-01", **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "productId": product_id_from_sku(sku),
        "sku": sku,
        "slug": "amul-butter",
        "name": "Amul Butter",
        "brand": "Amul",
        "category": "Dairy",
        "businessType": ["Cafe"],
        "quantities": ["500g"],
        "description": "",
        "isTrending": False,
        "sortRank": 10,
        "status": "PUBLISHED",
        "version": 1,
        "image": {"card": "media/products/x/card-v1.webp"},
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "createdBy": "seed",
        "updatedBy": "seed",
    }
    item.update(overrides)
    return item


def _payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "sku": "KF-20",
        "name": "Fresh Cream",
        "brand": "Amul",
        "category": "Dairy",
        "businessType": ["Bakery"],
        "quantities": ["1 L"],
    }
    body.update(overrides)
    return body


class Env:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.products = FakeProductsTable(items)
        self.config = FakeSiteConfigTable(SITE_CONFIG)
        self.s3 = FakeS3()

    def call(
        self,
        route: str,
        *,
        body: Any = None,
        product_id: str | None = None,
        key: str | None = KEY,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "routeKey": route,
            "headers": {} if key is None else {"x-admin-key": key},
            "pathParameters": {} if product_id is None else {"id": product_id},
        }
        if body is not None:
            event["body"] = json.dumps(body)
        return handler(
            event,
            None,
            table=self.products,
            site_config_table=self.config,
            s3_client=self.s3,
            ssm_client=FakeSsm(),
            now=NOW,
        )

    def index_ids(self) -> list[str]:
        return [item["id"] for item in json.loads(self.s3.calls[-1]["Body"])["items"]]


def _json(response: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(response["body"])
    return result


@pytest.mark.parametrize(
    "route",
    [
        "GET /admin/products",
        "POST /admin/products",
        "GET /admin/products/{id}",
        "PUT /admin/products/{id}",
        "POST /admin/products/{id}/archive",
        "POST /admin/products/{id}/restore",
        "POST /admin/catalog-index/rebuild",
    ],
)
def test_every_route_requires_the_admin_key(route: str) -> None:
    env = Env([_stored()])

    for key in (None, "wrong"):
        response = env.call(
            route, key=key, product_id=product_id_from_sku("KF-01"), body={}
        )
        assert response["statusCode"] == 401

    assert env.s3.calls == []
    assert env.products.items[product_id_from_sku("KF-01")]["version"] == 1


def test_list_returns_all_statuses_sorted() -> None:
    env = Env(
        [
            _stored("KF-02", name="B", sortRank=20, status="ARCHIVED"),
            _stored("KF-01", name="A", sortRank=10),
        ]
    )

    response = env.call("GET /admin/products")

    assert response["statusCode"] == 200
    assert response["headers"]["Cache-Control"] == "no-store"
    assert [p["sku"] for p in _json(response)["products"]] == ["KF-01", "KF-02"]


def test_list_follows_scan_pagination() -> None:
    env = Env([_stored(f"KF-{n:02d}") for n in range(1, 6)])
    env.products.page_size = 2

    assert len(_json(env.call("GET /admin/products"))["products"]) == 5


def test_get_product_and_not_found() -> None:
    env = Env([_stored()])
    product_id = product_id_from_sku("KF-01")

    assert env.call("GET /admin/products/{id}", product_id=product_id)[
        "statusCode"
    ] == 200
    assert env.call("GET /admin/products/{id}", product_id="prod_0000000000")[
        "statusCode"
    ] == 404
    assert env.call("GET /admin/products/{id}", product_id="../etc")[
        "statusCode"
    ] == 404


def test_create_hidden_by_default_does_not_touch_the_index() -> None:
    env = Env()

    response = env.call("POST /admin/products", body=_payload())

    assert response["statusCode"] == 201
    product = _json(response)["product"]
    assert product["status"] == "ARCHIVED"
    assert product["version"] == 1
    assert product["slug"] == "fresh-cream"
    assert product["createdBy"] == "admin-key"
    assert "image" not in product
    assert product["productId"] == product_id_from_sku("KF-20")
    assert env.s3.calls == []


def test_create_published_rebuilds_index_with_headers() -> None:
    env = Env([_stored()])

    response = env.call("POST /admin/products", body=_payload(status="PUBLISHED"))

    assert _json(response)["indexRebuilt"] is True
    call = env.s3.calls[-1]
    assert call["Bucket"] == "data-bucket"
    assert call["Key"] == "data/catalog-index.json"
    assert call["ContentType"] == "application/json"
    assert call["CacheControl"] == "public, max-age=0, must-revalidate"
    assert len(env.index_ids()) == 2


def test_create_duplicate_sku_returns_409_and_keeps_original() -> None:
    env = Env([_stored("KF-20", name="Original")])

    response = env.call("POST /admin/products", body=_payload())

    assert response["statusCode"] == 409
    assert env.products.items[product_id_from_sku("KF-20")]["name"] == "Original"


def test_create_slug_collision_appends_brand() -> None:
    env = Env([_stored(slug="fresh-cream")])

    product = _json(env.call("POST /admin/products", body=_payload()))["product"]

    assert product["slug"] == "fresh-cream-amul"


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": "Retired"},
        {"category": "Unknown"},
        {"image": {"card": "media/x.webp"}},
        {"productId": "prod_x"},
        {"status": "DRAFT"},
        {"name": ""},
    ],
)
def test_create_rejects_invalid_input_without_writing(
    overrides: dict[str, Any],
) -> None:
    env = Env()

    response = env.call("POST /admin/products", body=_payload(**overrides))

    assert response["statusCode"] == 400
    assert _json(response)["error"] == "validation_failed"
    assert env.products.items == {}


def test_create_returns_503_when_categories_unreadable() -> None:
    env = Env()
    env.config.fail_reads = True

    response = env.call("POST /admin/products", body=_payload())

    assert response["statusCode"] == 503
    assert env.products.items == {}


def test_create_rejects_bad_json_and_missing_body() -> None:
    env = Env()
    event = {
        "routeKey": "POST /admin/products",
        "headers": {"x-admin-key": KEY},
        "body": "{bad",
    }
    response = handler(
        event,
        None,
        table=env.products,
        site_config_table=env.config,
        ssm_client=FakeSsm(),
    )
    assert response["statusCode"] == 400
    assert env.call("POST /admin/products")["statusCode"] == 400


def test_update_changes_fields_bumps_version_keeps_image_and_slug() -> None:
    env = Env([_stored()])
    product_id = product_id_from_sku("KF-01")
    body = _payload(version=1, name="Amul Butter Salted")
    del body["sku"]

    response = env.call("PUT /admin/products/{id}", body=body, product_id=product_id)

    assert response["statusCode"] == 200
    stored = env.products.items[product_id]
    assert stored["name"] == "Amul Butter Salted"
    assert stored["version"] == 2
    assert stored["slug"] == "amul-butter"
    assert stored["image"] == {"card": "media/products/x/card-v1.webp"}
    assert stored["createdBy"] == "seed"
    assert stored["updatedBy"] == "admin-key"
    assert _json(response)["indexRebuilt"] is True


def test_update_of_hidden_product_does_not_rebuild_index() -> None:
    env = Env([_stored(status="ARCHIVED")])
    body = _payload(version=1)
    del body["sku"]

    response = env.call(
        "PUT /admin/products/{id}", body=body, product_id=product_id_from_sku("KF-01")
    )

    assert response["statusCode"] == 200
    assert "indexRebuilt" not in _json(response)
    assert env.s3.calls == []


def test_update_with_stale_version_returns_409_and_does_not_write() -> None:
    env = Env([_stored(version=3)])
    product_id = product_id_from_sku("KF-01")
    body = _payload(version=2, name="Changed")
    del body["sku"]

    response = env.call("PUT /admin/products/{id}", body=body, product_id=product_id)

    assert response["statusCode"] == 409
    assert _json(response)["currentVersion"] == 3
    assert env.products.items[product_id]["name"] == "Amul Butter"


def test_update_unknown_product_404_and_immutable_fields_rejected() -> None:
    env = Env([_stored()])
    body = _payload(version=1)

    unknown = env.call(
        "PUT /admin/products/{id}", body={**body, "sku": None}, product_id="prod_1"
    )
    assert unknown["statusCode"] == 404

    del body["sku"]
    missing = env.call(
        "PUT /admin/products/{id}", body=body, product_id="prod_0000000000"
    )
    assert missing["statusCode"] == 404

    for extra in ({"sku": "KF-99"}, {"slug": "x"}, {"status": "ARCHIVED"}):
        response = env.call(
            "PUT /admin/products/{id}",
            body={**body, **extra},
            product_id=product_id_from_sku("KF-01"),
        )
        assert response["statusCode"] == 400


def test_archive_hides_product_and_restore_shows_it() -> None:
    env = Env([_stored("KF-01"), _stored("KF-02", slug="other", name="Other")])
    product_id = product_id_from_sku("KF-01")

    archived = env.call("POST /admin/products/{id}/archive", product_id=product_id)

    assert archived["statusCode"] == 200
    assert env.products.items[product_id]["status"] == "ARCHIVED"
    assert env.products.items[product_id]["version"] == 2
    assert env.index_ids() == [product_id_from_sku("KF-02")]

    restored = env.call("POST /admin/products/{id}/restore", product_id=product_id)

    assert restored["statusCode"] == 200
    assert env.products.items[product_id]["status"] == "PUBLISHED"
    assert env.products.items[product_id]["version"] == 3
    assert product_id in env.index_ids()


def test_archive_and_restore_unknown_product_404() -> None:
    env = Env()

    for action in ("archive", "restore"):
        response = env.call(
            f"POST /admin/products/{{id}}/{action}", product_id="prod_0000000000"
        )
        assert response["statusCode"] == 404


def test_restore_incomplete_product_is_rejected() -> None:
    env = Env([_stored(status="ARCHIVED", category="")])
    product_id = product_id_from_sku("KF-01")

    response = env.call("POST /admin/products/{id}/restore", product_id=product_id)

    assert response["statusCode"] == 400
    assert _json(response)["error"] == "incomplete_product"
    assert env.products.items[product_id]["status"] == "ARCHIVED"


def test_index_failure_keeps_the_write_and_reports_it() -> None:
    env = Env([_stored()])
    env.s3.fail = True
    product_id = product_id_from_sku("KF-01")

    response = env.call("POST /admin/products/{id}/archive", product_id=product_id)

    assert response["statusCode"] == 200
    assert _json(response)["indexRebuilt"] is False
    assert "Rebuild" in _json(response)["message"]
    assert env.products.items[product_id]["status"] == "ARCHIVED"


def test_manual_rebuild_success_and_failure() -> None:
    env = Env([_stored()])

    assert env.call("POST /admin/catalog-index/rebuild")["statusCode"] == 200
    assert len(env.s3.calls) == 1

    env.s3.fail = True
    assert env.call("POST /admin/catalog-index/rebuild")["statusCode"] == 500


def test_unknown_route_and_unexpected_error_do_not_leak_details() -> None:
    env = Env()
    assert env.call("DELETE /admin/products/{id}")["statusCode"] == 404

    class Broken(FakeProductsTable):
        def scan(self, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("secret internal detail")

    event = {"routeKey": "GET /admin/products", "headers": {"x-admin-key": KEY}}
    response = handler(
        event,
        None,
        table=Broken(),
        site_config_table=env.config,
        ssm_client=FakeSsm(),
    )

    assert response["statusCode"] == 500
    assert "secret" not in response["body"]
