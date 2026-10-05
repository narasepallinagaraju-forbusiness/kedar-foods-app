# Final Project Plan: AWS Serverless Next.js Product Catalogue

Version: final (includes validation fixes). Source of truth for all AI-assisted work.

---

## 1. Goal and scope

Deploy an existing Emergent-generated Next.js product catalogue (source in GitHub) to AWS.

```text
Products: 100–1,000
Users: approximately 100–200
Traffic: seasonal/uncertain
Priority: low fixed cost, serverless, easy maintenance
```

### Phase 1 includes

```text
Public product browsing, category browsing, search and filters
Product detail pages (variants, specifications, images, customization notes)
Admin product management (create, edit, publish, unpublish, archive)
Admin product image uploads
Homepage offer/banner and basic category configuration
Custom domain and HTTPS
WhatsApp inquiry links (pre-filled message)
```

Product changes must appear on the customer site without a GitHub push or frontend redeploy.

### Phase 1 excludes

```text
Cart, checkout, payments, orders, inventory
Customer accounts, customer OTP
Email/SMS/WhatsApp automation
OpenSearch, RDS, ECS, SQS, Step Functions, EventBridge
Microservices
```

---

## 2. Architecture

Static Next.js frontend + dynamic serverless backend. Static hosting means only the UI files
(HTML, CSS, JS, fonts, icons) are prebuilt. Product and category content stays dynamic.

```text
GitHub → GitHub Actions (OIDC) → Next.js static export
                                        |
                                        v
                        Private frontend S3 bucket (OAC)
                                        |
Customer browser → CloudFront (ONE distribution, www.yourdomain.com)
                        |  behaviors:
                        |   /data/*   → Private media/data S3 bucket (OAC)
                        |   /media/*  → Private media/data S3 bucket (OAC)
                        |   /_next/*  → frontend bucket
                        |   default   → frontend bucket (+ product-shell rewrite function)
                        |
Browser → API Gateway HTTP API → Lambda → DynamoDB (Products, SiteConfig)
                                        → media/data bucket (presign, confirm, index rebuild)
Admin   → Cognito hosted login (PKCE + TOTP MFA) → protected admin APIs
```

Content update flow:

```text
Admin saves product → API Gateway → Lambda → DynamoDB
→ catalog-index.json rebuilt in media/data bucket → customers see the change
```

Use ONE CloudFront distribution. Do not create a separate media distribution or media domain.
Same-origin delivery means no CORS for the catalog index/images, one certificate, and a simpler CSP.

Use CloudFront Price Class 200 or All. Do not use Price Class 100 (customers are in India).

---

## 3. Regions and environments

### Regions

```text
All application resources (FrontendStack, BackendStack): ap-south-1 (Mumbai)
ACM certificate for CloudFront: us-east-1 (N. Virginia)
```

CloudFront is global and only needs the certificate ARN. Create the certificate once in
us-east-1 (console or CLI, DNS validation) and pass its ARN into CDK through context.
Do not create a third stack for it. Do not create a duplicate certificate in Mumbai.

### Environments

```text
dev:  uses the default CloudFront domain (no custom domain needed)
prod: custom domain, manual approval for every deploy
```

Separate AWS accounts are preferred; separate stacks (for example Frontend-dev,
Backend-prod) are the minimum. Run the first CDK deploys locally with a dev profile until
the stacks are stable, then move deploys to CI.

---

## 4. Phase 0 gate: static routing prototype

Complete this BEFORE any AWS infrastructure is built.

Major risk: product routes such as `/products/new-product-added-later` have no prebuilt
HTML file after an admin creates a new product.

### Prototype requirement

A small throwaway local test with:

```text
One static product detail shell page
One placeholder product slug
One new slug not present during build
Client-side product loading
A fallback/rewrite approach (a local server rule or CloudFront Function equivalent)
```

Test all cases:

```text
1. Direct visit: /products/example-product
2. Browser refresh on that page
3. Newly added product: /products/new-product-added-later
4. Unknown slug: /products/does-not-exist
5. Browser back/forward navigation
6. Mobile browser navigation
```

### Implementation rule

Do not depend on static route parameters. In the shell page, read the slug from
`window.location.pathname` (or `usePathname()`), then call `GET /products/{slug}`.
Do not assume `useParams()` works after a rewrite.

### Decision gate

```text
Clean URLs reliable  → keep /products/{slug}
Clean URLs unstable  → use /product?slug={slug}
```

Do not spend excessive time forcing a fragile rewrite. Record the decision in docs/.

---

## 5. Static-export validation

Before infrastructure work, audit the project:

```text
Next.js version; App Router or Pages Router
next.config.js / next.config.ts (output, rewrites, redirects, headers, images)
middleware.ts; app/api; pages/api; route.ts; server actions
getServerSideProps; getStaticProps; getStaticPaths; generateStaticParams; revalidate
next/headers; next/server; cookies(); headers(); redirect(); next/image
Node.js-only dependencies
```

Static export is allowed only if `npm run build` succeeds with:

```ts
const nextConfig = {
  output: "export",
  images: { unoptimized: true }
};
export default nextConfig;
```

Static export does not support Next rewrites/redirects/custom headers or the image optimizer.
Handle redirects and headers in CloudFront instead.

If static export fails because of required SSR, ISR, server actions, server-only cookies,
required route handlers or other server runtime features, use AWS Amplify Hosting for the
Next.js frontend only. The backend stays unchanged.

If the repository contains a separate backend (for example FastAPI/MongoDB, common in
Emergent projects), document it, plan the data migration to DynamoDB, and re-point the
admin UI to the new Lambda API.

---

## 6. Frontend data strategy

### Public catalogue listing

No public Lambda `GET /products` list API. Use a compact public index:

```text
https://www.yourdomain.com/data/catalog-index.json
```

stored at S3 key `data/catalog-index.json` in the media/data bucket (never in the frontend bucket).

The browser loads it once and performs search, category/attribute filtering, sorting,
pagination and Load More locally. Render only 12–24 product cards at a time.
Use plain JavaScript filtering first; add Fuse.js/MiniSearch only if fuzzy search is needed.

### Catalog index fields

```json
{
  "version": "2026-10-05T00:00:00Z",
  "items": [
    {
      "id": "prod_001",
      "slug": "example-product",
      "name": "Example Product",
      "modelId": "MODEL-001",
      "category": "example-category",
      "thumbnailKey": "media/products/prod_001/card-v1.webp",
      "searchText": "example product model-001 category material",
      "filterAttributes": { "material": ["example"], "color": ["white"] },
      "isFeatured": true,
      "sortRank": 10
    }
  ]
}
```

Never include: draft/unpublished/archived products, admin notes, createdBy/updatedBy,
internal status notes, supplier info, cost price, full descriptions/specifications/galleries,
customer data, secrets.

Related products are computed in the browser from this index (same category). They are
not part of the detail API.

### Index regeneration

Rebuild `data/catalog-index.json` by a full scan after a product is created, updated,
published, unpublished, archived or deleted. A full rebuild is fine at 1,000 products.
Write it with `Cache-Control: public, max-age=60, s-maxage=60`.

Required: error handling, logging, a failure response to the admin if the rebuild fails
(never silently save a product and leave the public catalogue stale), retry if needed,
and an admin "Rebuild Catalog Index" action (`POST /admin/catalog-index/rebuild`).

### Product detail API

```text
GET /products/{slug}
```

Must: return 404 if the product does not exist; return 404 if status is not PUBLISHED;
return only an explicit public allowlist of fields; never return the raw DynamoDB record.

Allowed: id, slug, name, modelId, shortDescription, description, category, specifications,
variants, customizationOptions, final public image keys (`media/...`), updatedAt if needed.

Never return: createdBy, updatedBy, adminNotes, supplierCost, draft status details,
internal audit fields, upload session data, incoming/internal image paths.

### Site configuration

```text
GET /site-config
```

Holds: offer banner, homepage content, category list/order, WhatsApp number, site settings.
The WhatsApp number lives here, not in code.

---

## 7. Buckets and CloudFront

### Bucket separation

```text
1. Frontend deployment bucket
   - Static Next.js export; replaced by deployment
   - Safe for: aws s3 sync --delete

2. Media/data bucket
   - Product images (media/...), catalog-index.json (data/...), incoming/ uploads
   - Never touched by frontend deployment
```

Both buckets are private (Block Public Access, OAC only). Never run the frontend sync
against the media/data bucket.

### Stack ownership

The media/data bucket and the CloudFront distribution are defined in FrontendStack.
Defining the bucket in BackendStack and the distribution in FrontendStack can create a
circular dependency through the OAC bucket policy. BackendStack imports the media/data
bucket (name/ARN) for Lambda permissions. BackendStack therefore depends on FrontendStack,
which also supplies the site origin for CORS and Cognito callback URLs.

### Key and URL prefixes

CloudFront passes the URL path to S3 as the object key, so they must match:

```text
URL /data/catalog-index.json            → key data/catalog-index.json
URL /media/products/prod_101/main-v2.webp → key media/products/prod_101/main-v2.webp
Uploads (never routed by CloudFront)    → key incoming/{productId}/{uploadId}
```

### Behaviors

```text
/data/*   → media/data bucket, short-cache policy (honor origin Cache-Control)
/media/*  → media/data bucket, long-cache policy
/_next/*  → frontend bucket, long cache (hashed assets)
default   → frontend bucket, short cache for HTML, with the product-shell function
```

Enable Brotli/gzip in cache policies. Tighten the bucket policy so CloudFront can read only
`data/*` and `media/*` where practical (defense in depth; no behavior routes `incoming/*`).

### Product-shell rewrite

Use a CloudFront Function (viewer request) on the default behavior to rewrite only
application page routes (for example `/products/<slug>` with no file extension) to the
static product shell page chosen in Phase 0. It must not apply to `/data/*`, `/media/*`,
`/_next/*`, or any path with a file extension. Real missing files return 404.
Do not use a distribution-wide "403/404 → index.html" error rule.

### Cache rules

```text
Hashed JS/CSS and versioned images: Cache-Control: public, max-age=31536000, immutable
index.html / app shell: short TTL
catalog-index.json: max-age=60, s-maxage=60
```

Never overwrite a cached image filename; always use a new versioned key.

---

## 8. Admin authentication

```text
Amazon Cognito User Pool
Cognito group: admin
No public signup (admin-created users only)
TOTP MFA required
OAuth authorization-code grant with PKCE
Cognito managed/hosted login (prefix domain is fine)
```

Choose one OIDC/PKCE client library for the SPA (for example `oidc-client-ts`) and
document the choice. Do not improvise a custom login flow.

```text
Admin opens /admin
→ redirect to Cognito hosted login
→ sign in + TOTP MFA
→ redirect to static /admin/callback page
→ PKCE code exchange
→ tokens held in memory (sessionStorage acceptable; never localStorage)
→ admin calls protected APIs with the ACCESS token
```

Configure the HTTP API JWT authorizer for the access token (issuer + client ID audience).
The access token carries `cognito:groups`. Configure callback and logout URLs per
environment (localhost, dev domain, prod domain).

Create the first admin with the CLI and a temporary password. In dev, test TOTP enrollment
on that first login. Check the user pool feature tier/pricing in the console.

Do not store: admin passwords in code or GitHub, tokens in localStorage, passwords in
Secrets Manager, any client secret in the browser.

---

## 9. Admin APIs

### Read

```text
GET /admin/products           (drafts, published, archived, admin metadata, version, pagination)
GET /admin/products/{id}
GET /admin/site-config
```

### Write

```text
POST /admin/products
PUT  /admin/products/{id}
POST /admin/products/{id}/publish
POST /admin/products/{id}/unpublish
POST /admin/products/{id}/archive
DELETE /admin/products/{id}        (hard delete only if explicitly enabled)
POST /admin/site-config
POST /admin/uploads/presign
POST /admin/uploads/confirm
POST /admin/catalog-index/rebuild
```

Every admin API must: require a valid Cognito JWT; verify `cognito:groups` contains `admin`
inside Lambda (a valid JWT alone is not enough); validate all input with a schema library
(for example zod); return correct HTTP errors; avoid logging sensitive data; use
least-privilege Lambda IAM. Do not rely on hiding `/admin` UI routes.

---

## 10. Data safety

Enable DynamoDB point-in-time recovery and `RemovalPolicy.RETAIN` for tables and important buckets.

### Data model

```text
Products table: PK productId; GSI slug-index
  fields: productId, slug, name, modelId, category, shortDescription, description,
  specifications, variants, customizationOptions, imageKeys, status, isFeatured,
  sortRank, version, createdAt, updatedAt, createdBy, updatedBy
SiteConfig table: PK configKey (item "site": banner, categories, WhatsApp number, settings)
```

Do not add tables for categories, leads, inquiries, carts, orders or inventory yet.

### Optimistic locking

Every mutable record has `version`. Updates send the expected version and use a conditional
write. On failure return HTTP 409; the frontend reloads the latest record.

### Lifecycle

```text
Status: DRAFT | PUBLISHED | UNPUBLISHED | ARCHIVED
Default delete = archive (soft delete)
Hard delete: separate, deliberate, restricted, audited, optional
```

### Slugs

Generated from the name at creation. Uniqueness is checked by Lambda before publish
(a GSI does not enforce uniqueness). Immutable after publish.

---

## 11. Image upload security

```text
1. Admin selects an image.
2. Browser validates JPEG/PNG/WebP, file size and dimensions.
3. Browser resizes/compresses (card thumbnail + main image; WebP when possible).
4. Admin calls POST /admin/uploads/presign.
5. Lambda validates JWT + admin group, generates the object key server-side,
   creates a presigned POST (content-type restriction, content-length-range,
   short expiry) for incoming/{productId}/{uploadId}.
6. Browser uploads directly to the private media/data bucket.
7. Browser calls POST /admin/uploads/confirm.
8. Lambda checks the object exists, belongs to the product/upload session,
   copies it to the final versioned key media/products/{productId}/{name}-v{n}.webp,
   and returns the approved key.
9. Product create/update APIs accept only approved final keys that belong to that product.
```

Add an S3 lifecycle rule: `incoming/*` expires after 1–7 days.
Configure S3 CORS on the media/data bucket so the browser can POST from the site origin.
Never accept client-chosen object keys. SVG is not allowed.

Phase 1 variants are prepared in the browser. Later option: S3 event → image-processing Lambda.
Do not depend on Next.js image optimization.

Seeding: the Phase 2 seed script must also upload the existing mock/product images to the
media/data bucket under final keys.

---

## 12. Frontend build configuration

Public (non-secret) values:

```text
NEXT_PUBLIC_API_BASE_URL
NEXT_PUBLIC_COGNITO_USER_POOL_ID
NEXT_PUBLIC_COGNITO_CLIENT_ID
NEXT_PUBLIC_COGNITO_DOMAIN
NEXT_PUBLIC_AWS_REGION
NEXT_PUBLIC_MEDIA_BASE_URL     (same origin: /media)
NEXT_PUBLIC_DATA_BASE_URL      (same origin: /data)
```

Never expose AWS credentials, a Cognito client secret, payment/SMS/WhatsApp secrets,
DynamoDB credentials or Secrets Manager values.

Pipeline mechanism: after `cdk deploy --outputs-file cdk-outputs.json`, the workflow reads
the stack outputs (nested by stack name), exports the NEXT_PUBLIC_* variables, then builds
the frontend. A runtime `/config.json` is an alternative; if used, keep it in the
media/data bucket or exclude it from the deployment `--delete`.

---

## 13. CORS, CSP and security headers

### CORS

```text
API Gateway: allow only the site origin (plus http://localhost:3000 in dev);
             allowed headers Authorization, Content-Type.
Media/data bucket (S3 CORS): allow POST from the site origin for presigned uploads.
```

### Response headers policy (CloudFront)

```text
Strict-Transport-Security
X-Content-Type-Options: nosniff
Referrer-Policy
Permissions-Policy
Content-Security-Policy (report-only first)
```

The CSP must allow: the API domain (connect-src), the S3 upload endpoint, the Cognito
domain, WhatsApp links, and any analytics domain. Enforce only after report-only testing.

---

## 14. API protection and throttling

```text
Catalog listing served from CloudFront (not Lambda)
Input validation on every endpoint; maximum payload/query sizes
Cognito authorization on admin APIs
Lower throttle thresholds on admin and upload endpoints
CloudWatch alarms (API errors, Lambda failures, unusual invocations)
CloudFront caching
```

Reserved Lambda concurrency may be unavailable in new accounts with low quotas; do not
depend on it. Add AWS WAF rate-based rules later if abuse becomes real.

---

## 15. CI/CD

GitHub Actions with OIDC federation. No long-lived AWS keys in GitHub.
The OIDC role trust policy is scoped to this repository and specific branches/environments.
Keep the deployment role separate from Lambda runtime roles and use least privilege.

```text
Pull request / feature branch:
→ lint → type-check → unit tests → Next.js build → CDK synth

Merge to main:
→ CDK diff → CDK deploy to dev → write cdk-outputs.json
→ export NEXT_PUBLIC_* → build frontend
→ sync out/ to the FRONTEND bucket only (--delete is safe there)
→ targeted CloudFront invalidation → smoke test

Prod:
→ same pipeline for the same commit, behind a GitHub Environment manual approval
```

Invalidation: first deploy `/*`; later `/`, `/index.html`, `/404.html` (plus the shell page).
Do not invalidate `/data/*` for frontend code deployments.

Also: AWS Budget alerts at $5, $10, $25, $50 and CloudWatch log retention on all Lambdas.

---

## 16. Repository and CDK structure

```text
/
├── (existing Next.js project files)
├── api/            handlers/ services/ repositories/ schemas/
├── infra/          bin/ lib/ test/
├── docs/
├── .github/workflows/
├── PROJECT_PLAN.md
├── .env.example
└── README.md
```

One CDK app, two stacks per environment.

### FrontendStack

```text
Frontend S3 bucket
Media/data S3 bucket (+ lifecycle rule for incoming/*, S3 CORS, RETAIN)
ONE CloudFront distribution with the behaviors in section 7
OAC for both buckets
Product-shell CloudFront Function
Response headers policy
ACM certificate reference (ARN from context, prod only)
Route 53 records if applicable
Outputs: bucket names, distribution ID, site domain
```

### BackendStack (depends on FrontendStack)

```text
Cognito User Pool, app client, admin group, TOTP MFA, callback/logout URLs
API Gateway HTTP API (JWT authorizer, CORS, throttling)
Lambda functions
Products and SiteConfig tables (PITR, RETAIN)
IAM permissions on the imported media/data bucket
CloudWatch log retention and alarms
Outputs: API URL, Cognito values
```

Do not add stacks without a real deployment, ownership or lifecycle reason.

---

## 17. Implementation order

### Phase 0: audit and route spike

```text
Audit the app (sections 4 and 5). Test static export. Prototype dynamic product routes.
Choose clean slug route or query-string route. Check for a separate Emergent backend.
Scan for committed secrets (rotate anything found). Add .env.example.
Do not build AWS infrastructure until this succeeds.
```

### Phase 1: frontend hosting

```text
CDK bootstrap in dev. Budget alerts.
Build FrontendStack (both buckets, one distribution, shell function, headers).
Deploy a simple static frontend to dev; confirm UI and product-shell routing work.
Create the us-east-1 certificate once; set up the prod custom domain.
Configure GitHub OIDC (dev first, prod with approval).
```

### Phase 2: backend foundation

```text
Build BackendStack. Create Products and SiteConfig (PITR, RETAIN).
Public GET /products/{slug} and GET /site-config.
Seed DynamoDB from mock data, including uploading existing images.
Generate data/catalog-index.json. Replace mock data in the frontend.
Compute related products client-side.
```

### Phase 3: admin security and CRUD

```text
Cognito pool, admin group, first admin (CLI), TOTP MFA, hosted login with PKCE.
Protected admin read/write APIs with group checks and validation.
Optimistic locking, archive/soft delete, slug rules, index rebuild + admin action.
```

### Phase 4: image management

```text
Presigned POST, incoming prefix, confirm endpoint, copy to final versioned key,
lifecycle cleanup, S3 CORS, connect to product CRUD, test delivery and caching.
```

### Phase 5: inquiry flow

```text
WhatsApp URL generation (URL-encoded) using the number from SiteConfig:
product name, model ID, selected options, notes, product URL.
Add tracking tables only if business reporting requires them.
```

### Phase 6: production hardening

```text
Unit tests, CDK tests, cdk synth, cdk diff.
Review IAM, CORS, S3 access, CloudFront OAC, headers/CSP (move CSP to enforce).
CloudWatch alarms. Backup/restore test. Rollback and recovery docs.
Prod cutover with manual approval; sitemap if SEO matters.
```

---

## 18. Future Phase 2: e-commerce

Extend the foundation with: customer Cognito accounts (separate user pool), cart, addresses,
orders, payment-gateway order/session creation, payment webhook Lambda with signature
validation, idempotency keys, duplicate-event protection, inventory, order status
management, email/SMS/WhatsApp notifications.

Payment confirmation happens only through verified gateway webhooks/server-side validation,
never because the frontend shows a success page. Webhooks go to API Gateway + Lambda, not
Next.js route handlers.

Add only when required: SQS, Step Functions, EventBridge, InquiryEvents, Leads, a search
engine, CRM integration. Do not rebuild hosting, product APIs, image delivery or the data foundation.

---

## 19. AI implementation rules

1. Read this file before making changes.
2. Inspect the repository before changing code.
3. Use plan mode before large changes.
4. Do not modify files until the plan is approved.
5. Work in small phases only; commit small and on a branch.
6. Do not create or deploy AWS resources without explicit approval. Never deploy to prod.
7. Do not add payments, checkout, cart, orders or inventory in Phase 1.
8. Do not expose secrets. Do not expose S3 buckets publicly.
9. Do not hardcode admin credentials.
10. Do not use Secrets Manager for normal user passwords.
11. Do not use long-lived AWS keys in GitHub.
12. Do not add unnecessary AWS services.
13. Use TypeScript strict mode.
14. Add tests for important logic.
15. Run lint, type-check, build, tests, CDK synth and CDK diff after every major phase.
16. Report all changed files and all commands run.
17. Report remaining risks and known limitations.
18. Keep existing UI/design unless a change is necessary for AWS integration.
19. Ask before making architecture changes outside this plan.
20. Have security-sensitive diffs (IAM, auth, uploads, authorization) reviewed
    independently before merging.

---

## 20. First AI task

Use Plan or Ask mode. If the model struggles with the long request, send items 1–5 first,
then items 6–11.

```text
Work in Plan mode only. Do not modify any files and do not deploy AWS resources.

Read PROJECT_PLAN.md first and treat it as the project source of truth.

Inspect this existing Next.js repository and provide a concise technical audit.

Identify:

1. Next.js version.
2. App Router or Pages Router.
3. Build, lint, type-check, and test commands.
4. Whether static export is possible.
5. Every static-export blocker:
   SSR, ISR, server actions, route handlers, middleware,
   next/image optimizer, server-only cookies/headers,
   server redirects, rewrites in next.config, or Node.js-only dependencies.
   Give file paths.
6. Existing mock product data and localStorage usage.
7. Existing admin login/authentication implementation and security risks.
8. Existing environment variables, committed .env files and potential secret exposure.
9. Existing product/detail routes and whether newly created product slugs
   can work through a static application shell.
10. Whether a separate backend exists (for example FastAPI/MongoDB) and how images
    are stored today.
11. Exact recommended minimal changes required before Phase 1 hosting.
12. A detailed Phase 0 routing prototype plan, including direct visit,
    refresh, newly-added slug, unknown-slug, and back/forward testing.

If you are unsure about something, say so instead of guessing.
Do not change code.
Do not create infrastructure.
Stop after the audit report.
```