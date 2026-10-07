"""Parse the portal export and seed the public catalogue when explicitly requested."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

if TYPE_CHECKING:
    from api.handlers.catalog_index import build_catalog_index
else:
    build_catalog_index = cast(
        Callable[[list[dict[str, Any]], datetime], dict[str, Any]],
        importlib.import_module("api.handlers.catalog_index").build_catalog_index,
    )

EXPORT_PATH = REPOSITORY_ROOT / "seed" / "kedar-export-2026-10-07.js"
OFFER_PATH = REPOSITORY_ROOT / "seed" / "site-offer.json"
REGION = "ap-south-1"
IMAGE_TIMEOUT_SECONDS = 20
MAX_IMAGE_BYTES = 10 * 1024 * 1024
REQUIRED_CONSTANTS = (
    "PRODUCTS",
    "CATEGORIES",
    "WHATSAPP_NUMBER",
    "WHATSAPP_DISPLAY",
)
REQUIRED_PRODUCT_FIELDS = (
    "id",
    "name",
    "quantities",
    "category",
    "brand",
    "businessType",
    "description",
    "image",
    "isTrending",
)
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SLUG_SEPARATORS = re.compile(r"[^a-z0-9]+")
OFFER_DEFAULT = {"enabled": False, "text": "", "link": "/catalogue"}
PRODUCT_MESSAGE = (
    "Hi Kedar Foods! I am interested in bulk rates for {name}{pack} (SKU: {sku})?"
)
GENERAL_MESSAGE = (
    "Hi Kedar Foods! I'd like to enquire about bulk wholesale rates."
)


class SeedDataError(ValueError):
    """Raised when the source export cannot safely be transformed."""


class SeedOperationError(RuntimeError):
    """Raised when a requested AWS-backed seed operation fails."""


@dataclass(frozen=True)
class ExportData:
    products: list[dict[str, Any]]
    categories: list[str]
    whatsapp_number: str
    whatsapp_display: str


@dataclass
class MappedProduct:
    item: dict[str, Any]
    image_url: str


@dataclass(frozen=True)
class ImageVariant:
    data: bytes
    width: int
    height: int


@dataclass
class WriteCounts:
    created: int = 0
    skipped: int = 0
    failed: int = 0


def _decode_constant(
    source: str,
    constant_name: str,
    decoder: json.JSONDecoder,
) -> Any:
    marker = f"export const {constant_name} ="
    marker_position = source.find(marker)
    if marker_position < 0:
        raise SeedDataError(
            f"Export is missing required constant {constant_name!r}."
        )
    value_start = marker_position + len(marker)
    while value_start < len(source) and source[value_start].isspace():
        value_start += 1
    try:
        value, _ = decoder.raw_decode(source, value_start)
    except json.JSONDecodeError as error:
        raise SeedDataError(
            f"Could not parse JSON value for export constant {constant_name!r}: "
            f"{error.msg} at line {error.lineno}, column {error.colno}."
        ) from error
    return value


def _reject_floats(value: Any, location: str) -> None:
    if isinstance(value, float):
        raise SeedDataError(f"Floating-point value is not allowed at {location}.")
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            _reject_floats(nested_value, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            _reject_floats(nested_value, f"{location}[{index}]")


def parse_export_text(source: str) -> ExportData:
    """Read the four JSON-exported constants without evaluating JavaScript."""
    decoder = json.JSONDecoder()
    constants = {
        name: _decode_constant(source, name, decoder) for name in REQUIRED_CONSTANTS
    }
    products = constants["PRODUCTS"]
    categories = constants["CATEGORIES"]
    whatsapp_number = constants["WHATSAPP_NUMBER"]
    whatsapp_display = constants["WHATSAPP_DISPLAY"]
    if not isinstance(products, list):
        raise SeedDataError("Export constant 'PRODUCTS' must be an array.")
    if not isinstance(categories, list) or not all(
        isinstance(category, str) for category in categories
    ):
        raise SeedDataError("Export constant 'CATEGORIES' must be an array of strings.")
    if not isinstance(whatsapp_number, str) or not isinstance(
        whatsapp_display, str
    ):
        raise SeedDataError(
            "Export constants 'WHATSAPP_NUMBER' and 'WHATSAPP_DISPLAY' "
            "must be strings."
        )

    seen_ids: set[str] = set()
    seen_source_slugs: set[str] = set()
    validated_products: list[dict[str, Any]] = []
    for position, product in enumerate(products, start=1):
        if not isinstance(product, dict):
            raise SeedDataError(f"Product at position {position} must be an object.")
        missing = [field for field in REQUIRED_PRODUCT_FIELDS if field not in product]
        if missing:
            raise SeedDataError(
                f"Product at position {position} is missing required field(s): "
                f"{', '.join(missing)}."
            )
        if not isinstance(product["id"], str) or not product["id"]:
            raise SeedDataError(f"Product at position {position} has an invalid id.")
        if product["id"] in seen_ids:
            raise SeedDataError(f"Duplicate product id {product['id']!r}.")
        seen_ids.add(product["id"])
        if "slug" in product:
            slug = product["slug"]
            if not isinstance(slug, str) or SLUG_PATTERN.fullmatch(slug) is None:
                raise SeedDataError(
                    f"Product {product['id']!r} has an invalid provided slug."
                )
            if slug in seen_source_slugs:
                raise SeedDataError(f"Duplicate product slug {slug!r}.")
            seen_source_slugs.add(slug)
        if not isinstance(product["name"], str) or not product["name"].strip():
            raise SeedDataError(f"Product {product['id']!r} has an invalid name.")
        if not isinstance(product["quantities"], list) or not all(
            isinstance(quantity, str) for quantity in product["quantities"]
        ):
            raise SeedDataError(
                f"Product {product['id']!r} quantities must be a string array."
            )
        for field in ("category", "brand", "description", "image"):
            if not isinstance(product[field], str) or not product[field].strip():
                raise SeedDataError(
                    f"Product {product['id']!r} has an invalid {field}."
                )
        if not isinstance(product["businessType"], list) or not all(
            isinstance(value, str) for value in product["businessType"]
        ):
            raise SeedDataError(
                f"Product {product['id']!r} businessType must be a string array."
            )
        if not isinstance(product["isTrending"], bool):
            raise SeedDataError(
                f"Product {product['id']!r} isTrending must be a boolean."
            )
        _reject_floats(product, f"PRODUCTS[{position - 1}]")
        validated_products.append(product)

    return ExportData(
        products=validated_products,
        categories=categories,
        whatsapp_number=whatsapp_number,
        whatsapp_display=whatsapp_display,
    )


def parse_export_file(path: Path = EXPORT_PATH) -> ExportData:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SeedDataError(f"Cannot read product export {path}: {error}") from error
    return parse_export_text(source)


def slugify(value: str) -> str:
    slug = SLUG_SEPARATORS.sub("-", value.lower()).strip("-")
    if SLUG_PATTERN.fullmatch(slug) is None:
        raise SeedDataError(f"Cannot generate a valid slug from {value!r}.")
    return slug


def _product_id(sku: str) -> str:
    digest = hashlib.sha1(sku.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"prod_{digest[:10]}"


def _iso_utc(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)
    return now.isoformat().replace("+00:00", "Z")


def map_products(
    products: Sequence[dict[str, Any]],
    now: datetime,
    *,
    report: Callable[[str], None] | None = None,
) -> list[MappedProduct]:
    """Map validated export products to DynamoDB records with unique slugs."""
    timestamp = _iso_utc(now)
    used_slugs: set[str] = set()
    mapped: list[MappedProduct] = []
    report_message = report or (lambda message: print(message, file=sys.stderr))

    for position, source in enumerate(products, start=1):
        sku = source["id"]
        base_slug = slugify(source["name"])
        slug = base_slug
        if slug in used_slugs:
            report_message(
                f"Slug collision for {source['name']!r}; adding brand "
                f"{source['brand']!r}."
            )
            slug = slugify(f"{base_slug}-{source['brand']}")
        if slug in used_slugs:
            report_message(
                f"Slug still collides for {source['name']!r}; adding SKU {sku!r}."
            )
            slug = slugify(f"{slug}-{sku}")
        if slug in used_slugs:
            raise SeedDataError(
                f"Slug collision remains after appending brand and SKU for {sku!r}."
            )
        used_slugs.add(slug)

        record = {
            "productId": _product_id(sku),
            "sku": sku,
            "slug": slug,
            "name": source["name"],
            "brand": source["brand"],
            "category": source["category"],
            "businessType": list(source["businessType"]),
            "quantities": list(source["quantities"]),
            "description": source["description"],
            "isTrending": source["isTrending"],
            "sortRank": position * 10,
            "status": "PUBLISHED",
            "version": 1,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "createdBy": "seed",
            "updatedBy": "seed",
        }
        _reject_floats(record, f"mapped product {sku}")
        mapped.append(MappedProduct(item=record, image_url=source["image"]))
    return mapped


def build_site_config(
    categories: Sequence[str],
    whatsapp_number: str,
    whatsapp_display: str,
    offer_path: Path = OFFER_PATH,
) -> dict[str, Any]:
    offer = OFFER_DEFAULT.copy()
    if offer_path.exists():
        try:
            raw_offer = json.loads(offer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SeedDataError(
                f"Cannot read offer configuration {offer_path}: {error}"
            ) from error
        if not isinstance(raw_offer, dict):
            raise SeedDataError("Offer configuration must be a JSON object.")
        unknown_keys = set(raw_offer) - {"enabled", "text", "link"}
        if unknown_keys:
            raise SeedDataError(
                f"Offer configuration contains unsupported key(s): "
                f"{', '.join(sorted(unknown_keys))}."
            )
        offer.update(raw_offer)
    if not isinstance(offer["enabled"], bool) or not all(
        isinstance(offer[field], str) for field in ("text", "link")
    ):
        raise SeedDataError("Offer configuration has invalid enabled/text/link values.")

    mapped_categories: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for position, name in enumerate(categories, start=1):
        slug = slugify(name)
        if slug in seen_slugs:
            raise SeedDataError(f"Duplicate category slug {slug!r}.")
        seen_slugs.add(slug)
        mapped_categories.append(
            {
                "id": slug,
                "name": name,
                "slug": slug,
                "sortOrder": position * 10,
                "isActive": True,
            }
        )
    return {
        "configKey": "site",
        "offerBanner": offer,
        "categories": mapped_categories,
        "whatsapp": {
            "number": whatsapp_number,
            "display": whatsapp_display,
            "messageTemplate": PRODUCT_MESSAGE,
            "generalMessage": GENERAL_MESSAGE,
        },
    }


def download_image(url: str) -> Image.Image:
    request = Request(url, headers={"User-Agent": "KedarFoodsCatalogSeeder/1.0"})
    try:
        with urlopen(request, timeout=IMAGE_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            if not content_type.lower().startswith("image/"):
                raise SeedDataError(
                    f"Image URL returned unexpected Content-Type {content_type!r}."
                )
            image_bytes = response.read(MAX_IMAGE_BYTES + 1)
    except SeedDataError:
        raise
    except Exception as error:
        raise SeedDataError(f"Image download failed: {error}") from error
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise SeedDataError(
            f"Image exceeds the {MAX_IMAGE_BYTES}-byte download limit."
        )
    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            opened.load()
            return ImageOps.exif_transpose(opened).convert("RGB")
    except Exception as error:
        raise SeedDataError(f"Image decode failed: {type(error).__name__}.") from error


def create_image_variants(image: Image.Image) -> dict[str, ImageVariant]:
    variants: dict[str, ImageVariant] = {}
    for variant, max_width in (("card", 480), ("main", 1200)):
        width = min(max_width, image.width)
        height = max(1, round(image.height * width / image.width))
        resized = image.resize(
            (width, height),
            resample=Image.Resampling.LANCZOS,
        )
        output = io.BytesIO()
        resized.save(output, format="WEBP", quality=82)
        variants[variant] = ImageVariant(
            data=output.getvalue(),
            width=width,
            height=height,
        )
    return variants


def _planned_image_keys(product_id: str) -> dict[str, str]:
    prefix = f"media/products/{product_id}"
    return {
        "card": f"{prefix}/card-v1.webp",
        "main": f"{prefix}/main-v1.webp",
    }


def _with_planned_images(products: Sequence[MappedProduct]) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for product in products:
        item = product.item.copy()
        if product.image_url:
            item["image"] = _planned_image_keys(item["productId"])
        preview.append(item)
    return preview


def _safe_site_config(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in config.items()
        if key in {"configKey", "offerBanner", "categories", "whatsapp"}
    }


def print_dry_run(
    products: Sequence[MappedProduct],
    site_config: Mapping[str, Any],
    now: datetime,
) -> None:
    preview_items = _with_planned_images(products)
    index = build_catalog_index(preview_items, now)
    print(f"Products: {len(products)}")
    for product in products:
        item = product.item
        keys = _planned_image_keys(item["productId"]) if product.image_url else {}
        print(
            f"slug={item['slug']} sku={item['sku']} "
            f"productId={item['productId']} imageKeys={json.dumps(keys)}"
        )
    print("SiteConfig:")
    print(json.dumps(_safe_site_config(site_config), ensure_ascii=False, indent=2))
    print("Catalog index preview (first 10 lines):")
    index_lines = json.dumps(index, ensure_ascii=False, indent=2).splitlines()
    print("\n".join(index_lines[:10]))


def _stack_outputs(cloudformation: Any, stack_name: str) -> dict[str, str]:
    try:
        response = cloudformation.describe_stacks(StackName=stack_name)
    except Exception as error:
        raise SeedOperationError(
            f"Reading CloudFormation outputs for {stack_name} failed: {error}"
        ) from error
    stacks = response.get("Stacks", [])
    if not stacks:
        raise SeedOperationError(f"CloudFormation stack {stack_name!r} was not found.")
    outputs = {
        output["OutputKey"]: output["OutputValue"]
        for output in stacks[0].get("Outputs", [])
    }
    return outputs


def _required_output(outputs: Mapping[str, str], key: str, stack_name: str) -> str:
    value = outputs.get(key)
    if not value:
        raise SeedOperationError(
            f"Stack {stack_name!r} is missing required output {key!r}."
        )
    return value


def _is_conditional_failure(error: Exception) -> bool:
    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return False
    error_info = response.get("Error")
    return (
        isinstance(error_info, Mapping)
        and error_info.get("Code") == "ConditionalCheckFailedException"
    )


def conditional_put(
    table: Any,
    item: Mapping[str, Any],
    key_name: str,
    *,
    overwrite: bool,
) -> str:
    request: dict[str, Any] = {"Item": dict(item)}
    if not overwrite:
        request["ConditionExpression"] = "attribute_not_exists(#pk)"
        request["ExpressionAttributeNames"] = {"#pk": key_name}
    try:
        table.put_item(**request)
    except Exception as error:
        if not overwrite and _is_conditional_failure(error):
            return "skipped"
        raise SeedOperationError(
            f"Writing key {item.get(key_name)!r} failed: {error}"
        ) from error
    return "created"


def _write_item(
    table: Any,
    item: Mapping[str, Any],
    key_name: str,
    overwrite: bool,
    counts: WriteCounts,
) -> None:
    try:
        result = conditional_put(
            table,
            item,
            key_name,
            overwrite=overwrite,
        )
    except SeedOperationError:
        counts.failed += 1
        raise
    if result == "created":
        counts.created += 1
    else:
        counts.skipped += 1


def _object_exists(s3: Any, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except Exception as error:
        response = getattr(error, "response", None)
        error_info = response.get("Error", {}) if isinstance(response, Mapping) else {}
        code = error_info.get("Code") if isinstance(error_info, Mapping) else None
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise SeedOperationError(
            f"Checking S3 object s3://{bucket}/{key} failed: {error}"
        ) from error
    return True


def upload_image_variants(
    s3: Any,
    bucket: str,
    product_id: str,
    variants: Mapping[str, ImageVariant],
    *,
    overwrite: bool,
) -> dict[str, str]:
    keys = _planned_image_keys(product_id)
    for variant_name, variant in variants.items():
        key = keys[variant_name]
        if not overwrite and _object_exists(s3, bucket, key):
            continue
        try:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=variant.data,
                ContentType="image/webp",
                CacheControl="public, max-age=31536000, immutable",
            )
        except Exception as error:
            raise SeedOperationError(
                f"Uploading s3://{bucket}/{key} failed: {error}"
            ) from error
    return keys


def _upload_catalog_index(s3: Any, bucket: str, index: Mapping[str, Any]) -> None:
    try:
        s3.put_object(
            Bucket=bucket,
            Key="data/catalog-index.json",
            Body=json.dumps(index, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            ),
            ContentType="application/json",
            CacheControl="public, max-age=60",
        )
    except Exception as error:
        raise SeedOperationError(
            f"Uploading s3://{bucket}/data/catalog-index.json failed: {error}"
        ) from error


def _scan_all_products(table: Any, table_name: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    request: dict[str, Any] = {}
    while True:
        try:
            response = table.scan(**request)
        except Exception as error:
            raise SeedOperationError(
                f"Scanning Products table {table_name!r} failed: {error}"
            ) from error
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        request["ExclusiveStartKey"] = last_key


def rebuild_and_upload_index(
    products_table: Any,
    s3: Any,
    table_name: str,
    bucket: str,
    now: datetime,
) -> dict[str, Any]:
    products = _scan_all_products(products_table, table_name)
    index = build_catalog_index(products, now)
    _upload_catalog_index(s3, bucket, index)
    return index


def _upload_seed_images(
    products: Sequence[MappedProduct],
    s3: Any,
    bucket: str,
    *,
    overwrite: bool,
) -> None:
    for product in products:
        try:
            image = download_image(product.image_url)
            variants = create_image_variants(image)
            keys = upload_image_variants(
                s3,
                bucket,
                product.item["productId"],
                variants,
                overwrite=overwrite,
            )
        except SeedDataError as error:
            print(
                f"WARNING: image for SKU {product.item['sku']} was omitted: {error}",
                file=sys.stderr,
            )
            continue
        product.item["image"] = keys


def _load_aws_clients(
    env_name: str,
) -> tuple[str, str, str, str, Any, Any, Any]:
    try:
        import boto3

        session = boto3.Session(region_name=REGION)
        sts = session.client("sts")
        account_id = cast(str, sts.get_caller_identity()["Account"])
        cloudformation = session.client("cloudformation")
        backend_stack = f"kedar-foods-app-{env_name}-backend"
        frontend_stack = f"kedar-foods-app-{env_name}-frontend"
        backend_outputs = _stack_outputs(cloudformation, backend_stack)
        frontend_outputs = _stack_outputs(cloudformation, frontend_stack)
        products_table = _required_output(
            backend_outputs,
            "ProductsTableName",
            backend_stack,
        )
        site_config_table = _required_output(
            backend_outputs,
            "SiteConfigTableName",
            backend_stack,
        )
        bucket = _required_output(
            frontend_outputs,
            "DataMediaBucketName",
            frontend_stack,
        )
        dynamodb = session.resource("dynamodb")
        products_table_resource = dynamodb.Table(products_table)
        site_config_table_resource = dynamodb.Table(site_config_table)
        s3 = session.client("s3")
    except SeedOperationError:
        raise
    except Exception as error:
        raise SeedOperationError(
            f"Preparing AWS clients/outputs failed: {error}"
        ) from error
    return (
        account_id,
        products_table,
        site_config_table,
        bucket,
        products_table_resource,
        site_config_table_resource,
        s3,
    )


def _write_records(
    products: Sequence[MappedProduct],
    site_config: Mapping[str, Any],
    products_table: Any,
    site_config_table: Any,
    *,
    overwrite: bool,
) -> WriteCounts:
    counts = WriteCounts()
    try:
        for product in products:
            _write_item(
                products_table,
                product.item,
                "productId",
                overwrite,
                counts,
            )
        _write_item(
            site_config_table,
            site_config,
            "configKey",
            overwrite,
            counts,
        )
    except SeedOperationError:
        print(
            f"Write counts before failure: created={counts.created}, "
            f"skipped={counts.skipped}, failed={counts.failed}",
            file=sys.stderr,
        )
        raise
    print(
        f"Write counts: created={counts.created}, skipped={counts.skipped}, "
        f"failed={counts.failed}"
    )
    return counts


def _confirm_operation(
    account_id: str,
    products_table: str,
    site_config_table: str,
    bucket: str,
) -> bool:
    print(f"AWS account: {account_id}")
    print(f"Region: {REGION}")
    print(f"Products table: {products_table}")
    print(f"SiteConfig table: {site_config_table}")
    print(f"Data/media bucket: {bucket}")
    return input('Type "yes" to continue: ').strip() == "yes"


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=("prod", "dev"), default="prod")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check-images", action="store_true")
    parser.add_argument("--rebuild-index", action="store_true")
    return parser


def _check_images(products: Sequence[MappedProduct]) -> None:
    for product in products:
        try:
            image = download_image(product.image_url)
            variants = create_image_variants(image)
        except SeedDataError as error:
            print(
                f"WARNING: image check failed for SKU {product.item['sku']}: {error}",
                file=sys.stderr,
            )
            continue
        for name, variant in variants.items():
            print(
                f"Image check {product.item['sku']} {name}: "
                f"{variant.width}x{variant.height}, {len(variant.data)} bytes"
            )


def run(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.apply and args.check_images:
        raise SeedDataError("--check-images cannot be combined with --apply.")
    if args.overwrite and not args.apply:
        raise SeedDataError("--overwrite requires --apply.")

    now = datetime.now(UTC)
    products: list[MappedProduct] = []
    site_config: dict[str, Any] = {}
    if args.apply or not args.rebuild_index:
        export_data = parse_export_file()
        products = map_products(export_data.products, now)
        site_config = build_site_config(
            export_data.categories,
            export_data.whatsapp_number,
            export_data.whatsapp_display,
        )

    if not args.apply and not args.rebuild_index:
        print_dry_run(products, site_config, now)
        if args.check_images:
            _check_images(products)
        return 0

    (
        account_id,
        products_table_name,
        site_config_table_name,
        bucket,
        products_table,
        site_config_table,
        s3,
    ) = _load_aws_clients(args.env)
    if not _confirm_operation(
        account_id,
        products_table_name,
        site_config_table_name,
        bucket,
    ):
        print("Cancelled; no seed writes or uploads were made.")
        return 0

    if args.apply:
        _upload_seed_images(
            products,
            s3,
            bucket,
            overwrite=args.overwrite,
        )
        _write_records(
            products,
            site_config,
            products_table,
            site_config_table,
            overwrite=args.overwrite,
        )

    index = rebuild_and_upload_index(
        products_table,
        s3,
        products_table_name,
        bucket,
        datetime.now(UTC),
    )
    print(f"Uploaded catalog index with {len(index['items'])} published products.")
    return 0


def main() -> int:
    try:
        return run()
    except (SeedDataError, SeedOperationError) as error:
        print(f"Seed failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
