"""Shared-secret admin key check and request body parsing for admin routes."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from typing import Any

from .common import error_response
from .dynamodb import ParameterReader, create_ssm_client

LOGGER = logging.getLogger(__name__)
ADMIN_KEY_HEADER = "x-admin-key"
CACHE_SECONDS = 300.0
MIN_KEY_LENGTH = 32
MAX_BODY_BYTES = 64 * 1024

_CACHE: dict[str, Any] = {"value": None, "expires": 0.0}


class AdminKeyUnavailableError(Exception):
    """The configured admin key could not be read or is unusable."""


class BodyError(Exception):
    """The request body is missing, too large or not a JSON value."""

    def __init__(self, status_code: int, error: str) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error


def clear_admin_key_cache() -> None:
    _CACHE["value"] = None
    _CACHE["expires"] = 0.0


def _load_admin_key(
    ssm_client: ParameterReader | None,
    clock: Callable[[], float],
) -> str:
    cached = _CACHE["value"]
    if isinstance(cached, str) and clock() < float(_CACHE["expires"]):
        return cached

    parameter_name = os.environ.get("ADMIN_KEY_PARAMETER")
    if not parameter_name:
        raise AdminKeyUnavailableError("parameter name not configured")
    try:
        client = ssm_client if ssm_client is not None else create_ssm_client()
        result = client.get_parameter(Name=parameter_name, WithDecryption=True)
        value = result["Parameter"]["Value"]
    except Exception as error:
        raise AdminKeyUnavailableError(type(error).__name__) from error
    if not isinstance(value, str) or len(value) < MIN_KEY_LENGTH:
        LOGGER.error("Admin key parameter is missing or shorter than the minimum")
        raise AdminKeyUnavailableError("unusable key")

    _CACHE["value"] = value
    _CACHE["expires"] = clock() + CACHE_SECONDS
    return value


def _header(event: Mapping[str, Any], name: str) -> str | None:
    headers = event.get("headers")
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == name and isinstance(value, str):
            return value
    return None


def authorize(
    event: Mapping[str, Any],
    *,
    ssm_client: ParameterReader | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any] | None:
    """Return None when the key is valid, otherwise a ready error response."""
    try:
        expected = _load_admin_key(ssm_client, clock)
    except AdminKeyUnavailableError as error:
        LOGGER.error("Admin key unavailable (%s)", error)
        return error_response(503, "admin_key_unavailable")

    supplied = _header(event, ADMIN_KEY_HEADER)
    if supplied is None or not hmac.compare_digest(
        supplied.encode("utf-8"), expected.encode("utf-8")
    ):
        LOGGER.warning("admin key rejected")
        return error_response(401, "unauthorized")
    return None


def parse_json_body(event: Mapping[str, Any]) -> object:
    raw = event.get("body")
    if not isinstance(raw, str) or raw == "":
        raise BodyError(400, "body_required")
    if event.get("isBase64Encoded") is True:
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as error:
            raise BodyError(400, "invalid_json") from error
    else:
        data = raw.encode("utf-8")
    if len(data) > MAX_BODY_BYTES:
        raise BodyError(413, "body_too_large")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise BodyError(400, "invalid_json") from error
