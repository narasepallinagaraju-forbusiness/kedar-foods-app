"""Tests for the admin picture routes (product slots and offer poster)."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from api.handlers.admin_auth import clear_admin_key_cache
from api.handlers.admin_images import handler
from api.handlers.image_rules import check_webp

from .admin_fakes import (
    SITE_CONFIG,
    FakeProductsTable,
    FakeS3,
    FakeSiteConfigTable,
    FakeSsm,
)

KEY = "k" * 40
PID = "prod_0123456789"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
STAMP = int(NOW.timestamp())


def make_webp(width: int = 480, height: int = 480, size: int = 2000) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    payload = b"\x2f" + bits.to_bytes(4, "little")
    payload += b"\x00" * (size - 12 - len(payload) - 8)
    chunk = b"VP8L" + len(payload).to_bytes(4, "little") + payload
    return b"RIFF" + (len(chunk) + 4).to_bytes(4, "little") + b"WEBP" + chunk


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def product(**extra: Any) -> dict[str, Any]:
    return {
        "productId": PID,
        "slug": "milk",
        "name": "Milk",
        "status": "PUBLISHED",
        "version": 3,
        **extra,
    }


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ADMIN_KEY_PARAMETER", "/test/admin-key")
    monkeypatch.setenv("DATA_BUCKET_NAME", "data-bucket")
    clear_admin_key_cache()
    yield
    clear_admin_key_cache()


def call(
    route: str,
    body: Any = None,
    *,
    table: FakeProductsTable | None = None,
    config: FakeSiteConfigTable | None = None,
    s3: FakeS3 | None = None,
    slot: str = "1",
    key: str | None = KEY,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "routeKey": route,
        "headers": {} if key is None else {"x-admin-key": key},
        "pathParameters": {"id": PID, "slot": slot},
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return handler(
        event,
        None,
        table=table,
        site_config_table=config,
        s3_client=s3 or FakeS3(),
        ssm_client=FakeSsm(),
        now=NOW,
    )


UPLOAD = "PUT /admin/products/{id}/images/{slot}"
REMOVE = "POST /admin/products/{id}/images/{slot}/remove"
POSTER = "PUT /admin/site-config/offer/image"
POSTER_OFF = "POST /admin/site-config/offer/image/remove"


def good_body(version: int = 3) -> dict[str, Any]:
    return {
        "version": version,
        "card": b64(make_webp(480, 480)),
        "main": b64(make_webp(1200, 900)),
    }


def test_routes_require_the_admin_key() -> None:
    table = FakeProductsTable([product()])
    s3 = FakeS3()

    assert call(UPLOAD, good_body(), table=table, s3=s3, key=None)["statusCode"] == 401
    assert call(POSTER, {"poster": "x"}, key=None)["statusCode"] == 401
    assert s3.calls == []


def test_upload_slot_one_stores_versioned_keys_and_saves_them() -> None:
    table = FakeProductsTable([product()])
    s3 = FakeS3()

    response = call(UPLOAD, good_body(), table=table, s3=s3)

    assert response["statusCode"] == 200
    card = f"media/products/{PID}/card-v{STAMP}.webp"
    main = f"media/products/{PID}/main-v{STAMP}.webp"
    stored = table.items[PID]
    assert stored["image"] == {"card": card, "main": main}
    assert stored["gallery"] == []
    assert stored["version"] == 4
    puts = {c["Key"]: c for c in s3.calls if c["Key"] != "data/catalog-index.json"}
    assert set(puts) == {card, main}
    for call_args in puts.values():
        assert call_args["ContentType"] == "image/webp"
        assert "immutable" in call_args["CacheControl"]
        assert call_args["Bucket"] == "data-bucket"
    assert json.loads(response["body"])["indexRebuilt"] is True
    assert any(c["Key"] == "data/catalog-index.json" for c in s3.calls)


def test_archived_product_picture_does_not_rebuild_index() -> None:
    table = FakeProductsTable([product(status="ARCHIVED")])
    s3 = FakeS3()

    assert call(UPLOAD, good_body(), table=table, s3=s3)["statusCode"] == 200
    assert all(c["Key"] != "data/catalog-index.json" for c in s3.calls)


def test_slots_fill_in_order_replace_and_compact_on_remove() -> None:
    table = FakeProductsTable([product()])

    assert call(UPLOAD, good_body(3), table=table, slot="2")["statusCode"] == 400
    assert call(UPLOAD, good_body(3), table=table, slot="1")["statusCode"] == 200
    assert call(UPLOAD, good_body(4), table=table, slot="2")["statusCode"] == 200
    assert call(UPLOAD, good_body(5), table=table, slot="3")["statusCode"] == 200
    stored = table.items[PID]
    assert len(stored["gallery"]) == 2
    first = stored["image"]
    second = stored["gallery"][0]
    third = stored["gallery"][1]
    assert len({first["card"], second["card"], third["card"]}) == 3

    assert call(REMOVE, {"version": 6}, table=table, slot="1")["statusCode"] == 200
    stored = table.items[PID]
    assert stored["image"] == second
    assert stored["gallery"] == [third]

    assert call(REMOVE, {"version": 7}, table=table, slot="3")["statusCode"] == 404
    assert call(REMOVE, {"version": 7}, table=table, slot="2")["statusCode"] == 200
    assert call(REMOVE, {"version": 8}, table=table, slot="1")["statusCode"] == 200
    assert table.items[PID]["image"] == {}
    assert table.items[PID]["gallery"] == []


def test_slot_four_and_bad_ids_are_not_found() -> None:
    table = FakeProductsTable([product()])

    assert call(UPLOAD, good_body(), table=table, slot="4")["statusCode"] == 404
    assert call(UPLOAD, good_body(), table=table, slot="0")["statusCode"] == 404
    missing = FakeProductsTable([])
    assert call(UPLOAD, good_body(), table=missing)["statusCode"] == 404


def test_stale_version_conflicts_and_nothing_is_written_to_the_table() -> None:
    table = FakeProductsTable([product()])
    s3 = FakeS3()

    response = call(UPLOAD, good_body(2), table=table, s3=s3)

    assert response["statusCode"] == 409
    assert json.loads(response["body"])["currentVersion"] == 3
    assert "image" not in table.items[PID]
    assert s3.calls == []


@pytest.mark.parametrize(
    ("card", "main", "field"),
    [
        (b64(b"not an image" * 200), b64(make_webp()), "card"),
        (b64(make_webp(size=500)), b64(make_webp()), "card"),
        (b64(make_webp(900, 900)), b64(make_webp()), "card"),
        (b64(make_webp()), b64(make_webp(1700, 100)), "main"),
        (b64(make_webp()), b64(make_webp(size=700 * 1024)), "main"),
        ("***", b64(make_webp()), "card"),
        ("", b64(make_webp()), "card"),
    ],
    ids=[
        "not-webp",
        "too-small",
        "card-too-wide",
        "main-too-wide",
        "too-big-file",
        "bad-base64",
        "empty",
    ],
)
def test_bad_pictures_are_rejected_before_anything_is_stored(
    card: str, main: str, field: str
) -> None:
    table = FakeProductsTable([product()])
    s3 = FakeS3()

    response = call(
        UPLOAD, {"version": 3, "card": card, "main": main}, table=table, s3=s3
    )

    assert response["statusCode"] == 400
    details = json.loads(response["body"])["details"]
    assert details[0]["field"] == field
    assert s3.calls == []
    assert "image" not in table.items[PID]


def test_truncated_webp_and_missing_version_are_rejected() -> None:
    table = FakeProductsTable([product()])
    truncated = make_webp()[:-10]
    body = {"version": 3, "card": b64(truncated), "main": b64(make_webp())}

    assert call(UPLOAD, body, table=table)["statusCode"] == 400
    no_version = good_body()
    del no_version["version"]
    assert call(UPLOAD, no_version, table=table)["statusCode"] == 400
    assert call(REMOVE, {}, table=table)["statusCode"] == 400


def test_oversized_request_is_refused() -> None:
    table = FakeProductsTable([product()])
    huge = {"version": 3, "card": "A" * (3 * 1024 * 1024), "main": "A"}

    assert call(UPLOAD, huge, table=table)["statusCode"] == 413


def test_s3_failure_leaves_the_product_unchanged() -> None:
    table = FakeProductsTable([product()])

    response = call(UPLOAD, good_body(), table=table, s3=FakeS3(fail=True))

    assert response["statusCode"] == 500
    assert "image" not in table.items[PID]


def test_poster_upload_keeps_other_offer_fields_and_remove_clears_it() -> None:
    config = FakeSiteConfigTable(SITE_CONFIG)
    s3 = FakeS3()

    response = call(POSTER, {"poster": b64(make_webp(1200, 400))}, config=config, s3=s3)

    assert response["statusCode"] == 200
    key = f"media/offer/poster-v{STAMP}.webp"
    assert config.item is not None
    assert config.item["offerBanner"] == {
        "enabled": False,
        "text": "",
        "link": "",
        "image": key,
    }
    assert [c["Key"] for c in s3.calls] == [key]

    assert call(POSTER_OFF, config=config)["statusCode"] == 200
    assert "image" not in config.item["offerBanner"]


def test_poster_rejects_bad_files_and_missing_config() -> None:
    config = FakeSiteConfigTable(SITE_CONFIG)
    s3 = FakeS3()

    assert call(POSTER, {"poster": "***"}, config=config, s3=s3)["statusCode"] == 400
    assert call(POSTER, {}, config=config, s3=s3)["statusCode"] == 400
    big = b64(make_webp(2000, 100))
    assert call(POSTER, {"poster": big}, config=config, s3=s3)["statusCode"] == 400
    assert s3.calls == []
    empty = FakeSiteConfigTable(None)
    ok = b64(make_webp())
    assert call(POSTER, {"poster": ok}, config=empty, s3=s3)["statusCode"] == 404
    assert s3.calls == []


def test_check_webp_accepts_lossy_and_extended_layouts() -> None:
    vp8 = bytearray(make_webp(size=2000))
    vp8[12:16] = b"VP8 "
    vp8[26:28] = (640).to_bytes(2, "little")
    vp8[28:30] = (480).to_bytes(2, "little")
    assert check_webp("card", bytes(vp8), 800) == bytes(vp8)

    vp8x = bytearray(make_webp(size=2000))
    vp8x[12:16] = b"VP8X"
    vp8x[24:27] = (799).to_bytes(3, "little")
    vp8x[27:30] = (99).to_bytes(3, "little")
    assert check_webp("card", bytes(vp8x), 800) == bytes(vp8x)
    vp8x[24:27] = (800).to_bytes(3, "little")
    with pytest.raises(Exception, match="at most 800"):
        check_webp("card", bytes(vp8x), 800)
