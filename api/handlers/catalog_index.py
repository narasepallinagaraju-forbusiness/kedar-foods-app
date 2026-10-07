"""Build the compact public catalogue index from product table items."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def _rank(value: Any) -> int:
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def build_catalog_index(
    items: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Return a versioned index containing only published public listing fields."""
    index_items: list[dict[str, Any]] = []
    for product in items:
        if product.get("status") != "PUBLISHED":
            continue
        name = product.get("name", "")
        brand = product.get("brand", "")
        category = product.get("category", "")
        image = product.get("image")
        item: dict[str, Any] = {
            "id": product.get("productId"),
            "sku": product.get("sku"),
            "slug": product.get("slug"),
            "name": name,
            "brand": brand,
            "category": category,
            "businessType": list(product.get("businessType", [])),
            "quantities": list(product.get("quantities", [])),
            "isTrending": product.get("isTrending", False),
            "searchText": " ".join(
                value.lower()
                for value in (name, brand, category)
                if isinstance(value, str)
            ),
            "sortRank": _rank(product.get("sortRank")),
        }
        if isinstance(image, dict) and isinstance(image.get("card"), str):
            item["thumbnailKey"] = image["card"]
        index_items.append(item)

    index_items.sort(key=lambda item: (item["sortRank"], item["name"]))
    return {"version": _timestamp(now), "items": index_items}
