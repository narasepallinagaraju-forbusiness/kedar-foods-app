"""Admin site-config routes: read the stored offer banner and update only it."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .admin_auth import BodyError, authorize, parse_json_body
from .common import error_response, json_response
from .dynamodb import (
    AdminSiteConfigTable,
    ParameterReader,
    create_admin_site_config_table,
)
from .product_validation import ProductValidationError, validate_offer

LOGGER = logging.getLogger(__name__)


def _no_store(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return json_response(status_code, body, cache_control="no-store")


def _condition_failed(error: Exception) -> bool:
    response = getattr(error, "response", None)
    details = response.get("Error") if isinstance(response, Mapping) else None
    return (
        isinstance(details, Mapping)
        and details.get("Code") == "ConditionalCheckFailedException"
    )


def handler(
    event: dict[str, Any],
    context: object,
    *,
    table: AdminSiteConfigTable | None = None,
    ssm_client: ParameterReader | None = None,
) -> dict[str, Any]:
    del context
    denied = authorize(event, ssm_client=ssm_client)
    if denied is not None:
        return denied

    route = event.get("routeKey")
    try:
        config_table = table if table is not None else create_admin_site_config_table()
        if route == "GET /admin/site-config":
            item = config_table.get_item(Key={"configKey": "site"}).get("Item")
            if not isinstance(item, Mapping):
                return error_response(404, "not_found")
            offer = item.get("offerBanner")
            return _no_store(
                200,
                {"offerBanner": dict(offer) if isinstance(offer, Mapping) else {}},
            )
        if route == "PUT /admin/site-config/offer":
            try:
                offer = validate_offer(parse_json_body(event))
            except ProductValidationError as error:
                return _no_store(
                    400, {"error": "validation_failed", "details": error.errors}
                )
            try:
                config_table.update_item(
                    Key={"configKey": "site"},
                    UpdateExpression="SET offerBanner = :offer",
                    ConditionExpression="attribute_exists(configKey)",
                    ExpressionAttributeValues={":offer": offer},
                )
            except Exception as error:
                if _condition_failed(error):
                    return error_response(404, "not_found")
                raise
            return _no_store(200, {"offerBanner": offer})
        return error_response(404, "not_found")
    except BodyError as error:
        return error_response(error.status_code, error.error)
    except Exception as error:
        LOGGER.error("Admin site-config request failed (%s)", type(error).__name__)
        return error_response(500, "internal_error")
