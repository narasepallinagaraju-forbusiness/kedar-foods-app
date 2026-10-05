# Phase 0 Product Routing Decision

## Decision

Keep clean product URLs in the form `/products/{slug}`. Serve a single static
product shell page and use a narrowly scoped edge rewrite to serve that shell
for product slugs that were not known when the frontend was built.

The shell reads the requested slug from `window.location.pathname` and loads
product data client-side. It does not use `useParams()` for the rewritten slug.

## Local routing prototype results

All six Phase 0 routing cases passed locally:

| Test | Result |
| --- | --- |
| Direct visit to `/products/example-product` | Passed |
| Refresh on a product URL | Passed |
| Product slug added after the frontend build | Passed without rebuilding |
| Unknown product slug | Passed; the mock API returns 404 and the shell shows not-found |
| Back/forward between catalogue and product pages | Passed |
| Mobile browser navigation | Passed |

## Generated shell file

The exact generated static HTML shell is:

```text
out/products/_shell.html
```

The static export also emits Next.js navigation payload files under
`out/products/`. The edge rewrite target is the HTML file above.

## Local server rewrite rules

The temporary local server in `scripts/spike-server.mjs` rewrites a request to
`/products/_shell.html` only when its URL path:

- Matches exactly `/products/<one-segment-slug>`.
- Has no file extension.
- Is not under `/_next/`, `/data/`, or `/media/`.

Paths that do not match those rules are served as static paths from `out/` and
missing files return 404. Product API requests are served separately from the
temporary `spike-data/products.json` file.

## Draft CloudFront Function

Attach this viewer-request function to the **default frontend behavior** only.
This is documentation for Phase 1; it has not been deployed.

The source of truth for the ES5-compatible function is
[`scripts/cloudfront-routing-function.js`](../scripts/cloudfront-routing-function.js).
Keep that file and this section aligned when the function changes.

Before applying the rules below, strip trailing slashes from the URI, except
when the URI is exactly `/`. The rules are then applied in this order:

1. Leave `/_next/*`, `/data/*`, and `/media/*` unchanged.
2. Rewrite `/` to `/index.html`.
3. Rewrite exactly `/products/<one-segment-slug>` to
   `/products/_shell.html` when the segment contains no dot. Slug case is not
   checked by the edge.
4. Leave a URI unchanged when its last path segment contains a dot (a file
   extension).
5. For every other extensionless path, append `.html` to the normalized URI,
   for example `/catalogue` to `/catalogue.html` and `/admin/dashboard` to
   `/admin/dashboard.html`.

CloudFront Function events provide the query string separately from `request.uri`.
The function changes only the URI and leaves the query string untouched.
Product slugs must contain lowercase letters, digits, and hyphens only; dots are
not allowed.
The product API lowercases or rejects non-lowercase slugs; the edge does not.

Unknown non-product pages therefore request a missing `.html` object. Configure
CloudFront custom error responses for S3 `403` and `404` missing-object
responses to serve `/404.html` with response status **404**. The error response
must never point to the product shell or `/index.html`. Ensure `out/404.html`
is present in the frontend export.

## Routing validation commands

Run the static build first, then the routing tests:

```text
npm run build
node scripts/test-routing-function.mjs
```

The test script checks the required URI cases and scans every `.html` file in
`out/`, deriving its clean URL and checking that the function maps it to an
existing export file. It also verifies that `out/404.html` exists.

## Phase 1 verification gate

Before accepting the Phase 1 frontend hosting setup, repeat all six routing
tests against the dev CloudFront distribution: direct visit, refresh, a slug
added after build, unknown slug, browser back/forward, and mobile navigation.
Do not treat the local prototype as proof that the CloudFront behavior itself
works.

## Admin deployment warning

The existing admin login is a temporary client-side check, not secure
authentication or authorization. It must be replaced with the planned protected
authentication/API flow or disabled before the first public deployment.
