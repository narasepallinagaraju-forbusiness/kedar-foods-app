"""Lazy DynamoDB resource factories used by the Lambda handlers."""

from __future__ import annotations

import os
from importlib import import_module
from typing import Any, Protocol, cast

_TABLE_CACHE: dict[str, object] = {}


class ProductsTable(Protocol):
    def query(self, **kwargs: Any) -> dict[str, Any]: ...


class SiteConfigTable(Protocol):
    def get_item(self, **kwargs: Any) -> dict[str, Any]: ...


class AdminProductsTable(Protocol):
    def get_item(self, **kwargs: Any) -> dict[str, Any]: ...
    def put_item(self, **kwargs: Any) -> dict[str, Any]: ...
    def update_item(self, **kwargs: Any) -> dict[str, Any]: ...
    def query(self, **kwargs: Any) -> dict[str, Any]: ...
    def scan(self, **kwargs: Any) -> dict[str, Any]: ...


class AdminSiteConfigTable(Protocol):
    def get_item(self, **kwargs: Any) -> dict[str, Any]: ...
    def update_item(self, **kwargs: Any) -> dict[str, Any]: ...


class S3Writer(Protocol):
    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...


class ParameterReader(Protocol):
    def get_parameter(self, **kwargs: Any) -> dict[str, Any]: ...


def _get_table(table_name: str) -> object:
    table = _TABLE_CACHE.get(table_name)
    if table is None:
        boto3 = import_module("boto3")
        table = boto3.resource("dynamodb").Table(table_name)
        _TABLE_CACHE[table_name] = table
    return table


def clear_table_cache() -> None:
    _TABLE_CACHE.clear()


def create_products_table() -> ProductsTable:
    table_name = os.environ["PRODUCTS_TABLE_NAME"]
    return cast(ProductsTable, _get_table(table_name))


def create_site_config_table() -> SiteConfigTable:
    table_name = os.environ["SITE_CONFIG_TABLE_NAME"]
    return cast(SiteConfigTable, _get_table(table_name))


def create_admin_products_table() -> AdminProductsTable:
    table_name = os.environ["PRODUCTS_TABLE_NAME"]
    return cast(AdminProductsTable, _get_table(table_name))


def create_admin_site_config_table() -> AdminSiteConfigTable:
    table_name = os.environ["SITE_CONFIG_TABLE_NAME"]
    return cast(AdminSiteConfigTable, _get_table(table_name))


def create_s3_client() -> S3Writer:
    boto3 = import_module("boto3")
    return cast(S3Writer, boto3.client("s3"))


def create_ssm_client() -> ParameterReader:
    boto3 = import_module("boto3")
    return cast(ParameterReader, boto3.client("ssm"))


def slug_key_condition(slug: str) -> object:
    conditions = import_module("boto3.dynamodb.conditions")
    return conditions.Key("slug").eq(slug)
