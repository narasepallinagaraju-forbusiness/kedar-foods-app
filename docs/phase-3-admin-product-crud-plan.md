# Phase 3: Admin product add/edit (plan only)

Status: **PLAN ONLY. Nothing is implemented. Wait for approval before coding.**
Scope decision (owner): product add/edit and a hide/show toggle from the admin
page, plus the offer banner (on/off, text, link), with the existing hardcoded admin
login kept for now and a shared **admin key** protecting the write API. Cognito,
image upload (products and offer poster), offer start/end scheduling and the custom
domain are later phases.

Owner decisions recorded (approved):
1. Visibility is a single toggle: the admin switches a product between visible
   (`PUBLISHED`) and hidden (`ARCHIVED`). Hidden products can be edited and shown
   again at any time. `DRAFT` and `UNPUBLISHED` stay reserved and unused.
2. `sku` is typed by the admin (manual) for now.
3. The category list stays the six seeded names for now; adding categories is a
   later step if needed.
4. The offer banner (enabled, text, link) is editable and live in this phase. The
   poster image and the start/end schedule are deferred to Phase 4 (they need the
   image upload system and customer page changes).

Sources: PROJECT_PLAN.md sections 8-11, 21, 22, 24; docs/product-model.md;
docs/phase-2a-backend-read-path-plan.md; docs/phase-2c-live-api-implementation.md;
current infra/backend_stack.py, api/handlers/*, scripts/seed/seed_catalog.py,
app/admin/**.

## 1. Goal

Today the admin pages save to browser localStorage, so edits never reach the live
site. After this phase the owner can add, edit, publish/unpublish and archive
products in the admin page. The change is saved in DynamoDB and the public
catalogue index is rebuilt, so customers see it within about 60 seconds.

## 2. Decisions already made by the owner

1. Keep the hardcoded login (`admin` / `kedar123`) in the browser. Replace it
   with Cognito in a later phase, before the site is announced publicly.
2. Protect write APIs with a single shared admin key (section 4).
3. Only one environment exists (prod). There is no dev stack.
4. Admin pages are touched only as listed in this plan.

## 3. Scope

In scope:
- Write API: create, update, hide (archive) and show (restore) product; admin list
  and admin get; read and update the offer banner; rebuild catalog index.
- Admin key check in the Lambda, key entered in the admin UI.
- Admin dashboard product screens switched from localStorage to the API.
- Index rebuild after every successful write.
- Tests (Python and node:test), CDK synth tests, docs.

Not in scope (explicit):
- Cognito, MFA, real user accounts (admin key is a stop-gap).
- Image upload, resize, presigned POST, media bucket write from the browser
  (Phase 4). See section 8 for how images behave in this phase.
- Offer poster image and offer start/end scheduling (Phase 4).
- Category editing and WhatsApp settings editing (SiteConfig keeps them as seeded).
- Hard delete, bulk import/export, audit tables, inquiry tracking.
- Custom domain, SEO, customer pages (no customer file changes).

## 4. Admin key (stop-gap protection)

- A long random string (at least 40 characters), created by the owner. It is
  never written in code, git, docs or chat.
- Storage: AWS Systems Manager Parameter Store `SecureString`, created once by
  the owner with the AWS CLI (CDK cannot create a SecureString). Parameter name
  is `/kedar-foods-app/prod/admin-key`. The name, not the value, goes into the
  Lambda environment variable `ADMIN_KEY_PARAMETER`.
- The write Lambdas have `ssm:GetParameter` on that one parameter only (plus
  `kms:Decrypt` through the default AWS-managed key). The value is read once per
  Lambda container and cached in memory, never logged.
- Requests send `X-Admin-Key: <key>`. The Lambda compares with
  `hmac.compare_digest`. Missing or wrong key returns 401 with a generic body and
  logs only "admin key rejected", no key material, no request body.
- If the parameter cannot be read, return 503, never "allow".
- Rotation: the owner puts a new parameter value and redeploys or waits for
  container recycling (cache lifetime 5 minutes, then re-read).
- API Gateway throttling for `/admin/*` routes is lower than the public routes
  (for example rate 5, burst 10) to slow down guessing.
- UI: one extra "Admin key" field on `/admin`. The key is kept in
  `sessionStorage` only (gone when the tab closes), never in the bundle, never in
  localStorage, never in a URL.
- Known weaknesses, accepted for now: one shared secret, no per-user identity,
  no audit of who changed what, a leak requires rotation. `createdBy` and
  `updatedBy` are set to `"admin-key"`.
- **Gate:** Cognito must replace the hardcoded login and the key before the
  public launch (PROJECT_PLAN section 21).

## 5. API design

All routes live on the existing HTTP API (`ApiUrl`). Base path `/admin`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /admin/products | List all products, any status, with `version` |
| GET | /admin/products/{id} | One product, all fields |
| POST | /admin/products | Create |
| PUT | /admin/products/{id} | Update, requires expected `version` |
| POST | /admin/products/{id}/archive | status -> ARCHIVED (hidden from the site) |
| POST | /admin/products/{id}/restore | status -> PUBLISHED (shown on the site) |
| GET | /admin/site-config | Offer banner as stored (admin view) |
| PUT | /admin/site-config/offer | Update offerBanner {enabled, text, link} only |
| POST | /admin/catalog-index/rebuild | Rebuild and upload the index |

Common rules:
- Every handler checks the admin key first, before parsing the body.
- Body limit 64 KB, JSON only, unknown fields rejected (not ignored).
- Responses use `no-store`, `X-Content-Type-Options: nosniff`.
- Errors: 400 validation (list of field messages, no stack traces), 401 key,
  404 unknown id, 409 version conflict or duplicate sku/slug, 503 key store
  unavailable, 500 generic.
- CORS: allowed origins stay the CloudFront site and `http://localhost:3000`.
  Add methods POST, PUT and the header `X-Admin-Key`. Still no wildcard origin.
  If a custom domain is added later, add it to the allowed origins.

## 6. Data rules (follow PROJECT_PLAN section 21 and the seed script)

Editable fields: `name`, `brand`, `category`, `businessType[]`, `quantities[]`,
`description`, `isTrending`, `sortRank` (optional integer).

Validation (shared allowlist, one module so tests and handlers agree):
- `name`: 2-120 chars, trimmed, no control characters.
- `brand`: 1-60 chars. `category`: must exist in the seeded SiteConfig category
  names (read from SiteConfig; if unreadable, reject with 503, not accept).
- `businessType`: non-empty subset of Bakery, Cafe, Restaurant, no duplicates.
- `quantities`: 1-12 strings, each 1-20 chars, no duplicates, stored as a list.
- `description`: up to 2000 chars. `isTrending`: boolean.
- `sortRank`: integer 0-100000, stored as int (never float; DynamoDB numbers
  are converted with Decimal on write).
- Anything else in the body is rejected.

Immutable after creation: `productId`, `sku`, `slug` (once published),
`createdAt`, `createdBy`.

Create:
- `sku` is required, unique, 2-30 chars of A-Z, 0-9, hyphen. It is chosen by the
  admin (for example KF-12).
- `productId = "prod_" + first 10 hex of sha1(sku)`, same as the seed script, so
  a duplicate sku is impossible: the write uses
  `ConditionExpression attribute_not_exists(productId)` and returns 409.
- `slug` is generated from the name (lowercase, non-alphanumerics to hyphens,
  trimmed, must match `^[a-z0-9]+(-[a-z0-9]+)*$`). On collision with an existing
  slug (checked through `slug-index`) append brand, then sku, as the seed does.
  Slug is shown to the admin before publish; it cannot change after publish.
- Status is chosen on create: `PUBLISHED` (shown) or `ARCHIVED` (hidden); the form
  defaults to hidden so a new product is not live by accident. `version = 1`;
  timestamps are UTC ISO.

Update/archive/restore:
- The client sends the `version` it loaded. The write is conditional on that
  version and increments it. A mismatch returns 409 and the UI reloads the
  record.
- Hidden (archived) products can still be edited. Showing a product requires a
  valid, complete record. Images arrive in Phase 4, so showing does **not**
  require an image (section 8).

Offer banner (`PUT /admin/site-config/offer`):
- Body allows only `enabled` (boolean), `text` (up to 160 chars, no control
  characters) and `link`. `link` is empty or must pass the same rule as the
  customer `safeLink` (single leading `/` without backslashes, or `https://`,
  no whitespace). Unknown fields are rejected.
- The write updates only `offerBanner` on the `site` item (conditional on the item
  existing); WhatsApp and categories are never touched.
- The public `GET /site-config` is cached by clients for about 60 seconds, so an
  offer change appears within about a minute.

## 7. Catalog index rebuild

- After every successful write that can affect the public list (create with
  PUBLISHED status, update of a published item, archive, restore) the
  Lambda rebuilds the index with the existing `build_catalog_index` from a full
  paginated scan of the Products table, then writes
  `data/catalog-index.json` with `Content-Type: application/json` and
  `Cache-Control: public, max-age=60`, same as the seed script.
- If the product write succeeds but the index upload fails, return a success
  with `indexRebuilt: false` and a clear message; the admin UI shows a warning
  and a "Rebuild index" button (`POST /admin/catalog-index/rebuild`). The product
  is never rolled back because of an index failure.
- Concurrent writes: the rebuild is idempotent and always reads the whole table,
  so the last rebuild wins and is correct.
- No CloudFront invalidation is created (60 second TTL is accepted, as in Phase
  2c). Document that a change can take up to about a minute to appear.
- The Lambda needs `s3:PutObject` on `data/catalog-index.json` only. The bucket
  name is passed from the frontend stack to the backend stack (CDK parameter,
  not hardcoded). Confirm during implementation whether this creates a
  circular dependency between the two stacks; if it does, pass the name through
  CDK context or a CloudFormation export instead of a direct reference, and
  stop to ask before choosing.

## 8. Images in this phase

SUPERSEDED by section 19 item B (image upload added as a follow-up). Original text:

Phase 4 owns image upload. Until then:
- New products have no `image`, so customer pages already show the neutral
  placeholder (Phase 2c behavior).
- Editing a product never changes or removes `image` and never accepts `image`
  from the client.
- The admin form shows the current image read-only (or "no image yet") and a
  note "Image upload comes later".
- Products seeded earlier keep their images.

If the owner wants a new product to have a picture before Phase 4, the existing
seed workflow can upload images; that is a manual step and not part of this
plan.

## 9. Infrastructure changes (infra/backend_stack.py)

Planned changes, to be reviewed with `cdk synth` and `cdk diff` before any
deploy:
- New write Lambda functions (or one router function with a clear route table;
  decision for implementation, default: one `admin_products` function per
  group of routes to keep IAM small).
- IAM per function, least privilege:
  - Products table: `PutItem`, `UpdateItem`, `GetItem`, `Query` (slug-index and
    table), `Scan` only on the function that rebuilds the index.
  - SiteConfig table: `GetItem` (categories) and `UpdateItem` only on the offer
    function.
  - SSM: `GetParameter` on the single admin key parameter.
  - S3: `PutObject` on `data/catalog-index.json` only.
- API routes in section 5 on the existing HTTP API, with lower throttling.
- CORS changes in section 5.
- New environment variables (names only): `PRODUCTS_TABLE_NAME`,
  `SITE_CONFIG_TABLE_NAME`, `ADMIN_KEY_PARAMETER`, `DATA_BUCKET_NAME`.
- CDK tests: routes exist, no wildcard origin, IAM has no `*` resources for the
  write functions beyond what AWS requires, tables keep `RETAIN`, point-in-time
  recovery still on.
- Lambda memory 512 MB, timeout 10 s for single-item writes; the index rebuild
  function gets 30 s.
- No change to the frontend stack, CloudFront or buckets.

## 10. Frontend (admin only, customer files untouched)

Create new modules, do not edit `useProducts.js` or `useSiteOffer.js` until the
end of the phase:
- `app/lib/admin-api/client.js`: fetch with `X-Admin-Key`, 15 s timeout (reuse
  `fetch-timeout.mjs`), maps 401/409/400/5xx to clear messages.
- `app/lib/admin-api/validation.mjs`: pure form validation mirroring section 6,
  tested with node:test.
- `app/lib/admin-api/hooks.js`: React Query hooks for list, get, create, update,
  publish, unpublish, archive, rebuild.
- `app/admin/page.js`: add the "Admin key" field, store it in `sessionStorage`.
  Login still uses the hardcoded credentials.
- `app/admin/dashboard/page.js`: product table and add/edit modal use the new
  hooks. Show status as a "Visible on site" toggle (archive/restore), version
  conflict message ("Someone changed this product; reloaded"), saving/errors, and
  an index warning with a rebuild button. Remove the localStorage product reset
  and the `data.js` export buttons because they no longer apply. The offer
  section keeps its layout but saves only on/off, text and link through the API;
  the poster image and schedule fields are shown as "coming later" and stay
  local-only.
- Offer-related and customer-facing files are not touched.

Design stays as it is. No redesign.

## 11. Tests

Python (pytest, fake DynamoDB/S3/SSM clients, no AWS, no network):
- Admin key: missing, wrong, correct; key never logged; SSM failure returns 503;
  cache re-read.
- Validation: each field, unknown fields rejected, floats rejected, lists not
  sets, sku format, businessType set.
- Create: deterministic productId, slug rules and collision, duplicate sku 409,
  default status and version.
- Update: version match and mismatch 409, immutable fields rejected, `image`
  rejected, archived item rejected.
- Publish/unpublish/archive transitions and invalid transitions.
- Index rebuild: published only, failure path returns `indexRebuilt: false`,
  product not rolled back.
- Response headers and error shapes.
- CDK tests as listed in section 9.

node:test: validation module, admin client error mapping (fake fetch), key
storage helper (no persistence beyond the session).

Checks to run: `npm run lint`, `npm run test:customer-logic` (and the new admin
logic script), `npm run test:routing`, `npm run check:python`, `cdk synth`.

## 12. Implementation order and rules

- Part A: shared validation and slug/productId modules in `api/handlers`, with
  tests. No AWS.
- Part B: admin handlers, admin key module, index rebuild, with tests. No AWS.
- Part C: CDK changes (routes, IAM, CORS, env vars) and CDK tests; `cdk synth`
  only. **Show the synth output and stop.** `cdk diff` and `cdk deploy` happen
  only after separate approval.
- Part D: admin frontend modules and pages; lint, tests, dummy-URL build.
- Part E: owner creates the SSM parameter, deploy backend, manual checklist.
- Do not commit without approval. Make no AWS calls during Parts A-D.
- Do not touch customer pages, `scripts/seed/` behavior, `infra` frontend stack,
  or `app/lib/data.js`.

## 13. Manual verification checklist (after deploy, run by the owner)

1. `curl` any `/admin/*` route with no key: 401. With a wrong key: 401.
2. Create a product with the key: 201, status DRAFT, no change on the public
   catalogue.
3. Create a product (hidden by default), then switch "Visible on site" on: within
   about 60 seconds it appears in the catalogue and at `/products/<slug>`; the
   page shows the image placeholder.
4. Edit the name and quantities: change appears after the cache window; slug
   unchanged.
5. Open the same product in two tabs, save in both: second save shows the
   conflict message and reloads.
6. Switch "Visible on site" off: product disappears from the catalogue;
   `/products/<slug>` shows "Product not found". Switch it on again: it returns.
7. Edit the offer text/link and switch it on: the home page banner updates
   within about a minute; an unsafe link (for example `//evil.com`) is rejected.
8. Invalid input (empty name, bad sku, unknown category) shows field errors.
9. Stop the key: close the tab, reopen `/admin`, the dashboard asks for the key
   again.
10. Check CloudWatch logs contain no admin key and no request bodies.
11. Existing seeded products and the public site still work.

## 14. Assumptions

- The seeded categories exist in SiteConfig and are the allowed list.
- The owner can create an SSM SecureString in `ap-south-1`.
- `ApiUrl` and CORS origins are unchanged.
- The product list is small (tens to low hundreds); a full scan for the index
  is acceptable.
- The hardcoded login stays visible in the JavaScript bundle; the admin key,
  not the login, is the real protection.

## 15. Risks

- **Shared key is weak:** anyone who gets the key can edit the live catalogue.
  Mitigation: SecureString storage, never in the bundle or git, throttling,
  rotation, and replace with Cognito before launch.
- **Admin pages are public and use a hardcoded password.** Not a protection, by
  design of this phase.
- **Index staleness:** up to about 60 seconds after a change.
- **Index upload failure:** handled by the warning and rebuild button.
- **No audit trail:** `updatedBy` is a constant; add real identity with Cognito.
- **Stack dependency:** passing the data bucket name to the backend stack may
  create a circular dependency (section 7); resolve before coding the infra.
- **No images for new products** until Phase 4.
- **Cost:** DynamoDB on-demand, SSM standard parameter and Lambda are within
  free or negligible cost at this scale.

## 16. Files expected to change or be added

New:
- `api/handlers/admin_products.py`, `admin_site_config.py`, `admin_auth.py`,
  `product_validation.py`
- `api/tests/test_admin_products.py`, `test_admin_site_config.py`,
  `test_admin_auth.py`, `test_product_validation.py`
- `app/lib/admin-api/client.js`, `hooks.js`, `validation.mjs`,
  `validation.test.mjs`, `client.test.mjs`
- `docs/phase-3-admin-product-crud-implementation.md`

Changed:
- `infra/backend_stack.py`, `infra/app.py` (bucket name wiring), infra tests
- `app/admin/page.js`, `app/admin/dashboard/page.js`
- `package.json` (new test script), `.env.example` (documentation only)
- `docs/phase-2a-backend-read-path-plan.md` or PROJECT_PLAN.md only to record
  the decisions above

Not changed: customer pages, `app/lib/api/*` (customer), `app/lib/data.js`,
`scripts/seed/*` behavior, frontend stack, CloudFront function.

## 17. Open questions for the owner

All four were answered; see "Owner decisions recorded" at the top. Remaining item
to decide later: the poster image and offer start/end schedule (Phase 4).

## 18. Rollback

Before deploying: `git tag pre-phase-3`. To roll back: check out the tag,
rebuild and redeploy the frontend, and redeploy the backend stack from that tag.
The Products table has point-in-time recovery enabled; the admin key parameter is
deleted separately if the phase is abandoned.

## 19. Change requests after the first deploy (owner testing, Phase 3 follow-up)

Backend and frontend of sections 1 to 18 were deployed and mostly verified. The
owner asked for four follow-ups. Section 8 ("Images in this phase") is superseded
by item B below.

Status key: DONE = built locally; DEFERRED = owner moved it to Phase 4.

### A. Enquire on WhatsApp button on the product detail page. DONE (local)

Removed from `scripts/product-shell.js`, together with the now-unused site-config
query and WhatsApp imports. Needs a frontend build and deploy to go live.
Still present (not asked to remove yet): the home page hero carousel button and
the home page "Enquire on WhatsApp" link. Ask the owner before touching them.

### B. Product images in admin. DEFERRED to Phase 4 (owner decision)

Owner wants: upload a file, capture with the device camera, or paste a URL.

Design:
- File chooser uses `accept="image/*"`; a second button uses `capture="environment"`
  to open the camera on phones.
- The browser resizes and converts to WebP with a canvas: `card` (about 480 px
  wide) and `main` (about 1200 px wide). Max source size 10 MB; JPEG, PNG, WebP.
- The browser then uploads both files straight to S3 using short-lived presigned
  PUT URLs from a new admin endpoint `POST /admin/products/{id}/image-upload`
  (key required, 5 requests per minute throttle, content type and size fixed in
  the signature, expiry 5 minutes).
- Keys are versioned and never overwritten:
  `media/products/{productId}/card-vN.webp` and `main-vN.webp`. `/media/*` is
  cached for one year, so a new version number is what makes a changed picture
  show immediately.
- A second call `PUT /admin/products/{id}/image` (with `version` check) verifies
  both objects exist in S3, saves `image: {card, main}`, and rebuilds the index.
- URL option: the browser fetches the URL, and if the other site allows it,
  resizes and uploads the same way. The server never fetches the URL (avoids
  server-side request forgery). If the site blocks it the admin sees "download
  the picture and upload the file instead".
- Remove picture: sets `image` back to empty (placeholder), objects kept.

Infrastructure: `s3:PutObject` for the products Lambda only on
`media/products/*` (no wildcard bucket access); S3 CORS rule on the media bucket
for PUT, only when the `siteOrigin` context value is set (the existing rule from
the first CDK plan: https exact origin, never a wildcard). This needs a frontend
stack deploy with `-c siteOrigin=https://d1sq3xexjsq6iz.cloudfront.net`, which
the owner must approve. Orphan image versions are not deleted automatically.

### C. Offer banner poster image. DEFERRED to Phase 4 (owner decision)

Same upload flow, key `media/offer/poster-vN.webp` (about 1200 px wide), saved on
the SiteConfig `offerBanner.image`. Admin gets a poster upload box in the offer
section plus "remove poster". Customer pages must then show the poster in the
offer banner, so this item touches customer code (`app/page.js` banner) and
needs the owner's approval for that exception to the "do not touch customer
pages" rule. Schedule (start/end date) stays deferred.

### D. Changes not appearing until a hard refresh. DONE (local), backend deploy pending

Cause: the public catalog file is saved with `Cache-Control: public, max-age=60`,
so the browser keeps its own copy for a minute, and CloudFront keeps one for 60 s
to 5 min. The product API and site-config API add 30 s of browser caching and the
site-config Lambda caches for 60 s.

Fix (DONE locally, needs backend deploy):
- Catalog index uploaded as `Cache-Control: public, max-age=0, must-revalidate`
  (browser must check with the server each time; an unchanged file answers with a
  tiny "not modified"). CloudFront honors this for the /data/* policy (min TTL 0),
  so it also stops serving stale copies. No CloudFront invalidation permission is
  needed.
- Product API and site-config API responses use the same header instead of 30 s.
- There is no Lambda-side cache on site-config (earlier note was wrong).
- In-page data (React Query) is memory only and is reset on every normal reload,
  so no change is needed there.
- After the fix a normal reload shows a change within a few seconds. Tabs that
  are already open still need one reload.
- The catalog index file already in S3 keeps its old header until the next admin
  write or "Rebuild public list" re-uploads it.
- Tests updated for the new header values.

Cost: slightly more Lambda calls and S3 reads. Negligible at current traffic.

### Suggested order

1. D and A, one backend deploy plus one frontend deploy (current step).
2. B and C move to Phase 4 together with the open questions below.

### Open questions for the owner

1. Is "paste a URL" acceptable with the limit that it only works if the other site
   allows it? (Otherwise remove the URL option.)
2. May item C change the customer home page banner?
3. Should the home page "Enquire on WhatsApp" buttons also be removed?
