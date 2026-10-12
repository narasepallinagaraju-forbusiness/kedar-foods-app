
#python .\utils\change_category.py "Flavours" "Baking Essentials" --apply

import sys
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr

TABLE = "kedar-foods-app-prod-products"

if len(sys.argv) < 3:
    sys.exit('Usage: python change_category.py "Old Category" "New Category" [--apply]')
old, new = sys.argv[1], sys.argv[2]
apply = "--apply" in sys.argv[3:]

table = boto3.resource("dynamodb", region_name="ap-south-1").Table(TABLE)

items, kwargs = [], {"FilterExpression": Attr("category").eq(old)}
while True:
    page = table.scan(**kwargs)
    items.extend(page["Items"])
    if "LastEvaluatedKey" not in page:
        break
    kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

for item in items:
    print(item["productId"], "|", item.get("name"))
print(f"{len(items)} product(s) with category '{old}' -> '{new}'")
if not apply:
    sys.exit("Dry run only. Add --apply to write.")

now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
for item in items:
    table.update_item(
        Key={"productId": item["productId"]},
        UpdateExpression="SET category = :new, updatedAt = :now, version = version + :one",
        ConditionExpression="category = :old",
        ExpressionAttributeValues={":new": new, ":old": old, ":now": now, ":one": 1},
    )
print("Updated.")