"""Admin product routes: list, read, create, update, hide/show, index rebuild."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from .admin_auth import BodyError, authorize, parse_json_body
from .catalog_index import build_catalog_index
from .common import error_response, json_default, json_response
from .dynamodb import (
    AdminProductsTable,
    AdminSiteConfigTable,
    ParameterReader,
    S3Writer,
    create_admin_products_table,
    create_admin_site_config_table,
    create_s3_client,
)
from .product_validation import (
    ProductValidationError,
    product_id_from_sku,
    unique_slug,
    validate_create_product,
    validate_update_product,
)

LOGGER = logging.getLogger(__name__)
ACTOR = "admin-key"
INDEX_KEY = "data/catalog-index.json"
MAX_IMPORT_ROWS = 50
MAX_IMPORT_BODY_BYTES = 256 * 1024
PRODUCT_ID_PATTERN = re.compile(r"^prod_[0-9a-f]{10}$")
REQUIRED_TO_SHOW = ("slug", "name", "brand", "category", "businessType", "quantities")


class CategoriesUnavailableError(Exception):
    """Allowed categories could not be read from the site configuration."""


def _no_store(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return json_response(status_code, body, cache_control="no-store")


def _iso(now: datetime) -> str:
    return now.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _condition_failed(error: Exception) -> bool:
    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return False
    details = response.get("Error")
    return (
        isinstance(details, Mapping)
        and details.get("Code") == "ConditionalCheckFailedException"
    )


def _scan_all(table: AdminProductsTable) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    start_key: Any = None
    while True:
        kwargs: dict[str, Any] = {}
        if start_key is not None:
            kwargs["ExclusiveStartKey"] = start_key
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        start_key = page.get("LastEvaluatedKey")
        if not start_key:
            return items


def _allowed_categories(config_table: AdminSiteConfigTable) -> set[str]:
    try:
        item = config_table.get_item(Key={"configKey": "site"}).get("Item")
    except Exception as error:
        raise CategoriesUnavailableError(type(error).__name__) from error
    raw = item.get("categories") if isinstance(item, Mapping) else None
    if not isinstance(raw, list):
        raise CategoriesUnavailableError("no categories")
    names = {
        category["name"]
        for category in raw
        if isinstance(category, Mapping)
        and isinstance(category.get("name"), str)
        and category.get("isActive", True) is not False
    }
    if not names:
        raise CategoriesUnavailableError("no categories")
    return names


def _slug_exists(table: AdminProductsTable, slug: str) -> bool:
    result = table.query(
        IndexName="slug-index",
        KeyConditionExpression="slug = :slug",
        ExpressionAttributeValues={":slug": slug},
        Limit=1,
    )
    return bool(result.get("Items"))


def rebuild_index(
    products: AdminProductsTable,
    s3_client: S3Writer,
    now: datetime,
) -> bool:
    """Rebuild the public index; return False (never raise) if it fails."""
    try:
        index = build_catalog_index(_scan_all(products), now)
        s3_client.put_object(
            Bucket=os.environ["DATA_BUCKET_NAME"],
            Key=INDEX_KEY,
            Body=json.dumps(
                index, default=json_default, separators=(",", ":")
            ).encode("utf-8"),
            ContentType="application/json",
            CacheControl="public, max-age=0, must-revalidate",
        )
    except Exception as error:
        LOGGER.error("Catalog index rebuild failed (%s)", type(error).__name__)
        return False
    return True


def _write_result(
    product: Mapping[str, Any],
    *,
    rebuild: bool,
    products: AdminProductsTable,
    s3_client: S3Writer | None,
    now: datetime,
    status_code: int = 200,
) -> dict[str, Any]:
    index_rebuilt: bool | None = None
    if rebuild:
        try:
            writer = s3_client if s3_client is not None else create_s3_client()
        except Exception as error:
            LOGGER.error("S3 client failed (%s)", type(error).__name__)
            index_rebuilt = False
        else:
            index_rebuilt = rebuild_index(products, writer, now)
    body: dict[str, Any] = {"product": dict(product)}
    if index_rebuilt is not None:
        body["indexRebuilt"] = index_rebuilt
        if not index_rebuilt:
            body["message"] = (
                "Saved, but the public list was not refreshed. Rebuild it."
            )
    return _no_store(status_code, body)


def _validation_response(error: ProductValidationError) -> dict[str, Any]:
    return _no_store(400, {"error": "validation_failed", "details": error.errors})


def _insert_product(
    clean: dict[str, Any],
    products: AdminProductsTable,
    now: datetime,
) -> dict[str, Any] | None:
    """Write a new product; return None if the SKU already exists."""
    sku = clean["sku"]
    slug = unique_slug(
        clean["name"],
        clean["brand"],
        sku,
        lambda candidate: _slug_exists(products, candidate),
    )
    timestamp = _iso(now)
    item: dict[str, Any] = {
        **clean,
        "productId": product_id_from_sku(sku),
        "slug": slug,
        "version": 1,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "createdBy": ACTOR,
        "updatedBy": ACTOR,
    }
    item.setdefault("description", "")
    item.setdefault("isTrending", False)
    item.setdefault("sortRank", 0)
    try:
        products.put_item(
            Item=item, ConditionExpression="attribute_not_exists(productId)"
        )
    except Exception as error:
        if _condition_failed(error):
            return None
        raise
    return item


def _create(
    event: Mapping[str, Any],
    products: AdminProductsTable,
    config_table: AdminSiteConfigTable,
    s3_client: S3Writer | None,
    now: datetime,
) -> dict[str, Any]:
    body = parse_json_body(event)
    try:
        categories = _allowed_categories(config_table)
    except CategoriesUnavailableError as error:
        LOGGER.error("Categories unavailable (%s)", error)
        return error_response(503, "categories_unavailable")
    try:
        clean = validate_create_product(body, categories)
    except ProductValidationError as error:
        return _validation_response(error)

    item = _insert_product(clean, products, now)
    if item is None:
        return error_response(409, "duplicate_sku")
    return _write_result(
        item,
        rebuild=item["status"] == "PUBLISHED",
        products=products,
        s3_client=s3_client,
        now=now,
        status_code=201,
    )


def _import_products(
    event: Mapping[str, Any],
    products: AdminProductsTable,
    config_table: AdminSiteConfigTable,
    s3_client: S3Writer | None,
    now: datetime,
) -> dict[str, Any]:
    """Create many products. Never edits existing ones; duplicates are skipped."""
    body = parse_json_body(event, MAX_IMPORT_BODY_BYTES)
    rows = body.get("rows") if isinstance(body, Mapping) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_IMPORT_ROWS:
        return _no_store(
            400,
            {
                "error": "validation_failed",
                "details": [
                    {
                        "field": "rows",
                        "message": f"must be a list of 1 to {MAX_IMPORT_ROWS} rows",
                    }
                ],
            },
        )
    try:
        categories = _allowed_categories(config_table)
    except CategoriesUnavailableError as error:
        LOGGER.error("Categories unavailable (%s)", error)
        return error_response(503, "categories_unavailable")

    results: list[dict[str, Any]] = []
    published_created = False
    for index, row in enumerate(rows):
        sku = row.get("sku") if isinstance(row, Mapping) else None
        entry: dict[str, Any] = {
            "row": index,
            "sku": sku if isinstance(sku, str) else "",
        }
        try:
            if not isinstance(row, Mapping):
                raise ProductValidationError(
                    [{"field": "row", "message": "must be an object"}]
                )
            candidate = {**row, "status": row.get("status") or "PUBLISHED"}
            clean = validate_create_product(candidate, categories)
        except ProductValidationError as error:
            entry["result"] = "failed"
            entry["errors"] = error.errors
            results.append(entry)
            continue
        try:
            item = _insert_product(clean, products, now)
        except Exception as error:
            LOGGER.error("Import row failed (%s)", type(error).__name__)
            entry["result"] = "failed"
            entry["errors"] = [{"field": "row", "message": "could not be saved"}]
            results.append(entry)
            continue
        if item is None:
            entry["result"] = "skipped"
        else:
            entry["result"] = "created"
            published_created = published_created or item["status"] == "PUBLISHED"
        results.append(entry)

    counts = {
        name: sum(1 for r in results if r["result"] == name)
        for name in ("created", "skipped", "failed")
    }
    response: dict[str, Any] = {**counts, "results": results}
    if published_created:
        try:
            writer = s3_client if s3_client is not None else create_s3_client()
            response["indexRebuilt"] = rebuild_index(products, writer, now)
        except Exception as error:
            LOGGER.error("S3 client failed (%s)", type(error).__name__)
            response["indexRebuilt"] = False
    return _no_store(200, response)


def _update(
    product_id: str,
    event: Mapping[str, Any],
    products: AdminProductsTable,
    config_table: AdminSiteConfigTable,
    s3_client: S3Writer | None,
    now: datetime,
) -> dict[str, Any]:
    body = parse_json_body(event)
    try:
        categories = _allowed_categories(config_table)
    except CategoriesUnavailableError as error:
        LOGGER.error("Categories unavailable (%s)", error)
        return error_response(503, "categories_unavailable")
    try:
        fields, version = validate_update_product(body, categories)
    except ProductValidationError as error:
        return _validation_response(error)

    names: dict[str, str] = {}
    values: dict[str, Any] = {":expected": version, ":one": 1}
    assignments: list[str] = []
    for position, (field, value) in enumerate(fields.items()):
        names[f"#f{position}"] = field
        values[f":v{position}"] = value
        assignments.append(f"#f{position} = :v{position}")
    values[":updatedAt"] = _iso(now)
    values[":actor"] = ACTOR
    assignments.extend(
        ["version = version + :one", "updatedAt = :updatedAt", "updatedBy = :actor"]
    )
    return _conditional_update(
        product_id,
        "SET " + ", ".join(assignments),
        names,
        values,
        "attribute_exists(productId) AND version = :expected",
        products,
        s3_client,
        now,
        rebuild=lambda product: product.get("status") == "PUBLISHED",
    )


def _set_status(
    product_id: str,
    status: str,
    products: AdminProductsTable,
    s3_client: S3Writer | None,
    now: datetime,
) -> dict[str, Any]:
    if status == "PUBLISHED":
        current = products.get_item(Key={"productId": product_id}).get("Item")
        if not isinstance(current, Mapping):
            return error_response(404, "not_found")
        missing = [field for field in REQUIRED_TO_SHOW if not current.get(field)]
        if missing:
            return _no_store(
                400,
                {
                    "error": "incomplete_product",
                    "details": [
                        {"field": field, "message": "is required before showing"}
                        for field in missing
                    ],
                },
            )
    return _conditional_update(
        product_id,
        "SET #status = :status, version = version + :one, "
        "updatedAt = :updatedAt, updatedBy = :actor",
        {"#status": "status"},
        {
            ":status": status,
            ":one": 1,
            ":updatedAt": _iso(now),
            ":actor": ACTOR,
        },
        "attribute_exists(productId)",
        products,
        s3_client,
        now,
        rebuild=lambda _product: True,
    )


def _conditional_update(
    product_id: str,
    expression: str,
    names: dict[str, str],
    values: dict[str, Any],
    condition: str,
    products: AdminProductsTable,
    s3_client: S3Writer | None,
    now: datetime,
    *,
    rebuild: Callable[[Mapping[str, Any]], bool],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "Key": {"productId": product_id},
        "UpdateExpression": expression,
        "ConditionExpression": condition,
        "ExpressionAttributeValues": values,
        "ReturnValues": "ALL_NEW",
    }
    if names:
        kwargs["ExpressionAttributeNames"] = names
    try:
        result = products.update_item(**kwargs)
    except Exception as error:
        if not _condition_failed(error):
            raise
        existing = products.get_item(Key={"productId": product_id}).get("Item")
        if not isinstance(existing, Mapping):
            return error_response(404, "not_found")
        return _no_store(
            409,
            {"error": "version_conflict", "currentVersion": existing.get("version")},
        )
    product = result.get("Attributes", {})
    return _write_result(
        product,
        rebuild=rebuild(product),
        products=products,
        s3_client=s3_client,
        now=now,
    )


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
    raw_id = (event.get("pathParameters") or {}).get("id")
    product_id = (
        raw_id
        if isinstance(raw_id, str) and PRODUCT_ID_PATTERN.fullmatch(raw_id)
        else None
    )

    try:
        products = table if table is not None else create_admin_products_table()
        config = (
            site_config_table
            if site_config_table is not None
            else create_admin_site_config_table()
        )
        if route == "GET /admin/products":
            items = sorted(
                _scan_all(products),
                key=lambda item: (item.get("sortRank", 0), item.get("name", "")),
            )
            return _no_store(200, {"products": items})
        if route == "POST /admin/products/import":
            return _import_products(event, products, config, s3_client, moment)
        if route == "POST /admin/products":
            return _create(event, products, config, s3_client, moment)
        if route == "POST /admin/catalog-index/rebuild":
            try:
                writer = s3_client if s3_client is not None else create_s3_client()
                rebuilt = rebuild_index(products, writer, moment)
            except Exception as error:
                LOGGER.error("S3 client failed (%s)", type(error).__name__)
                rebuilt = False
            if not rebuilt:
                return error_response(500, "index_rebuild_failed")
            return _no_store(200, {"indexRebuilt": True})

        if (
            route
            in (
                "GET /admin/products/{id}",
                "PUT /admin/products/{id}",
                "POST /admin/products/{id}/archive",
                "POST /admin/products/{id}/restore",
            )
        ):
            if product_id is None:
                return error_response(404, "not_found")
            if route == "GET /admin/products/{id}":
                item = products.get_item(Key={"productId": product_id}).get("Item")
                if not isinstance(item, Mapping):
                    return error_response(404, "not_found")
                return _no_store(200, {"product": dict(item)})
            if route == "PUT /admin/products/{id}":
                return _update(product_id, event, products, config, s3_client, moment)
            status = "ARCHIVED" if route.endswith("/archive") else "PUBLISHED"
            return _set_status(product_id, status, products, s3_client, moment)
        return error_response(404, "not_found")
    except BodyError as error:
        return error_response(error.status_code, error.error)
    except Exception as error:
        LOGGER.error("Admin product request failed (%s)", type(error).__name__)
        return error_response(500, "internal_error")
