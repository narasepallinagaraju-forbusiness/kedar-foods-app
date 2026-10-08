"""Pure validation and identifier rules for admin product and offer writes."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable, Collection, Mapping
from datetime import date
from typing import Any

BUSINESS_TYPES = ("Bakery", "Cafe", "Restaurant")
CREATE_STATUSES = frozenset({"PUBLISHED", "ARCHIVED"})
DEFAULT_CREATE_STATUS = "ARCHIVED"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SKU_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,28}[A-Z0-9]$")
SLUG_SEPARATORS = re.compile(r"[^a-z0-9]+")
MAX_SORT_RANK = 100_000
OFFER_TEXT_MAX = 160
OFFER_LINK_MAX = 200

_REQUIRED_FIELDS = ("name", "brand", "category", "businessType", "quantities")
_OPTIONAL_FIELDS = ("description", "isTrending", "sortRank")
_EDITABLE_FIELDS = (*_REQUIRED_FIELDS, *_OPTIONAL_FIELDS)
_CREATE_KEYS = frozenset({*_EDITABLE_FIELDS, "sku", "status"})
_UPDATE_KEYS = frozenset({*_EDITABLE_FIELDS, "version"})
_OFFER_KEYS = frozenset({"enabled", "text", "link", "startDate", "endDate"})


class ProductValidationError(Exception):
    """Raised with one or more field-level messages."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{e['field']}: {e['message']}" for e in errors))
        self.errors = errors


def _has_control(value: str, *, allow_newlines: bool = False) -> bool:
    for char in value:
        if allow_newlines and char in "\n\t":
            continue
        if unicodedata.category(char) == "Cc":
            return True
    return False


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def slugify(value: str) -> str:
    slug = SLUG_SEPARATORS.sub("-", value.lower()).strip("-")
    if SLUG_PATTERN.fullmatch(slug) is None:
        raise ValueError(f"Cannot generate a valid slug from {value!r}.")
    return slug


def product_id_from_sku(sku: str) -> str:
    digest = hashlib.sha1(sku.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"prod_{digest[:10]}"


def unique_slug(
    name: str,
    brand: str,
    sku: str,
    slug_exists: Callable[[str], bool],
) -> str:
    """Return the first free slug from name, then name-brand, then name-brand-sku."""
    base = slugify(name)
    candidates = [base, slugify(f"{base}-{brand}")]
    candidates.append(slugify(f"{candidates[1]}-{sku}"))
    for candidate in candidates:
        if not slug_exists(candidate):
            return candidate
    raise ValueError("No unique slug is available for this product.")


def safe_link(value: object) -> str | None:
    """Mirror of the customer safeLink rule: relative path or https URL only."""
    if not isinstance(value, str) or value == "":
        return None
    if any(char.isspace() or unicodedata.category(char) == "Cc" for char in value):
        return None
    if "\\" in value or value.startswith("//"):
        return None
    if value.startswith("/"):
        return value
    if value.startswith("https://") and len(value) > len("https://"):
        return value
    return None


def _check_text(
    body: Mapping[str, Any],
    field: str,
    low: int,
    high: int,
    errors: list[dict[str, str]],
    *,
    allow_newlines: bool = False,
) -> str | None:
    value = body.get(field)
    if not isinstance(value, str):
        errors.append({"field": field, "message": "must be text"})
        return None
    text = value.strip()
    if not low <= len(text) <= high:
        errors.append(
            {"field": field, "message": f"must be {low}-{high} characters"}
        )
        return None
    if _has_control(text, allow_newlines=allow_newlines):
        errors.append({"field": field, "message": "contains control characters"})
        return None
    return text


def _check_unknown(
    body: Mapping[str, Any],
    allowed: frozenset[str],
    errors: list[dict[str, str]],
) -> None:
    for key in sorted(set(body) - allowed):
        errors.append({"field": str(key), "message": "is not allowed"})


def _validate_editable(
    body: Mapping[str, Any],
    categories: Collection[str],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    clean: dict[str, Any] = {}

    name = _check_text(body, "name", 2, 120, errors)
    if name is not None:
        clean["name"] = name
    brand = _check_text(body, "brand", 1, 60, errors)
    if brand is not None:
        clean["brand"] = brand

    category = body.get("category")
    if not isinstance(category, str) or category not in categories:
        errors.append({"field": "category", "message": "is not an allowed category"})
    else:
        clean["category"] = category

    business_type = body.get("businessType")
    if (
        not isinstance(business_type, list)
        or not business_type
        or not all(isinstance(item, str) for item in business_type)
        or any(item not in BUSINESS_TYPES for item in business_type)
        or len(set(business_type)) != len(business_type)
    ):
        errors.append(
            {
                "field": "businessType",
                "message": "must list one or more of "
                + ", ".join(BUSINESS_TYPES)
                + " without duplicates",
            }
        )
    else:
        clean["businessType"] = list(business_type)

    quantities = body.get("quantities")
    quantity_problem = "must be 1-12 unique pack sizes of 1-20 characters"
    if (
        not isinstance(quantities, list)
        or not 1 <= len(quantities) <= 12
        or not all(isinstance(item, str) for item in quantities)
    ):
        errors.append({"field": "quantities", "message": quantity_problem})
    else:
        cleaned = [item.strip() for item in quantities]
        if (
            any(not 1 <= len(item) <= 20 or _has_control(item) for item in cleaned)
            or len(set(cleaned)) != len(cleaned)
        ):
            errors.append({"field": "quantities", "message": quantity_problem})
        else:
            clean["quantities"] = cleaned

    if "description" in body:
        value = body["description"]
        if not isinstance(value, str) or len(value) > 2000:
            errors.append(
                {"field": "description", "message": "must be text up to 2000 chars"}
            )
        elif _has_control(value, allow_newlines=True):
            errors.append(
                {"field": "description", "message": "contains control characters"}
            )
        else:
            clean["description"] = value.strip()

    if "isTrending" in body:
        if not isinstance(body["isTrending"], bool):
            errors.append({"field": "isTrending", "message": "must be true or false"})
        else:
            clean["isTrending"] = body["isTrending"]

    if "sortRank" in body:
        rank = body["sortRank"]
        if not _is_int(rank) or not 0 <= rank <= MAX_SORT_RANK:
            errors.append(
                {
                    "field": "sortRank",
                    "message": f"must be a whole number 0-{MAX_SORT_RANK}",
                }
            )
        else:
            clean["sortRank"] = rank

    return clean


def validate_create_product(
    body: object,
    categories: Collection[str],
) -> dict[str, Any]:
    """Return cleaned create fields including ``sku`` and ``status``."""
    if not isinstance(body, Mapping):
        raise ProductValidationError(
            [{"field": "body", "message": "must be a JSON object"}]
        )
    errors: list[dict[str, str]] = []
    _check_unknown(body, _CREATE_KEYS, errors)
    clean = _validate_editable(body, categories, errors)

    sku = body.get("sku")
    if not isinstance(sku, str) or SKU_PATTERN.fullmatch(sku) is None:
        errors.append(
            {
                "field": "sku",
                "message": "must be 2-30 characters of A-Z, 0-9 and hyphens",
            }
        )
    else:
        clean["sku"] = sku

    status = body.get("status", DEFAULT_CREATE_STATUS)
    if status not in CREATE_STATUSES:
        errors.append({"field": "status", "message": "must be PUBLISHED or ARCHIVED"})
    else:
        clean["status"] = status

    if errors:
        raise ProductValidationError(errors)
    return clean


def validate_update_product(
    body: object,
    categories: Collection[str],
) -> tuple[dict[str, Any], int]:
    """Return cleaned editable fields and the client's expected ``version``."""
    if not isinstance(body, Mapping):
        raise ProductValidationError(
            [{"field": "body", "message": "must be a JSON object"}]
        )
    errors: list[dict[str, str]] = []
    _check_unknown(body, _UPDATE_KEYS, errors)
    clean = _validate_editable(body, categories, errors)

    raw_version = body.get("version")
    version = 0
    if isinstance(raw_version, int) and not isinstance(raw_version, bool):
        version = raw_version
    if version < 1:
        errors.append({"field": "version", "message": "must be a whole number >= 1"})

    if errors:
        raise ProductValidationError(errors)
    return clean, version


def validate_offer(body: object) -> dict[str, Any]:
    """Return ``{enabled, text, link}`` for the public offer banner."""
    if not isinstance(body, Mapping):
        raise ProductValidationError(
            [{"field": "body", "message": "must be a JSON object"}]
        )
    errors: list[dict[str, str]] = []
    _check_unknown(body, _OFFER_KEYS, errors)

    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        errors.append({"field": "enabled", "message": "must be true or false"})

    text_value = body.get("text", "")
    text = ""
    if not isinstance(text_value, str):
        errors.append({"field": "text", "message": "must be text"})
    else:
        text = text_value.strip()
        if len(text) > OFFER_TEXT_MAX:
            errors.append(
                {"field": "text", "message": f"must be at most {OFFER_TEXT_MAX} chars"}
            )
        elif _has_control(text):
            errors.append({"field": "text", "message": "contains control characters"})
        elif enabled is True and not text:
            errors.append({"field": "text", "message": "is required when enabled"})

    link_value = body.get("link", "")
    link = ""
    if not isinstance(link_value, str):
        errors.append({"field": "link", "message": "must be text"})
    elif link_value != "":
        if len(link_value) > OFFER_LINK_MAX or safe_link(link_value) is None:
            errors.append(
                {
                    "field": "link",
                    "message": "must start with a single / or https://",
                }
            )
        else:
            link = link_value

    offer: dict[str, Any] = {"enabled": enabled, "text": text, "link": link}
    dates: dict[str, str] = {}
    for field in ("startDate", "endDate"):
        raw = body.get(field, "")
        if raw is None or raw == "":
            continue
        parsed = _parse_date(raw)
        if parsed is None:
            errors.append(
                {"field": field, "message": "must be a real date as YYYY-MM-DD"}
            )
        else:
            dates[field] = parsed.isoformat()
    if (
        "startDate" in dates
        and "endDate" in dates
        and dates["endDate"] < dates["startDate"]
    ):
        errors.append(
            {"field": "endDate", "message": "must not be before the start date"}
        )

    if errors:
        raise ProductValidationError(errors)
    offer.update(dates)
    return offer


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or DATE_PATTERN.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
