"""Shared in-memory fakes for the admin handler tests."""

from __future__ import annotations

import copy
import re
from typing import Any


class FakeConditionError(Exception):
    def __init__(self) -> None:
        super().__init__("conditional check failed")
        self.response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeProductsTable:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.items = {item["productId"]: copy.deepcopy(item) for item in items or []}
        self.page_size = 1000

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        item = self.items.get(kwargs["Key"]["productId"])
        return {"Item": copy.deepcopy(item)} if item else {}

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        item = kwargs["Item"]
        if (
            "attribute_not_exists(productId)" in kwargs.get("ConditionExpression", "")
            and item["productId"] in self.items
        ):
            raise FakeConditionError
        self.items[item["productId"]] = copy.deepcopy(item)
        return {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        item = self.items.get(kwargs["Key"]["productId"])
        values = kwargs["ExpressionAttributeValues"]
        names = kwargs.get("ExpressionAttributeNames", {})
        condition = kwargs["ConditionExpression"]
        if item is None:
            raise FakeConditionError
        if ":expected" in values and item.get("version") != values[":expected"]:
            raise FakeConditionError
        assert condition.startswith("attribute_exists(productId)")
        expression = kwargs["UpdateExpression"].removeprefix("SET ")
        for part in expression.split(", "):
            target, source = (side.strip() for side in part.split(" = "))
            field = names.get(target, target)
            match = re.fullmatch(r"(\w+) \+ (:\w+)", source)
            if match:
                item[field] = item[match.group(1)] + values[match.group(2)]
            else:
                item[field] = copy.deepcopy(values[source])
        return {"Attributes": copy.deepcopy(item)}

    def query(self, **kwargs: Any) -> dict[str, Any]:
        slug = kwargs["ExpressionAttributeValues"][":slug"]
        found = [i for i in self.items.values() if i.get("slug") == slug]
        return {"Items": copy.deepcopy(found)}

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        everything = [copy.deepcopy(i) for i in self.items.values()]
        start = int(kwargs.get("ExclusiveStartKey", {}).get("offset", 0))
        page = everything[start : start + self.page_size]
        result: dict[str, Any] = {"Items": page}
        if start + self.page_size < len(everything):
            result["LastEvaluatedKey"] = {"offset": start + self.page_size}
        return result


class FakeSiteConfigTable:
    def __init__(self, item: dict[str, Any] | None) -> None:
        self.item = copy.deepcopy(item)
        self.fail_reads = False

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        if self.fail_reads:
            raise RuntimeError("boom")
        return {"Item": copy.deepcopy(self.item)} if self.item else {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        if self.item is None:
            raise FakeConditionError
        self.item["offerBanner"] = kwargs["ExpressionAttributeValues"][":offer"]
        return {}


class FakeS3:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("s3 down")
        self.calls.append(kwargs)
        return {}


class FakeSsm:
    def __init__(self, value: str | None = "k" * 40, *, fail: bool = False) -> None:
        self.value = value
        self.fail = fail
        self.calls = 0

    def get_parameter(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["WithDecryption"] is True
        self.calls += 1
        if self.fail:
            raise RuntimeError("ssm down")
        return {"Parameter": {"Value": self.value}}


SITE_CONFIG = {
    "configKey": "site",
    "offerBanner": {"enabled": False, "text": "", "link": ""},
    "categories": [
        {"name": "Dairy", "isActive": True},
        {"name": "Chocolate", "isActive": True},
        {"name": "Retired", "isActive": False},
    ],
}
