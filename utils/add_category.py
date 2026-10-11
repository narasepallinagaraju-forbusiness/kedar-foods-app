
#use example
#python .\add_category.py "Whole Spices" --apply

import re, sys
import boto3

TABLE = "kedar-foods-app-prod-site-config"
name = sys.argv[1].strip()
apply = "--apply" in sys.argv[2:]

slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
if not name or not slug:
    sys.exit("Category name is empty.")

table = boto3.resource("dynamodb", region_name="ap-south-1").Table(TABLE)
item = table.get_item(Key={"configKey": "site"}).get("Item")
if not item:
    sys.exit("Site config item not found.")

categories = item.get("categories", [])
if any(c.get("id") == slug or str(c.get("name", "")).lower() == name.lower() for c in categories):
    sys.exit(f"Category already exists: {name}")

sort_order = int(max((c.get("sortOrder", 0) for c in categories), default=0)) + 10
new_category = {"id": slug, "name": name, "slug": slug, "sortOrder": sort_order, "isActive": True}
print("Will add:", new_category)
if not apply:
    sys.exit("Dry run only. Add --apply to write.")

table.update_item(
    Key={"configKey": "site"},
    UpdateExpression="SET categories = list_append(categories, :new)",
    ConditionExpression="size(categories) = :count",
    ExpressionAttributeValues={":new": [new_category], ":count": len(categories)},
)
print("Added.")
