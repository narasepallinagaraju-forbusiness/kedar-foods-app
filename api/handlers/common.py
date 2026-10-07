"""Shared JSON response and DynamoDB value helpers."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


def json_response(
    status_code: int,
    body: dict[str, Any],
    *,
    cache_control: str,
) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": cache_control,
        },
        "body": json.dumps(body, default=json_default, separators=(",", ":")),
    }


def json_default(value: object) -> int | float:
    if isinstance(value, Decimal):
        integral_value = value.to_integral_value()
        if value == integral_value:
            return int(integral_value)
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def error_response(status_code: int, error: str) -> dict[str, Any]:
    return json_response(
        status_code,
        {"error": error},
        cache_control="no-store",
    )
