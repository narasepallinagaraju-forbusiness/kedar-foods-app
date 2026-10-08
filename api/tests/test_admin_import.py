"""Bulk import: POST /admin/products/import."""

from __future__ import annotations

from typing import Any

from api.handlers.product_validation import product_id_from_sku

from .test_admin_products import Env, _env, _json, _payload, _stored  # noqa: F401

ROUTE = "POST /admin/products/import"


def _rows(*skus: str, **overrides: Any) -> list[dict[str, Any]]:
    return [
        _payload(sku=sku, name=f"Product {sku}", **overrides) for sku in skus
    ]


def test_import_creates_live_products_by_default_and_rebuilds_once() -> None:
    env = Env()

    response = env.call(ROUTE, body={"rows": _rows("KF-30", "KF-31", "KF-32")})

    body = _json(response)
    assert response["statusCode"] == 200
    assert (body["created"], body["skipped"], body["failed"]) == (3, 0, 0)
    assert body["indexRebuilt"] is True
    assert len(env.s3.calls) == 1
    assert len(env.index_ids()) == 3
    stored = env.products.items[product_id_from_sku("KF-30")]
    assert stored["status"] == "PUBLISHED"
    assert stored["version"] == 1


def test_import_honours_archived_and_skips_the_index_when_nothing_is_live() -> None:
    env = Env()

    response = env.call(ROUTE, body={"rows": _rows("KF-30", status="ARCHIVED")})

    body = _json(response)
    assert body["created"] == 1
    assert "indexRebuilt" not in body
    assert env.s3.calls == []
    assert env.products.items[product_id_from_sku("KF-30")]["status"] == "ARCHIVED"


def test_import_skips_existing_skus_without_overwriting() -> None:
    env = Env([_stored("KF-30", name="Original")])

    body = _json(env.call(ROUTE, body={"rows": _rows("KF-30", "KF-31")}))

    assert [r["result"] for r in body["results"]] == ["skipped", "created"]
    assert env.products.items[product_id_from_sku("KF-30")]["name"] == "Original"


def test_import_skips_a_sku_repeated_inside_the_batch() -> None:
    env = Env()

    body = _json(env.call(ROUTE, body={"rows": _rows("KF-30", "KF-30")}))

    assert (body["created"], body["skipped"]) == (1, 1)


def test_import_reports_bad_rows_and_still_creates_good_ones() -> None:
    env = Env()
    rows = [
        _payload(sku="KF-30", category="Nope"),
        _payload(sku="kf 31"),
        "not an object",
        _payload(sku="KF-33", name="Good"),
    ]

    body = _json(env.call(ROUTE, body={"rows": rows}))

    assert [r["result"] for r in body["results"]] == [
        "failed",
        "failed",
        "failed",
        "created",
    ]
    assert body["results"][0]["errors"][0]["field"] == "category"
    assert body["results"][3]["row"] == 3
    assert list(env.products.items) == [product_id_from_sku("KF-33")]


def test_import_slug_collisions_get_distinct_slugs() -> None:
    env = Env()
    rows = [
        _payload(sku="KF-30", name="Cream", brand="Amul"),
        _payload(sku="KF-31", name="Cream", brand="Amul"),
        _payload(sku="KF-32", name="Cream", brand="Amul"),
    ]

    _json(env.call(ROUTE, body={"rows": rows}))

    slugs = {item["slug"] for item in env.products.items.values()}
    assert len(slugs) == 3


def test_import_rejects_bad_batches() -> None:
    env = Env()

    bad_batches: list[dict[str, Any]] = [
        {"rows": []},
        {"rows": _rows(*[f"KF-{n}" for n in range(10, 61)])},
        {"rows": "x"},
        {},
    ]
    for body in bad_batches:
        response = env.call(ROUTE, body=body)
        assert response["statusCode"] == 400
    assert env.products.items == {}


def test_import_index_failure_keeps_the_products_and_reports_it() -> None:
    env = Env()
    env.s3.fail = True

    body = _json(env.call(ROUTE, body={"rows": _rows("KF-30")}))

    assert body["created"] == 1
    assert body["indexRebuilt"] is False
    assert product_id_from_sku("KF-30") in env.products.items
