# Phase 2c: Wire the customer frontend to the live API

## Goal and guardrails

Replace the customer-facing mock/localStorage product and offer reads with the
already deployed public API and CloudFront objects. Keep the existing customer
visual design and static-export/product-shell routing.

- Customer scope is `/`, `/catalogue`, and the product detail shell only.
- Do not change admin pages or the admin dashboard.
- Keep `useProducts` and `useSiteOffer` available for admin use; customer
  components must stop importing/calling them.
- For every customer link to `/products/<slug>`—including home carousel cards,
  catalogue cards, and related products—use a plain `<a href>` element, never
  `next/link` or `router.push`. This follows the Phase 0 routing decision:
  `next/link` may prefetch a dynamic-slug data file that is not exported, and
  the edge function leaves paths with a file extension alone, causing a 404.
  `next/link` remains appropriate for real static routes such as `/` and
  `/catalogue`.
- Keep `app/lib/data.js` as the source for admin constants/helpers and as the
  customer fallback for existing WhatsApp number/display/message values.
- Do not add infrastructure, API routes, Cognito, upload functionality, custom
  domain work, or SEO changes.
- API calls use the API's absolute base URL; catalog JSON and media use the
  current site's same-origin CloudFront paths.

## Verified endpoints and response contracts

Read `NEXT_PUBLIC_API_BASE_URL` from the `ApiUrl` output of
`kedar-foods-app-{env}-backend`. Normalize away a trailing slash before joining
API routes:

- `GET {API}/products/{slug}`
- `GET {API}/site-config`

The product response is the Phase 2a allowlist: `id`, `sku`, `slug`, `name`,
`brand`, `category`, `businessType[]`, `quantities[]`, `description`,
`image? {card, main}`, and `updatedAt?`. Never expect or consume a raw DynamoDB
item. Image keys already include `media/`, so render them as `"/" + key`.

The SiteConfig response contains optional `offerBanner {enabled, text, link}`,
`categories[] {id, name, slug, sortOrder, isActive}`, and
`whatsapp {number, display, messageTemplate, generalMessage}`. Treat the
WhatsApp values as optional so the current constants in `app/lib/data.js` can
provide a reliable fallback.

CloudFront same-origin reads:

- `GET /data/catalog-index.json`
- Images at `/<key>`, such as `/media/products/<productId>/card-v1.webp`.

The catalog index is `{version, items}`. Each public item contains only `id`,
`sku`, `slug`, `name`, `brand`, `category`, `businessType[]`, `quantities[]`,
optional `thumbnailKey`, `isTrending`, `searchText`, and `sortRank`.

## Customer data modules and hooks

Create a small `app/lib/api/` surface separate from the admin stores. Keep
request construction and pure customer logic out of page components:

- `client.js`: normalize the configured API base URL and fetch JSON with clear
  errors for network failures and non-success statuses. Keep 404 distinguishable
  for product-detail handling. If `NEXT_PUBLIC_API_BASE_URL` is empty or
  missing, throw a clear configuration error; do not silently fall back to a
  mock or relative API URL.
- `catalog.js`: fetch and validate the catalog-index envelope/items.
- `catalog.mjs`: pure catalogue filtering, search, ordering, pagination, and
  related-product helpers.
- `site-config.js`: fetch SiteConfig and provide safe fallback accessors for
  WhatsApp values and home category labels.
- `products.js`: fetch one lowercase slug from the product API and resolve
  product image URLs from final `media/...` keys.
- `slug.mjs`: pure pathname-to-product-slug parsing and validation.
- `whatsapp.mjs`: pure message placeholder filling and WhatsApp URL building.
- `hooks.js` or focused hook modules: React Query hooks for the catalog index,
  site configuration, and one product. Use stable query keys and cancellation
  where supported.

Set query behavior explicitly for customer requests: `staleTime: 60_000` and
`refetchOnWindowFocus: false`, consistent with the existing QueryClient defaults.
The index is fetched once per fresh/stale query window and reused across home,
catalogue, and product-related sections. Give failed requests visible retry
controls rather than treating errors as empty successful data.

Keep pure logic modules and their tests in `.mjs` files so Node's built-in
`node:test` can load them without changing `package.json`'s module type. Do not
add a frontend test dependency. Components may import these `.mjs` modules;
the Next.js static-export build must verify that those imports bundle correctly.
Run the Node tests as part of implementation to prove the test files load and
execute.

## Catalogue page

Replace only the customer catalogue's `useProducts` read with the catalog-index
hook. Leave the existing admin use of `useProducts` untouched.

- Search uses the trimmed, lowercased input and substring-matches only the
  index's `searchText` (which represents name, brand, and category).
- Business type matches if any selected value occurs in a product's
  `businessType`; selected values within a group are ORed.
- Brand and category choices are derived from the index. Each group is ORed;
  the active groups are combined with AND.
- Preserve the existing `business` query-parameter behavior. Add/read a
  category query parameter for category links from home if needed, without
  changing current filters.
- Sort the filtered result by `isTrending` descending, then `sortRank`
  ascending. Use a deterministic name tie-break if ranks are equal.
- Show the first 12 results. A "Load more" action reveals the next 12; reset
  the visible count when search or filters change.
- Provide distinct loading, no-match/empty, and error-with-retry views.
- Keep current filter drawer, search, grid, header/footer, and responsive visual
  behavior.
- Adapt `ProductCard` to the index contract: navigate using its slug, use sku
  and quantities, use `thumbnailKey` for the image, and omit fields (such as
  full description) that are not in the public index. Place thumbnails in a
  fixed-aspect container with `object-fit: cover`, `loading="lazy"`, and a
  neutral placeholder when the key is absent.
- Build image URLs only as `"/" + thumbnailKey`; do not prepend an external
  media base URL.
- Every product card link to `/products/<slug>` must be a plain `<a href>`, not
  `next/link` or `router.push`, to prevent a prefetch request for a nonexistent
  dynamic-slug export file. Static-route links such as `/catalogue` may continue
  to use `next/link`.

## Product detail shell

Keep the existing exported `/products/_shell.html` entry and CloudFront
extensionless product-route rewrite. Put pathname parsing in the pure
`slug.mjs` module, with tests proving:

- `/products/amul-unsalted-butter` resolves to `amul-unsalted-butter`.
- `/products/Amul-Unsalted-Butter/` resolves to
  `amul-unsalted-butter` (trailing slash removed and lowercased).
- An encoded valid slug is decoded before validation and returned lowercase.
- `/products/` and `/products` produce an empty slug; do not call the API and
  render not-found.
- An invalid slug does not call the API and renders not-found.

For a valid slug, the shell reads `window.location.pathname`, uses the parsed
slug, and queries `{API}/products/{encodedSlug}`. Remove `/mock-api` completely
from the customer path. Every customer link to `/products/<slug>`, including
related-product links, must be a plain `<a href>` rather than `next/link` or
`router.push`, avoiding prefetches for dynamic-slug export files. Continue to
use `next/link` for actual static routes.

Implement the explicit states:

- Loading while the API request is pending.
- Found for a successful public product.
- Not found for API 404 (unknown and unpublished slugs stay indistinguishable).
- Error with retry for network and retryable server failures; do not present a
  5xx/network failure as a missing product.

On slug changes, cancel or disregard the stale request and load the new slug.
Set `document.title` from the found product and restore the application default
title on shell teardown/not-found as appropriate.

Render product name, SKU, brand, category, description, and pack sizes from the
detail response. Show the `image.main` key as `"/" + key`; if it is missing,
fails to load, or is absent, show a neutral placeholder. Add a real selected
pack-size control (rather than only a static list) and build the product
WhatsApp enquiry with the selected pack.

Related products come from the shared catalog-index query: same category,
excluding the current product id, at most four. Link to each related product
with a plain `<a href="/products/<slug>">`; do not use `next/link` or
`router.push`. If the index is unavailable, keep the product detail usable and
omit or gracefully report the related section; an index failure must not turn
a successful detail response into an error.

## WhatsApp and shared customer components

Create a pure helper module `app/lib/api/whatsapp.mjs` with
placeholder filling and URL construction. Product messages substitute:

- `{name}` with product name.
- `{sku}` with product SKU.
- `{pack}` with `" - Selected Pack Size: X"` when a pack is selected, otherwise
  the empty string.

Build `https://wa.me/{number}?text={URL-encoded message}` from SiteConfig's
number/template. The general enquiry uses `whatsapp.generalMessage`; display
text uses `whatsapp.display`. If SiteConfig is loading or fails, use existing
`WHATSAPP_NUMBER`, `WHATSAPP_DISPLAY`, and current message text from
`app/lib/data.js`, so the enquiry controls remain usable during API outages.
Never persist SiteConfig or fallback state in localStorage.

Update customer-facing shared components that expose these values, including
Header, Footer, ProductCard, and home hero/offer components. Verify admin pages
do not import these customer-only components before changing any shared
surface; if a shared component is also used by admin, preserve its current
admin behavior without changing admin pages.

If a shared customer component renders a product destination, it must use a
plain `<a href="/products/<slug>">` link, never `next/link` or `router.push`.
Continue using `next/link` only for real static routes.

The home offer model has text/link but no image. Adapt the existing promotional
banner and popup to display the configured text and use the configured link;
do not require an image or invent new offer data. Show them only after config
loads and `offerBanner.enabled` is true. A config failure hides the remote offer
without displaying stale localStorage offer content.

## Home page

- Replace its `useProducts` and `useSiteOffer` reads with the new catalog-index
  and SiteConfig hooks.
- Build the existing trending hero/carousel from index items where
  `isTrending` is true. Use the card `thumbnailKey` (`/<key>`); the index has no
  full description, so do not assume one.
- Every home carousel link to `/products/<slug>` must be a plain `<a href>`,
  never `next/link` or `router.push`, to avoid prefetching a dynamic-slug export
  file. Keep `next/link` for real static routes such as `/catalogue`.
- Keep `TOP_BRANDS` in `app/lib/data.js`.
- Read home categories from SiteConfig, with `CATEGORIES` from
  `app/lib/data.js` as fallback. Render them as links/filter affordances to the
  catalogue; keep category ids/slugs/names aligned with the API values.
- Show the SiteConfig offer banner/popup according to its `enabled`, `text`, and
  `link` fields.
- Keep the current business-style section, layout and styling.
- Do not read products or offer state from localStorage on customer pages.

## Configuration, local development, and build/deploy

Add/update `.env.example` with a documented, non-secret
`NEXT_PUBLIC_API_BASE_URL` entry. This is a public API endpoint, not a
credential. Data and media remain relative to the site origin: `/data/...` and
`"/" + key`.

For local development, a plain Next dev server or opening `out/` directly does
not proxy CloudFront's same-origin paths. `/data` and `/media` work on the
deployed CloudFront origin, but do not have CORS headers for a local origin.
The simplest no-infrastructure-change local setup is to repurpose
`scripts/spike-server.mjs` as an exported-site static server and proxy:

1. Serve `out/` on `http://localhost:3000` (the site origin already permitted
   by API CORS).
2. Proxy only `/data/*` and `/media/*` to the configured/deployed CloudFront
   site domain, preserving request path/query, response status, and relevant
   content/cache headers; do not add permissive CORS headers.
3. Keep API calls direct to `NEXT_PUBLIC_API_BASE_URL`; their Origin is
   `http://localhost:3000`, already allowed.
4. Remove `/mock-api` and the `spike-data` fixture handling from the customer
   dev path. Remove the fixture if no other tool depends on it, or explicitly
   isolate it as a Phase 0-only tool that cannot be mistaken for live data.

Create `scripts/build-frontend.ps1` with `-Env (prod|dev, default prod)`:

- Use region `ap-south-1`; read `ApiUrl` from
  `kedar-foods-app-{env}-backend` via `aws cloudformation describe-stacks`.
- Check every AWS command's exit code, the stack response, and that `ApiUrl` is
  non-empty. Fail with an actionable error if the output is absent.
- Set `NEXT_PUBLIC_API_BASE_URL` in the process environment before `npm run
  build`, so Next's static export embeds the correct endpoint.
- Ensure a production build fails clearly if `NEXT_PUBLIC_API_BASE_URL` is
  missing, either with a prebuild guard or in the build helper. An explicit
  dummy value such as `https://api.example.invalid` is allowed for local build
  checks that make no AWS calls.
- Keep `scripts/deploy-frontend.ps1` as the uploader and invalidation script.
  Its only permitted change is one preflight check: using the same
  `aws cloudformation describe-stacks` pattern it already uses, read `ApiUrl`
  from `kedar-foods-app-{Env}-backend`, extract/check its hostname, and require
  that hostname to appear in at least one file under `out/_next`. If not, stop
  with a clear message telling the operator to run
  `npm run build:frontend`. This check must also run in `-DryRun`; make no other
  uploader changes.

Add a `build:frontend` npm script to invoke this helper. Document the exact
prod/dev sequence; build must run before deployment and `-Env` must match the
target backend/frontend environment. Continue to use `deploy:frontend` (or
invoke the existing PowerShell uploader with its environment argument) after
building.

Before deploying, tag the current commit with `git tag pre-phase-2c`. To roll
back, check out that tag, rebuild the frontend, and deploy it again.

## Implementation order and file boundaries

Implement in three parts:

- **Part A — pure modules and tests:** add the framework-independent `.mjs`
  modules and their `.test.mjs` tests, including catalog behavior, WhatsApp
  message/link construction, and pathname-to-slug parsing. Run the Node tests
  to prove the files load and the cases pass.
- **Part B — customer UI wiring:** add the API client and hooks, then update
  home, catalogue, product shell, and shared customer components to use live
  data and the pure helpers. Preserve the existing design, admin behavior, and
  static-export routing.
- **Part C — scripts, npm scripts, docs, and `.env.example`:** add the build
  helper/configuration guard, the one permitted deploy-script preflight,
  test/build npm scripts, and customer-facing configuration/deployment
  documentation.

Do not edit admin pages or dashboard files, `app/lib/useProducts.js`,
`app/lib/useSiteOffer.js`, `infra/`, `api/`, or `seed/`. Do not make AWS calls
or run the deploy script during implementation.

## Pure tests and acceptance checklist

Add plain modules for logic and Node built-in `node:test` tests for:

- Pathname-to-slug parsing and validation in `slug.mjs`, including the standard
  product path, uppercase/trailing-slash path, encoded slug, empty `/products`
  and `/products/` paths, and invalid slugs. Empty and invalid values must
  produce not-found without making an API request.
- Filter OR-within-groups and AND-across-groups behavior.
- Trimmed/case-insensitive search using `searchText` only.
- Trending-first then rank ordering and deterministic ties.
- Page size 12, successive page slices, and reset after query/filter changes.
- Product URL/slug handling, related-product same-category/exclusion/maximum 4.
- Product WhatsApp placeholder filling with and without a selected pack.
- URL encoding, configured WhatsApp number/general message, and fallback
  constants.
- Optional `thumbnailKey` and image URL construction.

Add an npm test script using `node --test` for the new tests. Keep the existing
`node scripts/test-routing-function.mjs` / `npm run test:routing` behavior and
tests working. Pure modules and test files use `.mjs` extensions; run the new
Node tests to confirm Node loads and executes them without a `package.json`
module-type change.

Implementation-time verification must make no AWS calls. Run:

```powershell
npm run lint
npm run test:customer-logic
npm run test:routing
npm run check:python
$env:NEXT_PUBLIC_API_BASE_URL="https://api.example.invalid"
npm run build
```

Confirm the build creates `out/products/_shell.html`, `out/index.html`, and
`out/catalogue.html`. Also inspect/grep customer page imports to prove that
customer pages no longer import `useProducts` or `useSiteOffer`. Do not run
`scripts/deploy-frontend.ps1` during implementation. The real
`npm run build:frontend` and deployment are performed by the user afterwards.

After the user builds and deploys, manually verify against the CloudFront site:

1. Home loads; trending carousel is populated from the index; categories come
   from SiteConfig; fixed Top Brands remain visible.
2. Offer banner/popup appears only when enabled and uses configured text/link;
   it is absent when disabled.
3. Catalogue loads once and shows loading, empty, and retryable error states as
   applicable.
4. Business-type multi-select OR behavior and brand/category multi-select OR
   behavior; active groups combine with AND.
5. Brand/category choices match seeded index products; category links from home
   open the corresponding catalogue filter.
6. Search trims whitespace and matches case-insensitively against name, brand,
   and category only.
7. Default order puts trending products first, then sorts by rank.
8. "Load more" reveals 12 more cards at a time; changing search/filter resets
   the shown count.
9. Product card images use the `media/...` key, lazy-load, crop consistently,
    and show a placeholder if the thumbnail is absent. Clicking a product card
    navigates through a plain `<a href>`; it must not prefetch a dynamic-slug
    data file.
10. Open several known product slugs; check main image, description, SKU,
    selectable pack size, and related same-category products (maximum four).
    Home carousel and related-product navigation must also use plain `<a href>`
    links for product slugs.
11. Open an unknown slug and confirm a not-found state; directly refresh a
    product URL and confirm the CloudFront shell still loads and resolves it.
12. Check product and general WhatsApp links: configured number, correct
    display, URL encoding, `{name}`/`{sku}`, selected and empty `{pack}`, and
    correct general message.
13. Make SiteConfig unavailable: WhatsApp remains usable with code fallbacks,
    and no stale localStorage offer is displayed.
14. Throttle the network: loading/retry behavior remains usable. Disable/fail
    the API: catalogue/detail errors are explicit and retryable, unknown slug
    remains a 404, and no 5xx/network error is shown as not-found.
15. Repeat key navigation, filters, load-more, image placeholders and WhatsApp
    checks on mobile widths.

Planned build/deploy commands:

```powershell
npm run build:frontend -- -Env prod
npm run deploy:frontend
```

For dev, use the matching environment for both steps, for example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-frontend.ps1 -Env dev
powershell -ExecutionPolicy Bypass -File scripts/deploy-frontend.ps1 -Env dev
```

Also run the new pure logic tests and existing routing tests before building:

```powershell
npm run test:customer-logic
npm run test:routing
```

## Files expected

Likely new files:

- `app/lib/api/client.js`
- `app/lib/api/catalog.js`
- `app/lib/api/catalog.mjs`
- `app/lib/api/site-config.js`
- `app/lib/api/products.js`
- `app/lib/api/slug.mjs`
- `app/lib/api/whatsapp.mjs`
- `app/lib/api/hooks.js` (or narrowly split React Query hooks)
- `app/lib/api/catalog.test.mjs`
- `app/lib/api/slug.test.mjs`
- `app/lib/api/whatsapp.test.mjs`
- `scripts/build-frontend.ps1`

Likely updated files:

- `app/page.js`
- `app/catalogue/page.js`
- `app/products/[slug]/page.js` and/or `scripts/product-shell.js` (keep static
  shell export/routing intact)
- `components/kedar/ProductCard.js`
- `components/kedar/Header.js` and `Footer.js` if their customer WhatsApp
  affordances need SiteConfig display/links
- `components/kedar/OfferPromoBlock.js` and `OfferPopup.js`
- `scripts/spike-server.mjs`
- `scripts/deploy-frontend.ps1` (add only the specified API-hostname preflight
  check; no other uploader changes)
- `package.json`
- `.env.example`
- customer-facing docs (for example a Phase 2c implementation/local
  development guide)

Do not edit admin pages, `app/admin/**`, `app/lib/useProducts.js`,
`app/lib/useSiteOffer.js`, or add infrastructure changes. Preserve
`app/lib/data.js` as-is unless a strictly necessary customer/admin separation
requires a later explicit approval. The implementation must not touch
`infra/`, `api/`, or `seed/`.

## Assumptions and risks

- The deployed `ApiUrl`, API routes, seeded data, and CloudFront `/data` and
  `/media` objects are available and match the Phase 2a/2b response contracts.
- API CORS currently allows the deployed site origin and
  `http://localhost:3000`. A future custom domain must also be added to API
  CORS, or browser API requests from it will fail even though `/data` and
  `/media` are same-origin.
- Catalog CloudFront caching may leave the index stale for up to about 60
  seconds after a seed/admin change; product detail API success caching is 30
  seconds. Related products can therefore lag an index refresh briefly.
- Card source images have mixed aspect ratios; fixed-aspect `object-fit: cover`
  intentionally crops thumbnails, while the detail main image should preserve
  its natural proportions.
- `NEXT_PUBLIC_API_BASE_URL` is embedded at build time; using the wrong `-Env`
  can point a deployed static site at the wrong API until rebuilt and
  redeployed.
- The local static proxy needs the intended CloudFront site domain configured
  and network access to it. Port 3000 is required to match the already-allowed
  local API CORS origin.
- SiteConfig outage should not break enquiries: WhatsApp falls back to the
  existing code constants. Categories also fall back to `CATEGORIES`; the
  dynamic offer has no localStorage fallback by design.
- Do not assume index items include descriptions or a main image; those exist
  only on product detail responses.
- Route refresh depends on the deployed CloudFront Function continuing to
  rewrite `/products/<slug>` to the static shell; no client-only solution
  replaces that edge behavior.

## Explicitly out of scope

- Admin pages/dashboard, admin hooks/data persistence changes, Cognito, admin
  APIs, and authorization.
- Product editing, image uploads, upload APIs, seed changes, and backend/CDK
  infrastructure changes.
- Custom-domain setup or CORS changes for a new origin.
- SEO metadata/schema redesign, server rendering, and replacing the static
  export or CloudFront product-shell route strategy.
