# Current Product Model and Catalogue Behavior

This document describes the product data and customer catalogue as implemented
today. The API fields below are the planned Phase 1 contract, not fields that
already exist in the mock product objects or app.

## Existing mock product objects

The canonical mock records are the 11 objects in `app/lib/data.js` under
`PRODUCTS`. Every current record has these fields:

| Field | Type | Example |
| --- | --- | --- |
| `id` | string | `"KF-01"` |
| `name` | string | `"Amul Unsalted Butter"` |
| `quantities` | string array | `["100g", "500g", "1 kg", "5 kg"]` |
| `category` | string | `"Dairy"` |
| `brand` | string | `"Amul"` |
| `businessType` | string array | `["Bakery", "Cafe", "Restaurant"]` |
| `description` | string | `"Creamy unsalted table butter — a baking and spread essential."` |
| `image` | string | `"https://images.unsplash.com/photo-1719148162837-63d2f256231f?..."`
| `isTrending` | boolean | `true` |

The existing canonical records do not have a `slug`, `modelId`,
`shortDescription`, `specifications`, `variants`, `customizationOptions`,
`imageKeys`, `status`, or `sortRank` field. The temporary
`spike-data/products.json` fixture adds a `slug` for the routing prototype; that
does not make it part of the canonical mock model.

`getQuantities()` also has a compatibility fallback for records with `quantity`
and `unit` properties. Those properties are not present on the current
`PRODUCTS` records.

## Categories and brands

The fixed category options exposed by the current admin category dropdown are:

- Dairy
- Baking Essentials
- Chocolate
- Beverages
- Flavours
- Frozen Items

The current product data uses five of those categories: Dairy, Baking
Essentials, Chocolate, Flavours, and Frozen Items. No current product is
assigned to Beverages.

The current product records contain these six brands:

- Amul
- Callebaut
- Del Monte
- Milk Mist
- Puratos
- Tropilite

`TOP_BRANDS` contains the same six brands, in a separate fixed order for the
homepage banner. The catalogue brand filter derives and sorts its choices from
the current product records.

## Catalogue filters, search, sorting, and pagination

The current catalogue is implemented in `app/catalogue/page.js`.

- **Business Type:** Bakery, Cafe, Restaurant. A product matches if any of its
  `businessType` values is selected.
- **Brand:** choices are derived from current products. A product matches if
  its `brand` is selected.
- **Category:** choices are derived from current products. A product matches
  if its `category` is selected.
- **Combining filters:** selected values within one filter group are ORed;
  active groups are combined with AND. With no selected values in a group,
  that group does not restrict results.
- **Search:** trims surrounding whitespace and performs case-insensitive
  substring matching against `name`, `brand`, or `category`. The search match
  is combined with the selected filters using AND. It does not currently
  search `description`, `quantities`, or `businessType`.
- **Sort:** no sort control or explicit sorting is implemented. Products remain
  in their current source/store order.
- **Pagination / load more:** none is implemented. All matching products are
  rendered; the grid currently uses responsive CSS columns.

## WhatsApp message

`buildWaLink(product, qty)` in `app/lib/data.js` builds:

```text
Hi Kedar Foods! I am interested in bulk rates for {product.name}{optional pack text} (SKU: {product.id})?
```

When `qty` is truthy, the optional pack text is:

```text
 - Selected Pack Size: {qty}
```

The message is URL-encoded and appended as the `text` query parameter to
`https://wa.me/{WHATSAPP_NUMBER}`. Catalogue cards and the current detail shell
pass the first available quantity (if any); the homepage hero enquiry does not
pass a quantity.

## Planned catalog index fields

The Phase 1 catalog index is a planned compact public listing representation,
not the current mock product shape. Its planned item fields are:

| Field | Purpose |
| --- | --- |
| `id` | Product identifier |
| `slug` | Clean product URL identifier |
| `name` | Product display/search name |
| `modelId` | Product model identifier |
| `category` | Category filter |
| `thumbnailKey` | Public catalog-card image key |
| `searchText` | Searchable text prepared for client-side filtering |
| `filterAttributes` | Attribute values used by client-side filters |
| `isFeatured` | Featured-product flag |
| `sortRank` | Listing order value |

The index envelope also has `version` and `items`. The plan specifies that
unpublished/draft/archived products and internal/admin-only fields are not
included. These fields do not currently exist on the canonical mock objects
under the same names.

## Planned product detail API fields

The planned `GET /products/{slug}` response is an explicit public allowlist,
not the current localStorage object. The planned fields are:

- `id`
- `slug`
- `name`
- `modelId`
- `shortDescription`
- `description`
- `category`
- `specifications`
- `variants`
- `customizationOptions`
- final public image keys
- `updatedAt` if needed

These API fields are planned only. The current canonical mock objects do not
currently provide most of them; in particular, they have no product slug,
model ID, specifications, variants, customization options, or `updatedAt`.
