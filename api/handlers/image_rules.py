"""Server-side checks for uploaded WebP images; the browser is never trusted."""

from __future__ import annotations

import base64
import binascii

MIN_IMAGE_BYTES = 1024
MAX_IMAGE_BYTES = 600 * 1024
CARD_MAX_SIDE = 800
MAIN_MAX_SIDE = 1600
POSTER_MAX_SIDE = 1600
MAX_PICTURES = 3


class ImageError(Exception):
    """Raised with a short machine-friendly message naming the bad field."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


def decode_base64(field: str, value: object) -> bytes:
    if not isinstance(value, str) or value == "":
        raise ImageError(field, "is required")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ImageError(field, "is not valid base64") from error


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        return (
            int.from_bytes(data[26:28], "little") & 0x3FFF,
            int.from_bytes(data[28:30], "little") & 0x3FFF,
        )
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X" and len(data) >= 30:
        return (
            int.from_bytes(data[24:27], "little") + 1,
            int.from_bytes(data[27:30], "little") + 1,
        )
    raise ValueError("unknown WebP layout")


def check_webp(field: str, data: bytes, max_side: int) -> bytes:
    """Return the bytes when they are a complete WebP within size limits."""
    if not MIN_IMAGE_BYTES <= len(data) <= MAX_IMAGE_BYTES:
        raise ImageError(field, "must be between 1 KB and 600 KB")
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ImageError(field, "must be a WebP image")
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ImageError(field, "is incomplete or corrupted")
    try:
        width, height = _webp_dimensions(data)
    except ValueError as error:
        raise ImageError(field, "is not a readable WebP image") from error
    if not 1 <= width <= max_side or not 1 <= height <= max_side:
        raise ImageError(field, f"must be at most {max_side} pixels on each side")
    return data
