# Phase 2c customer frontend: local use and release

Customer pages load the catalogue index and media from the same-origin
CloudFront paths (`/data/catalog-index.json` and `/<media-key>`). Product
details and site configuration load from the API Gateway URL embedded into the
static build as `NEXT_PUBLIC_API_BASE_URL`. The browser never connects directly
to DynamoDB.

## Local exported-site preview

Build the static site with an API URL available in the environment. To make a
local-only build without AWS, set an explicit dummy value:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="https://api.example.invalid"
npm run build
```

For a working preview, use a real API URL and the deployed site's CloudFront
origin:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="https://<api-id>.execute-api.ap-south-1.amazonaws.com"
npm run build
$env:CLOUDFRONT_SITE_ORIGIN="https://<cloudfront-domain>"
npm run serve:export
```

Open `http://localhost:3000`. The preview server serves `out/`, rewrites
extensionless product routes to the static product shell, and proxies only
`/data/*` and `/media/*` to `CLOUDFRONT_SITE_ORIGIN`. It does not provide a
mock product API. `CLOUDFRONT_SITE_ORIGIN` must be an HTTPS origin; it is used
only by the local server and is not embedded in frontend bundles.

## Production build and deployment

From the repository root, build for the selected environment. The helper reads
the backend stack's `ApiUrl` output in `ap-south-1` and fails if it is missing:

```powershell
npm run build:frontend -- -Env prod
```

Review the diff and verify the generated static files before deploying. The
uploader checks that this build contains the matching API hostname in
`out/_next`; it performs the same check in dry-run mode.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-frontend.ps1 -Env prod -DryRun
powershell -ExecutionPolicy Bypass -File scripts/deploy-frontend.ps1 -Env prod
```

For dev, use `-Env dev` for both build and deploy. A build with the wrong
environment's API URL will be rejected by the deploy preflight.

Before the first deployment, create the rollback tag:

```powershell
git tag pre-phase-2c
```

To roll back, check out that tag, rebuild the frontend for the intended
environment, and deploy it again.

## Local verification

```powershell
npm run lint
npm run test:customer-logic
npm run test:routing
npm run check:python
```

Then set `NEXT_PUBLIC_API_BASE_URL` to a real API URL and run
`npm run build:frontend -- -Env prod` before any production deployment. The
manual CloudFront checklist is in the Phase 2c plan.

## Known differences from the previous customer UI

- Descriptions are removed from product cards and the home carousel because
  descriptions are not included in the catalog index.
- Product cards use 4:3 images.
- Product details use a pack-size dropdown.
- Related products are text-only.
- The home page has new "Shop by Category" chips.
- The offer banner and popup are reduced to text plus a link because SiteConfig
  provides only `enabled`, `text`, and `link`. The poster-style offer is deferred
  to Phase 3, which needs image, lines, and button fields.
