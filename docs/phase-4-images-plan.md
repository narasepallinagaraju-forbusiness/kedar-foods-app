# Phase 4: Images, offer schedule, admin search and bulk import (IN PROGRESS)

Status: APPROVED, being built. Steps A–E built; deploy 1 (backend + site) done.
Follows `docs/phase-3-admin-product-crud-plan.md` (section 19, items B and C,
which were deferred to this phase) and `PROJECT_PLAN.md` section 11.

## Build log and deviations (read this first; later sections may be stale)

- **Upload design changed to "option A" (owner chose it).** The browser resizes the
  picture to small WebP and sends it as base64 JSON straight to our API
  (`PUT /admin/products/{id}/images/{slot}`, `POST .../remove`, `PUT /admin/site-config/offer/image`,
  `POST .../offer/image/remove`). The server checks the real bytes and stores them.
  So sections 5, 6, 8, 13 and 17 that mention presign/confirm, S3 CORS, `siteOrigin`
  or a CSP change are **not used**. The frontend stack was not changed. The
  `incoming/` lifecycle rule is unused but harmless. A separate `AdminImagesFunction`
  holds S3 write rights only for `media/products/*`, `media/offer/*` and the index.
- **Post-deploy fixes (owner testing, deploy 1):**
  1. Admin picture box: the uploaded thumbnail was huge and pushed the buttons out of
     the popup. Fixed: 64 px thumbnail, buttons beside it. Cause: `app/globals.css` is a
     pre-built Tailwind file, so classes it does not contain (e.g. `h-16`, `max-h-56`)
     do nothing. **Rule: for new UI use inline `style` sizes or classes already in
     `globals.css`.**
  2. Offer popup: owner later asked for the poster in the popup too, above the offer
     text. Done (popup and home banner both show it).
  3. Product page gallery: a product with several pictures shows thumbnails under the
     main picture; clicking one switches the main picture; the strip scrolls sideways
     if needed; thumbnails load lazily (done early, ahead of step H).
- **Step G (CSV import) done and deployed (deploy 2), owner-verified.**
  `POST /admin/products/import` (max 50 rows per batch, 1 request/s, burst 2, on the
  products Lambda). The browser parses and validates the CSV (max 500 rows / 1 MB),
  shows a preview, then sends batches of 50. Blank status = PUBLISHED (live). Existing
  SKUs are skipped, never overwritten. One index rebuild per batch. Step H (gallery) was
  verified by the owner. Remaining: I (wrap-up, commit and tag `phase-4` only after
  owner approval). Git tag `pre-phase-4` exists.

## 0. Owner decisions (answers to the first draft)

1. Picture source: the admin chooses ONE method per picture: upload a file (or
   camera) OR paste a URL. Never both at once. The form shows two tabs and the
   unused one is disabled.
2. The customer home page banner may show the offer poster (customer code change
   approved).
3. Offer start/end schedule: do it now if easy. It is easy (small), so it is IN.
4. Gallery: up to 3 pictures per product, kept light for site performance. IN, but
   built last in this phase (see cut line in section 11).
5. "Rebuild public list" button: NOT now. Tracked in `docs/future-enhancements.md`.
6. New requests:
   a. Search box on the admin product list (name, SKU, brand). Small, IN.
   b. Bulk import of products from a CSV file. Medium, IN. Sample file:
      `docs/sample-products-import.csv`.
7. Budget note: about 750 credits left. Work is ordered so the most valuable parts
   come first and the phase can stop cleanly at any cut line without leaving
   half-built features. Quality and tests stay the same as before.

## Effort at a glance

| Item | Size | Touches |
|---|---|---|
| Admin search box | Small | admin dashboard only |
| Offer schedule (start/end dates) | Small | validation, public site-config, admin offer form |
| Single product picture + offer poster upload | Large (core) | backend, CDK, S3 CORS, admin, customer banner |
| Bulk CSV import | Medium | one backend route, admin import dialog |
| Gallery up to 3 pictures | Medium | data field, upload slots, customer product page |

Recommendation: do search, schedule and the core picture upload first, then CSV
import, then gallery last. If credits get tight, gallery moves to a next phase
and nothing else is affected, because the upload engine is built slot-based
(slot 1 = main picture, slots 2 and 3 = gallery) from the start.

## 1. Goal

From the admin dashboard the owner can:
1. Add or change product pictures (up to 3 per product): per picture, either
   upload a file / take a photo, or paste a URL (one method only).
2. Add or change an offer banner poster picture, and set an optional start and end
   date for the offer.
3. Remove any picture (the site then shows the neutral placeholder).
4. Search the product list by name, SKU or brand.
5. Import many products at once from a CSV file.

Customers see new pictures after a normal page reload, with no hard refresh.

## 2. Decisions already made by the owner

- Images were deferred from Phase 3 to this phase.
- Cache problem was fixed in Phase 3 (catalog, product and site-config responses
  use `max-age=0, must-revalidate`).
- Admin protection is still the shared admin key (Cognito comes later).
- See section 0 for the answers to the first draft.

## 3. Scope

In scope:
- Admin image upload for products (max 3) and for the offer poster.
- Resizing in the browser, secure direct upload to S3, server-side confirmation.
- Admin form changes (preview, replace, remove), customer offer banner showing the
  poster, customer product page showing up to 3 pictures.
- Offer schedule, admin search, CSV bulk import (sections 6a to 6c).
- Backend routes, IAM, tests, docs, manual checklist.

Out of scope (later, see `docs/future-enhancements.md`):
- "Rebuild public list" dashboard button.
- Cognito login, custom domain, CSP enforcement.
- Automatic deletion of old picture versions.
- Server-side image processing Lambda.
- Importing pictures through the CSV (pictures are added afterwards, one product
  at a time).

## 4. What already exists (verified in the repo)

- Media/data bucket `kedar-foods-app-prod-data-media`, private, SSL enforced,
  RETAIN. Already has a lifecycle rule: `incoming/` expires after 7 days.
- The frontend stack already creates an S3 CORS rule (POST, exact origin) only when
  the `siteOrigin` CDK context value is set. It is not set today, so no CORS rule
  exists on the bucket now.
- CloudFront serves `/media/*` (one-year cache, OAC) and `/data/*`. `incoming/` is
  never routed by CloudFront.
- Product `image` field shape: `{card, main}` = keys like
  `media/products/{productId}/card-v1.webp`. The catalog index uses
  `image.card` as `thumbnailKey`. The seed script uses the same layout.
- Customer pages already show a placeholder when a product has no image.
- Admin update (`PUT /admin/products/{id}`) deliberately rejects `image` today.

## 5. Upload flow (follows PROJECT_PLAN section 11)

1. Admin picks a file, takes a photo, or pastes a URL.
2. Browser checks: JPEG, PNG or WebP only (no SVG, no GIF), source size at most
   10 MB, at most 8000 px on the long side.
3. Browser resizes and converts to WebP with a canvas:
   - Product: `card` about 480 px wide, `main` about 1200 px wide.
   - Offer poster: one `poster` about 1200 px wide.
   - Target size under 300 KB each (quality about 0.82, lowered if needed).
4. Browser calls `POST /admin/uploads/presign` with the target (product id or
   offer) and the files it will send (type and size).
5. Lambda generates object keys itself (client never chooses a key) and returns a
   presigned POST per file: key `incoming/{target}/{uploadId}/{name}`, content type
   fixed to `image/webp`, size range limited (1 KB to 600 KB), expiry 5 minutes.
6. Browser uploads each file straight to S3 using the presigned POST.
7. Browser calls `POST /admin/uploads/confirm` with the upload id.
8. Lambda checks the objects exist in `incoming/`, are `image/webp` and within the
   size limit, and that the upload id belongs to that product/offer. It copies them to
   final versioned keys and returns the keys:
   - `media/products/{productId}/card-v{n}.webp` and `main-v{n}.webp`
   - `media/offer/poster-v{n}.webp`
   `n` is the next free version number (never overwrites a cached picture).
9. The same confirm call saves the keys to the product (with the `version` check)
   or to the offer, then rebuilds the catalog index.

If a step fails the old picture stays. Partial uploads sit in `incoming/` and
expire after 7 days.

## 6. API additions (admin key required on all, same checks as Phase 3)

| Route | Purpose |
|---|---|
| `POST /admin/uploads/presign` | validate request, return presigned POSTs |
| `POST /admin/uploads/confirm` | verify, copy to final key, save to product slot or offer, rebuild index |
| `POST /admin/products/{id}/image/remove` | clear one picture slot (1 to 3); no deletes anywhere |
| `POST /admin/site-config/offer/poster/remove` | clear offer poster |
| `POST /admin/products/import` | bulk create from CSV rows (section 6c) |

Rules:
- Upload ids are random (128-bit), single use, bound to the target and slot.
- Presign and confirm are throttled lower than other admin routes (about 2 per
  second, burst 5).
- Confirm for a product requires the request `version` to match, same as edit
  (409 `version_conflict` otherwise). Removing a picture does the same.
- Errors use the existing messages style; image problems map to clear texts
  (too large, wrong type, upload expired, upload not found).
- Old picture objects are kept (not deleted); only the reference changes.

## 6a. Admin search (small)

- A search box above the product table filters in the browser on name, SKU and
  brand (case-insensitive, ignores extra spaces), as you type. The list is already
  fully loaded for admin, so no backend change.
- Shows "N of M products" and a "No products match" message; a clear (x) button.
- Works together with the existing list; the filter resets when you leave the page.
- Unit-tested filter helper (`filterProducts`).

## 6b. Offer schedule (small)

- Offer form gets optional "Start date" and "End date" (date only, India time).
- Stored on `offerBanner` as `startDate` / `endDate` (`YYYY-MM-DD`). Validation:
  both optional, end not before start, valid calendar dates.
- The public `GET /site-config` returns the banner only when it is enabled AND today
  (IST) is inside the window; the admin `GET /admin/site-config` always returns
  everything plus a computed label (Scheduled / Live / Ended / Off).
- No new Lambda or route. Takes effect on a normal reload because of the existing
  `must-revalidate` header.
- Tests: validation, date edges (start day, end day, end before start), public
  filtering with a fixed clock.

## 6c. Bulk CSV import (medium)

Sample: `docs/sample-products-import.csv`.

Columns (header row required, UTF-8, comma separated, quote values that contain
commas):

| Column | Required | Rules |
|---|---|---|
| `sku` | yes | 2 to 30 chars, A-Z, 0-9, hyphen (same as the form); must be unique |
| `name` | yes | 2 to 120 chars |
| `brand` | yes | 1 to 60 chars |
| `category` | yes | exact match of an active category: Dairy, Baking Essentials, Chocolate, Beverages, Flavours, Frozen Items |
| `businessType` | yes | one or more of Bakery, Cafe, Restaurant, separated by `|` |
| `quantities` | yes | 1 to 12 pack sizes, separated by `|`, each 1 to 20 chars |
| `description` | no | up to 2000 chars |
| `isTrending` | no | `true` or `false` (default false) |
| `sortRank` | no | whole number 0 to 100000 (default 0) |
| `status` | no | `PUBLISHED` (live, default) or `ARCHIVED` (hidden) |

Flow:
1. Admin presses "Import products", picks the CSV (max 500 rows, 1 MB).
2. The browser parses and checks every row with the same rules as the form and
   shows a preview table with a clear error per bad row. Nothing is sent yet.
3. Admin fixes the file and re-selects it, or presses "Import N valid rows".
   Rows are sent in batches of 50 to `POST /admin/products/import`.
4. The server re-validates every row (never trusts the browser), creates products
   with the same conditional write as the single create (duplicate SKU or slug
   handled the same way), skips duplicates and reports them, then rebuilds the
   catalog index once per batch (not once per product).
5. The result shows: created, skipped (already exists), failed with reasons.
   Re-running the same file is safe: existing SKUs are skipped, not overwritten.

Notes:
- Owner decision: imported products go LIVE by default (blank status = PUBLISHED).
  Use `status=ARCHIVED` for rows that should stay hidden. The preview warns that
  rows will go live.
- Pictures are not part of the CSV; add them per product afterwards.
- Import never edits or deletes existing products.
- Excel tip: save as "CSV UTF-8". The sample file opens in Excel as is.
- Throttle for the import route: 1 per second, burst 2. Request size limit stays
  64 KB, so batches of up to 50 rows fit (descriptions are capped at 2000 chars).
  Batch size will be tuned in testing if needed.
- Tests: valid/invalid rows, duplicate SKU in file and in database, unknown
  category, bad boolean, `|` lists, batch limit, one index rebuild per batch.

## 7. Data changes

- Products: `image = {card, main}` stays as the primary picture (slot 1), so the
  catalog index, cards and seed script keep working. New optional `gallery`: a list
  of up to 2 more `{card, main}` entries (slots 2 and 3). Removal clears a slot;
  clearing slot 1 promotes nothing (the admin reorders by re-uploading). `version`
  and `updatedAt` change as for any edit.
- SiteConfig `offerBanner`: add optional `image` (`media/offer/poster-vN.webp`),
  `startDate`, `endDate`. The public response includes `image` only when set; the
  key must start with `media/offer/` (validated server-side).
- Catalog index: `thumbnailKey` follows `image.card` as before. Gallery pictures
  are NOT put in the index (keeps the catalog small and fast); they are only in the
  per-product API response.
- No new tables.

## 8. Infrastructure changes

Backend stack (`infra/backend_stack.py`), products and site-config Lambdas get a
new upload handler (one extra Lambda, `AdminUploadsFunction`):
- `s3:PutObject` on `incoming/*` (needed to sign presigned POSTs).
- `s3:GetObject` on `incoming/*` (read for verify and copy).
- `s3:PutObject` on `media/products/*` and `media/offer/*` (copy target).
- `s3:GetObject`/`s3:ListBucket` limited to `media/products/*` and
  `media/offer/*` for finding the next version number (ListBucket with a prefix
  condition).
- DynamoDB: same Products/SiteConfig actions as the existing admin Lambdas,
  scoped to the two tables. No delete. No wildcard resources.
- Env vars: `DATA_BUCKET_NAME`, `ADMIN_KEY_PARAMETER`.

Frontend stack (`infra/frontend_stack.py`):
- Deploy with `-c siteOrigin=https://d1sq3xexjsq6iz.cloudfront.net` so the existing
  CORS rule (POST from that exact https origin, never a wildcard) is created. Needs
  the owner's approval, because it changes the live bucket. When the custom domain
  is added later, `siteOrigin` is updated.
- CSP is report-only. Add the regional S3 endpoint to `connect-src` and `img-src`
  so browsers do not report violations. Confirm the exact policy before editing.
- The "do not touch the frontend stack" rule from Phase 3 is lifted for these two
  items only.

## 9. Frontend changes

Admin (`app/admin/dashboard/page.js`, `app/lib/admin-api/*`):
- New picture panel inside the product modal: current picture preview, buttons
  "Choose file", "Take photo" (`capture="environment"`), "Paste URL" (optional),
  "Remove picture". Picture changes apply on its own button ("Save picture"),
  separate from "Save product", so a failed upload never loses typed text.
- New products: the owner must save the product first, then add the picture
  (the product id is needed). The form says so.
- Offer section: poster panel with the same actions.
- Progress and error messages in plain words; the preview shows before saving.
- Image helper module (`image-prepare.mjs`): type check, size check, canvas resize,
  WebP encode. Pure parts unit-tested; canvas parts kept thin.
- Source choice per picture: two tabs, "Upload / camera" or "Image URL". Choosing
  one disables the other; switching clears the pending choice. Only one source is
  ever used for a picture.
- URL option: the browser downloads the image and, if the other site allows it
  (CORS), resizes it and uploads as usual. The server never fetches a URL (avoids
  server-side request forgery). If the site blocks it the admin sees "download
  the picture and upload the file instead".
- Three picture slots in the product modal (slot 1 is the main picture shown on
  cards). Each slot has its own preview, source tabs and Remove button.
- Search box and the "Import products" button (with preview table and result
  summary) are added to the dashboard header area.

Customer (owner approved these exceptions to "customer pages untouched"):
- `app/page.js`: show the poster in the offer banner when `offerBanner.image`
  is set; text and link keep working; banner stays hidden when disabled or
  outside its dates.
- Product page (`scripts/product-shell.js`): main picture plus up to 2 small
  thumbnails that switch the main picture. Thumbnails use `loading="lazy"` and the
  small `card` size; only the selected picture loads its `main` size.
- Product cards and the catalog need no change (they read `thumbnailKey`).

## 10. Tests

Python (pytest, in-memory fakes, no AWS):
- Presign: rejects unknown target, bad type, too large, missing/invalid key, bad
  slot; returned keys are server-made; expiry and size limits in the signed policy.
- Confirm: missing object, wrong content type, oversize, wrong owner/upload id,
  reused upload id, version conflict, next-version numbering, copy keys, index
  rebuilt, offer key prefix check, slot rules (max 3).
- Removal: product slots and offer, version conflict.
- Offer schedule and public site-config filtering (6b); bulk import (6c).
- Public site-config includes `image` only when valid.
- CDK tests: new Lambda, new routes, throttling, IAM statements scoped to the
  exact prefixes (no `*` resources, no delete), CORS rule only with `siteOrigin`,
  exact origin and no wildcard.
JavaScript:
- Image prepare helper (type and size checks, dimension math, quality loop),
  request builders, error message mapping, `filterProducts`, CSV parser and row
  validation.
Existing checks stay green: ruff, mypy, pytest, `npm run lint`, `test:admin-logic`,
`test:customer-logic`, `test:routing`.

## 11. Implementation order (small steps, show diff after each, no commits until approved)

Most valuable first. Each lettered step ends with passing checks. Cut lines (CL)
mark where the phase can stop cleanly if credits get tight.

A. Admin search (6a) and offer schedule (6b), with tests. No AWS change needed
   until deploy.
B. Single-picture upload backend (presign, confirm, remove) built slot-based, with
   tests.
C. CDK: new Lambda, routes, IAM, throttling, tests; `cdk synth`.
D. Admin frontend: image helper, picture panel (slot 1) and offer poster panel.
E. Customer offer banner with poster and schedule.
F. Deploy 1 (needs approval): `cdk diff`, backend deploy, frontend stack deploy with
   `siteOrigin`, site build and deploy. Owner checks pictures, poster, schedule,
   search. -- CL 1: a complete, useful release.
G. Bulk CSV import (6c): backend route and tests, admin dialog. Deploy 2 and owner
   check with the sample CSV. -- CL 2.
H. Gallery slots 2 and 3: admin slots, customer product page thumbnails, tests.
   Deploy 3 and owner check. -- CL 3 (end of phase).
I. Update docs, write `docs/future-enhancements.md`, final checks, commit and tag
   `phase-4` after owner approval.

Several deploys are intended so a problem is found early and small.

## 12. Manual verification checklist (owner, after deploy)

1. Add a picture to an existing product from a file. It shows on the product
   page and card after a normal reload.
2. Take a photo with the phone camera for another product.
3. Replace a picture. The new one shows without a hard refresh.
4. Try a PDF or a 20 MB photo. Both are refused with a clear message.
5. Edit a product in two tabs, then add a picture in the second. Conflict
   message appears.
6. Remove a picture. The placeholder appears.
7. Upload an offer poster. It shows in the home page banner. Remove it.
8. Paste an image URL that allows access, and one that blocks it. Confirm the file
   upload tab is disabled while the URL tab is used.
9. Search: type part of a name, SKU and brand; list narrows; clear restores it.
10. Offer schedule: set start tomorrow (banner hidden), then start today (shown),
    then end yesterday (hidden).
11. Import `docs/sample-products-import.csv`: three live products created; run it
    again, all three skipped; try a file with a bad category and see the row error.
12. Gallery: add 3 pictures; thumbnails switch the main picture; page still loads
    fast; remove one slot.

## 13. Risks and mitigations

- Wrong CORS blocks all uploads: exact origin only, verified by a test and by the
  checklist; wildcard is never used.
- Stale pictures: new version number on every change; `/media/*` is cached for a
  year, so a reused name would stay stale.
- Presigned POST abuse: key chosen by server, content type and size fixed,
  5-minute expiry, admin key required, lower throttle.
- Wrong or huge files: checked in the browser and again on the server (type from
  the stored object, size limits).
- Storage growth: old versions stay. At the current size this costs cents. Cleanup
  is a later item.
- Phone camera pictures can be rotated: the canvas resize respects the EXIF
  orientation in current browsers; verify in the checklist on a real phone.
- Admin key still guards everything until Cognito arrives.

## 14. Assumptions

- The site origin is `https://d1sq3xexjsq6iz.cloudfront.net` until the custom
  domain is attached.
- The browser can encode WebP (all current Chrome, Edge, Firefox; Safari 17+).
  If not, the admin sees a clear message.
- Up to 3 pictures per product (slot 1 = main). Gallery pictures are not in the
  catalog index.
- CSV import is for text data only, up to 500 rows per file.

## 15. Files expected to change or be added

New: `api/handlers/admin_uploads.py`, `api/handlers/image_rules.py`,
`api/handlers/admin_import.py`, `api/tests/test_admin_uploads.py`,
`api/tests/test_admin_import.py`, `app/lib/admin-api/image-prepare.mjs`,
`app/lib/admin-api/csv-import.mjs`, `docs/future-enhancements.md`,
`docs/sample-products-import.csv` (already added), JS tests.
Changed: `api/handlers/admin_products.py`, `api/handlers/admin_site_config.py`,
`api/handlers/get_site_config.py`, `api/handlers/get_product.py` (gallery),
`api/handlers/product_validation.py` (offer dates), `api/handlers/dynamodb.py`,
`infra/backend_stack.py`, `infra/frontend_stack.py`,
`infra/tests/*`, `app/admin/dashboard/page.js`, `app/lib/admin-api/*`,
`app/page.js` (poster and schedule), `scripts/product-shell.js` (gallery),
`package.json` (test script if needed).

## 16. Open questions for the owner

All first-draft questions are answered (section 0). Remaining:
1. Confirm the CSV columns in section 6c and the sample file. Add or remove any
   column (for example price, HSN code, shelf life) before building. Extra columns
   mean extra fields in the data model, so tell me now.
2. ANSWERED: CSV columns approved as is; imported products go live (PUBLISHED) by default.
3. Any other additions before approval.

## 17. Rollback

Tag before deploy: `git tag pre-phase-4`. Redeploy the previous backend and site
from the tag. Pictures already uploaded are harmless. To undo the CORS rule,
redeploy the frontend stack without `siteOrigin`. DynamoDB has point-in-time
recovery for the Products table.
