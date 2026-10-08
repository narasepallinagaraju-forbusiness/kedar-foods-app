"""Admin picture routes: product pictures (up to 3 slots) and the offer poster.

The browser sends already-resized WebP files as base64 JSON. The server checks the
real bytes, stores them under a new versioned key (never overwriting, so the
one-year cache can never serve a stale picture) and then saves the key.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from .admin_auth import BodyError, authorize, parse_json_body
from .admin_products import _conditional_update, _iso, _no_store
from .common import error_response
from .dynamodb import (
    AdminProductsTable,
    AdminSiteConfigTable,
    ParameterReader,
    S3Writer,
    create_admin_products_table,
    create_admin_site_config_table,
    create_s3_client,
)
from .image_rules import (
    CARD_MAX_SIDE,
    MAIN_MAX_SIDE,
    MAX_PICTURES,
    POSTER_MAX_SIDE,
    ImageError,
    check_webp,
    decode_base64,
)

LOGGER = logging.getLogger(__name__)
ACTOR = "admin-key"
MAX_IMAGE_BODY_BYTES = 2 * 1024 * 1024
PRODUCT_ID_PATTERN = re.compile(r"^prod_[0-9a-f]{10}$")
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


def _picture_list(product: Mapping[str, Any]) -> list[dict[str, str]]:
    """Slot 1 is ``image``; slots 2 and 3 are ``gallery``. Incomplete entries drop."""
    entries: list[object] = [product.get("image")]
    gallery = product.get("gallery")
    if isinstance(gallery, list):
        entries.extend(gallery)
    pictures: list[dict[str, str]] = []
    for entry in entries[:MAX_PICTURES]:
        if (
            isinstance(entry, Mapping)
            and isinstance(entry.get("card"), str)
            and isinstance(entry.get("main"), str)
        ):
            pictures.append({"card": entry["card"], "main": entry["main"]})
    return pictures


def _put_image(s3_client: S3Writer, key: str, data: bytes) -> None:
    s3_client.put_object(
        Bucket=os.environ["DATA_BUCKET_NAME"],
        Key=key,
        Body=data,
        ContentType="image/webp",
        CacheControl=IMMUTABLE_CACHE,
    )


def _validation(error: ImageError) -> dict[str, Any]:
    return _no_store(
        400,
        {
            "error": "validation_failed",
            "details": [{"field": error.field, "message": error.message}],
        },
    )


def _version(body: object) -> int | None:
    if not isinstance(body, Mapping):
        return None
    version = body.get("version")
    if isinstance(version, int) and not isinstance(version, bool) and version >= 1:
        return version
    return None


def _save_pictures(
    product_id: str,
    pictures: list[dict[str, str]],
    version: int,
    products: AdminProductsTable,
    s3_client: S3Writer | None,
    now: datetime,
) -> dict[str, Any]:
    return _conditional_update(
        product_id,
        "SET #image = :image, #gallery = :gallery, version = version + :one, "
        "updatedAt = :updatedAt, updatedBy = :actor",
        {"#image": "image", "#gallery": "gallery"},
        {
            ":image": pictures[0] if pictures else {},
            ":gallery": pictures[1:],
            ":expected": version,
            ":one": 1,
            ":updatedAt": _iso(now),
            ":actor": ACTOR,
        },
        "attribute_exists(productId) AND version = :expected",
        products,
        s3_client,
        now,
        rebuild=lambda product: product.get("status") == "PUBLISHED",
    )


def _load_product(
    product_id: str, version: int, products: AdminProductsTable
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    item = products.get_item(Key={"productId": product_id}).get("Item")
    if not isinstance(item, Mapping):
        return None, error_response(404, "not_found")
    if item.get("version") != version:
        return None, _no_store(
            409, {"error": "version_conflict", "currentVersion": item.get("version")}
        )
    return dict(item), None


def _upload_product_picture(
    product_id: str,
    slot: int,
    event: Mapping[str, Any],
    products: AdminProductsTable,
    s3_client: S3Writer | None,
    now: datetime,
) -> dict[str, Any]:
    body = parse_json_body(event, MAX_IMAGE_BODY_BYTES)
    version = _version(body)
    if version is None or not isinstance(body, Mapping):
        return _no_store(
            400,
            {
                "error": "validation_failed",
                "details": [{"field": "version", "message": "is required"}],
            },
        )
    try:
        card_raw = decode_base64("card", body.get("card"))
        card = check_webp("card", card_raw, CARD_MAX_SIDE)
        main_raw = decode_base64("main", body.get("main"))
        main = check_webp("main", main_raw, MAIN_MAX_SIDE)
    except ImageError as error:
        return _validation(error)

    product, failure = _load_product(product_id, version, products)
    if failure is not None or product is None:
        return failure or error_response(404, "not_found")
    pictures = _picture_list(product)
    if slot > len(pictures) + 1:
        return _no_store(
            400,
            {
                "error": "validation_failed",
                "details": [
                    {"field": "slot", "message": "fill the earlier pictures first"}
                ],
            },
        )

    stamp = int(now.timestamp())
    prefix = f"media/products/{product_id}/" + (f"s{slot}-" if slot > 1 else "")
    entry = {
        "card": f"{prefix}card-v{stamp}.webp",
        "main": f"{prefix}main-v{stamp}.webp",
    }
    writer = s3_client if s3_client is not None else create_s3_client()
    _put_image(writer, entry["card"], card)
    _put_image(writer, entry["main"], main)
    if slot > len(pictures):
        pictures.append(entry)
    else:
        pictures[slot - 1] = entry
    return _save_pictures(product_id, pictures, version, products, writer, now)


def _remove_product_picture(
    product_id: str,
    slot: int,
    event: Mapping[str, Any],
    products: AdminProductsTable,
    s3_client: S3Writer | None,
    now: datetime,
) -> dict[str, Any]:
    version = _version(parse_json_body(event))
    if version is None:
        return _no_store(
            400,
            {
                "error": "validation_failed",
                "details": [{"field": "version", "message": "is required"}],
            },
        )
    product, failure = _load_product(product_id, version, products)
    if failure is not None or product is None:
        return failure or error_response(404, "not_found")
    pictures = _picture_list(product)
    if slot > len(pictures):
        return error_response(404, "not_found")
    del pictures[slot - 1]
    return _save_pictures(product_id, pictures, version, products, s3_client, now)


def _offer_with_image(
    config_table: AdminSiteConfigTable, image_key: str | None
) -> dict[str, Any] | None:
    item = config_table.get_item(Key={"configKey": "site"}).get("Item")
    if not isinstance(item, Mapping):
        return None
    stored = item.get("offerBanner")
    offer: dict[str, Any] = dict(stored) if isinstance(stored, Mapping) else {}
    if image_key is None:
        offer.pop("image", None)
    else:
        offer["image"] = image_key
    return offer


def _save_offer(
    config_table: AdminSiteConfigTable, offer: dict[str, Any]
) -> dict[str, Any]:
    config_table.update_item(
        Key={"configKey": "site"},
        UpdateExpression="SET offerBanner = :offer",
        ConditionExpression="attribute_exists(configKey)",
        ExpressionAttributeValues={":offer": offer},
    )
    return _no_store(200, {"offerBanner": offer})


def _upload_poster(
    event: Mapping[str, Any],
    config_table: AdminSiteConfigTable,
    s3_client: S3Writer | None,
    now: datetime,
) -> dict[str, Any]:
    body = parse_json_body(event, MAX_IMAGE_BODY_BYTES)
    try:
        raw = body.get("poster") if isinstance(body, Mapping) else None
        poster = check_webp("poster", decode_base64("poster", raw), POSTER_MAX_SIDE)
    except ImageError as error:
        return _validation(error)
    key = f"media/offer/poster-v{int(now.timestamp())}.webp"
    offer = _offer_with_image(config_table, key)
    if offer is None:
        return error_response(404, "not_found")
    writer = s3_client if s3_client is not None else create_s3_client()
    _put_image(writer, key, poster)
    return _save_offer(config_table, offer)


def handler(
    event: dict[str, Any],
    context: object,
    *,
    table: AdminProductsTable | None = None,
    site_config_table: AdminSiteConfigTable | None = None,
    s3_client: S3Writer | None = None,
    ssm_client: ParameterReader | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    del context
    denied = authorize(event, ssm_client=ssm_client)
    if denied is not None:
        return denied

    moment = now if now is not None else datetime.now(UTC)
    route = event.get("routeKey")
    params = event.get("pathParameters") or {}
    try:
        if route in (
            "PUT /admin/products/{id}/images/{slot}",
            "POST /admin/products/{id}/images/{slot}/remove",
        ):
            raw_id = params.get("id")
            raw_slot = params.get("slot")
            if (
                not isinstance(raw_id, str)
                or PRODUCT_ID_PATTERN.fullmatch(raw_id) is None
                or raw_slot not in ("1", "2", "3")
            ):
                return error_response(404, "not_found")
            products = table if table is not None else create_admin_products_table()
            action = (
                _upload_product_picture
                if route.startswith("PUT")
                else _remove_product_picture
            )
            return action(raw_id, int(raw_slot), event, products, s3_client, moment)

        if route in (
            "PUT /admin/site-config/offer/image",
            "POST /admin/site-config/offer/image/remove",
        ):
            config = (
                site_config_table
                if site_config_table is not None
                else create_admin_site_config_table()
            )
            if route.startswith("PUT"):
                return _upload_poster(event, config, s3_client, moment)
            offer = _offer_with_image(config, None)
            if offer is None:
                return error_response(404, "not_found")
            return _save_offer(config, offer)
        return error_response(404, "not_found")
    except BodyError as error:
        return error_response(error.status_code, error.error)
    except Exception as error:
        LOGGER.error("Admin image request failed (%s)", type(error).__name__)
        return error_response(500, "internal_error")
