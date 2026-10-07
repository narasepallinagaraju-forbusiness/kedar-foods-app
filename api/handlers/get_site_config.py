"""GET /site-config with an explicit public response allowlist."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from .common import error_response, json_response
from .dynamodb import SiteConfigTable, create_site_config_table

LOGGER = logging.getLogger(__name__)


def _copy_strings(source: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, str]:
    return {
        field: value
        for field in fields
        if isinstance((value := source.get(field)), str)
    }


def _public_config(item: Mapping[str, Any]) -> dict[str, Any]:
    public_config: dict[str, Any] = {}

    raw_banner = item.get("offerBanner")
    if isinstance(raw_banner, Mapping):
        banner: dict[str, Any] = {}
        enabled = raw_banner.get("enabled")
        if isinstance(enabled, bool):
            banner["enabled"] = enabled
        banner.update(_copy_strings(raw_banner, ("text", "link")))
        if banner:
            public_config["offerBanner"] = banner

    raw_categories = item.get("categories")
    if isinstance(raw_categories, list):
        categories: list[dict[str, Any]] = []
        for raw_category in raw_categories:
            if not isinstance(raw_category, Mapping):
                continue
            category: dict[str, Any] = _copy_strings(
                raw_category,
                ("id", "name", "slug"),
            )
            sort_order = raw_category.get("sortOrder")
            if (
                isinstance(sort_order, (int, float))
                and not isinstance(sort_order, bool)
            ):
                category["sortOrder"] = sort_order
            elif isinstance(sort_order, Decimal):
                integral_value = sort_order.to_integral_value()
                if sort_order == integral_value:
                    category["sortOrder"] = int(integral_value)
                else:
                    category["sortOrder"] = float(sort_order)
            is_active = raw_category.get("isActive")
            if isinstance(is_active, bool):
                category["isActive"] = is_active
            if category:
                categories.append(category)
        public_config["categories"] = categories

    raw_whatsapp = item.get("whatsapp")
    if isinstance(raw_whatsapp, Mapping):
        whatsapp = _copy_strings(
            raw_whatsapp,
            ("number", "display", "messageTemplate", "generalMessage"),
        )
        if whatsapp:
            public_config["whatsapp"] = whatsapp

    return public_config


def handler(
    event: dict[str, Any],
    context: object,
    *,
    table: SiteConfigTable | None = None,
) -> dict[str, Any]:
    del event, context
    try:
        config_table = table if table is not None else create_site_config_table()
        result = config_table.get_item(Key={"configKey": "site"})
    except Exception as error:
        LOGGER.error("Site configuration read failed (%s)", type(error).__name__)
        return error_response(500, "internal_error")

    item = result.get("Item")
    if not isinstance(item, Mapping):
        return error_response(404, "not_found")

    return json_response(
        200,
        _public_config(item),
        cache_control="public, max-age=0, must-revalidate",
    )


def warm_up() -> None:
    create_site_config_table()


if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    try:
        warm_up()
    except Exception as error:
        LOGGER.warning(
            "Site configuration handler warm-up failed (%s)",
            type(error).__name__,
        )
