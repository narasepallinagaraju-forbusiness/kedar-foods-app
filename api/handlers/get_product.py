"""GET /products/{slug}; omit ``image`` when no final media keys are present.

The frontend builds an image URL by prefixing each returned key with ``/``.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from importlib import import_module
from typing import Any

from .common import error_response, json_response
from .dynamodb import ProductsTable, create_products_table, slug_key_condition

LOGGER = logging.getLogger(__name__)
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED_STATUSES = frozenset({"DRAFT", "PUBLISHED", "UNPUBLISHED", "ARCHIVED"})
PRODUCT_PUBLIC_FIELDS = (
    "sku",
    "slug",
    "name",
    "brand",
    "category",
    "businessType",
    "quantities",
    "description",
    "updatedAt",
)


def _public_product(item: Mapping[str, Any]) -> dict[str, Any]:
    public_item: dict[str, Any] = {}
    product_id = item.get("productId")
    if isinstance(product_id, str):
        public_item["id"] = product_id

    for field in PRODUCT_PUBLIC_FIELDS:
        if field in item:
            public_item[field] = item[field]

    raw_image = item.get("image")
    if isinstance(raw_image, Mapping):
        image = {
            field: key
            for field in ("card", "main")
            if isinstance((key := raw_image.get(field)), str)
            and key.startswith("media/")
        }
        if image:
            public_item["image"] = image

    return public_item


def handler(
    event: dict[str, Any],
    context: object,
    *,
    table: ProductsTable | None = None,
) -> dict[str, Any]:
    del context
    path_parameters = event.get("pathParameters") or {}
    raw_slug = path_parameters.get("slug")
    if not isinstance(raw_slug, str):
        return error_response(404, "not_found")
    slug = raw_slug.lower()
    if SLUG_PATTERN.fullmatch(slug) is None:
        return error_response(404, "not_found")

    try:
        products_table = table if table is not None else create_products_table()
        result = products_table.query(
            IndexName="slug-index",
            KeyConditionExpression=slug_key_condition(slug),
        )
    except Exception as error:
        LOGGER.error("Product read failed (%s)", type(error).__name__)
        return error_response(500, "internal_error")

    items = result.get("Items", [])
    if not isinstance(items, list):
        return error_response(500, "internal_error")
    product = next(
        (
            item
            for item in items
            if isinstance(item, Mapping)
            and item.get("status") in ALLOWED_STATUSES
            and item.get("status") == "PUBLISHED"
        ),
        None,
    )
    if product is None:
        return error_response(404, "not_found")

    return json_response(
        200,
        _public_product(product),
        cache_control="public, max-age=0, must-revalidate",
    )


def warm_up() -> None:
    create_products_table()
    import_module("boto3.dynamodb.conditions")


if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    try:
        warm_up()
    except Exception as error:
        LOGGER.warning("Product handler warm-up failed (%s)", type(error).__name__)
