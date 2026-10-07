"""Tests for the admin key check and body parsing."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from typing import Any

import pytest

from api.handlers import admin_auth
from api.handlers.admin_auth import (
    BodyError,
    authorize,
    clear_admin_key_cache,
    parse_json_body,
)

from .admin_fakes import FakeSsm

KEY = "k" * 40


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ADMIN_KEY_PARAMETER", "/test/admin-key")
    clear_admin_key_cache()
    yield
    clear_admin_key_cache()


def _event(key: str | None, header: str = "x-admin-key") -> dict[str, Any]:
    return {"headers": {} if key is None else {header: key}}


def test_correct_key_is_accepted_case_insensitively() -> None:
    assert authorize(_event(KEY), ssm_client=FakeSsm()) is None
    assert authorize(_event(KEY, "X-Admin-Key"), ssm_client=FakeSsm()) is None


@pytest.mark.parametrize("supplied", [None, "", "wrong", KEY + "x", "é" * 40])
def test_missing_or_wrong_key_returns_401(supplied: str | None) -> None:
    response = authorize(_event(supplied), ssm_client=FakeSsm())

    assert response is not None
    assert response["statusCode"] == 401
    assert KEY not in response["body"]


def test_unreadable_parameter_returns_503_and_never_allows() -> None:
    response = authorize(_event(KEY), ssm_client=FakeSsm(fail=True))

    assert response is not None
    assert response["statusCode"] == 503


def test_short_or_empty_key_in_store_returns_503() -> None:
    for stored in ("short", "", None):
        clear_admin_key_cache()
        response = authorize(_event("short"), ssm_client=FakeSsm(stored))
        assert response is not None
        assert response["statusCode"] == 503


def test_missing_parameter_name_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_KEY_PARAMETER")

    response = authorize(_event(KEY), ssm_client=FakeSsm())

    assert response is not None
    assert response["statusCode"] == 503


def test_key_is_cached_then_reread_after_expiry() -> None:
    ssm = FakeSsm()
    now = [0.0]

    def clock() -> float:
        return now[0]

    authorize(_event(KEY), ssm_client=ssm, clock=clock)
    authorize(_event(KEY), ssm_client=ssm, clock=clock)
    assert ssm.calls == 1

    now[0] = admin_auth.CACHE_SECONDS + 1
    authorize(_event(KEY), ssm_client=ssm, clock=clock)
    assert ssm.calls == 2


def test_rotated_key_is_used_after_expiry() -> None:
    ssm = FakeSsm()
    now = [0.0]
    authorize(_event(KEY), ssm_client=ssm, clock=lambda: now[0])

    ssm.value = "n" * 40
    now[0] = admin_auth.CACHE_SECONDS + 1

    old = authorize(_event(KEY), ssm_client=ssm, clock=lambda: now[0])
    assert old is not None and old["statusCode"] == 401
    assert authorize(_event("n" * 40), ssm_client=ssm, clock=lambda: now[0]) is None


def test_key_never_appears_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    authorize(_event("guess-guess-guess"), ssm_client=FakeSsm())
    authorize(_event(KEY), ssm_client=FakeSsm(fail=True))

    assert KEY not in caplog.text
    assert "guess-guess-guess" not in caplog.text


def test_parse_json_body_variants() -> None:
    assert parse_json_body({"body": '{"a": 1}'}) == {"a": 1}
    encoded = base64.b64encode(json.dumps({"a": 2}).encode()).decode()
    assert parse_json_body({"body": encoded, "isBase64Encoded": True}) == {"a": 2}


@pytest.mark.parametrize(
    ("event", "status"),
    [
        ({}, 400),
        ({"body": ""}, 400),
        ({"body": "{nope"}, 400),
        ({"body": "!!", "isBase64Encoded": True}, 400),
        ({"body": "x" * (64 * 1024 + 1)}, 413),
    ],
)
def test_parse_json_body_errors(event: dict[str, Any], status: int) -> None:
    with pytest.raises(BodyError) as raised:
        parse_json_body(event)

    assert raised.value.status_code == status
