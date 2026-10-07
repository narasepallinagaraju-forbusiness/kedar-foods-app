# Phase 2a: BackendStack read path

## Scope and stack setup

- Add `BackendStack` to the existing Python CDK app. Name it
  `kedar-foods-app-{env}-backend`; use the existing `env` context, default
  `prod`, and region `ap-south-1`. Enable termination protection in prod.
- Tag it consistently with the frontend stack:
  `Project=kedar-foods-app`, `Env={env}`.
- Name configurable resources with the same prefix:
  `kedar-foods-app-{env}-<purpose>`.
- Update the CDK app to create both stacks and connect the backend to the
  frontend distribution domain.

## DynamoDB tables

Create exactly two tables:

| Table | Key and index | Protection |
|---|---|---|
| Products | Partition key `productId`; GSI `slug-index`, partition key `slug`, projection `ALL` | On-demand billing, point-in-time recovery, `RETAIN`, deletion protection in prod |
| SiteConfig | Partition key `configKey` | On-demand billing, point-in-time recovery, `RETAIN`, deletion protection in prod |

Use the requested physical names:
`kedar-foods-app-{env}-products` and
`kedar-foods-app-{env}-site-config`.

## Public HTTP API and CORS

Create an API Gateway v2 HTTP API with just these unauthenticated GET routes:

- `GET /products/{slug}`
- `GET /site-config`

Set default throttling to **20 requests/second with a burst limit of 40**.

Allow CORS origins only for:

- The `https://` CloudFront distribution domain obtained from `FrontendStack`.
- `http://localhost:3000`.
- The optional custom domain supplied through context, as
  `https://<domain>`.

Do not use wildcard origins. Add the custom origin only when a custom domain
is configured.

## Lambda handlers

Create two Python 3.12 Lambda functions under `api/`, both using arm64,
128 MB memory, a 5-second timeout, and 30-day CloudWatch log retention. Package
each function with `Code.from_asset` pointed at its handler directory, excluding
tests and `__pycache__`; no dependency bundling is needed.

- **Product detail handler:** lowercase the incoming slug, validate it against
  `^[a-z0-9]+(-[a-z0-9]+)*$`, then query `slug-index`. Use the allowed status
  constant `DRAFT`, `PUBLISHED`, `UNPUBLISHED`, `ARCHIVED`; return 404 with
  `{"error":"not_found"}` for an invalid slug, missing product, or any status
  other than `PUBLISHED`, without distinguishing these cases in the response.
  Return only this shape:

  ```json
  {
    "id": "value from productId",
    "sku": "value",
    "slug": "value",
    "name": "value",
    "brand": "value",
    "category": "value",
    "businessType": [],
    "quantities": [],
    "description": "value",
    "image": {
      "card": "media/products/prod_101/card-v1.webp",
      "main": "media/products/prod_101/main-v1.webp"
    },
    "updatedAt": "value"
  }
  ```

  Optional/missing fields must be omitted or safely defaulted, never copied
  from arbitrary raw item keys. Image values are final S3 keys already
  prefixed with `media/`; document that the frontend builds the URL as
  `"/" + key`. Never return `status`, `version`, `createdBy`, `updatedBy`, or
  any other field outside this allowlist.
- **Site-config handler:** read the `site` config record. If absent, return
  404 with `{"error":"not_found"}`. The only public response shape is:

  ```json
  {
    "offerBanner": {
      "enabled": true,
      "text": "value",
      "link": "value"
    },
    "categories": [
      {
        "id": "value",
        "name": "value",
        "slug": "value",
        "sortOrder": 0,
        "isActive": true
      }
    ],
    "whatsapp": {
      "number": "value",
      "messageTemplate": "value"
    }
  }
  ```

  Only those fields may be returned. Within categories, allow only `id`,
  `name`, `slug`, `sortOrder`, and `isActive`. Missing optional fields may be
  omitted or defaulted, but must never be passed through from the raw item.

Both handlers must return `Content-Type: application/json` and
`X-Content-Type-Options: nosniff`. Successful 200 responses use
`Cache-Control: public, max-age=30`; all error responses use
`Cache-Control: no-store` and generic error bodies. Never log the full Lambda
event or request headers.

Both handlers use boto3 only, with table access injected so unit tests can
pass a fake table. Construct each boto3 table object in a small factory
function, not at module import time, so unit tests require no AWS configuration,
credentials, or region. Dev-only type stubs for mypy are allowed; no
third-party runtime packages are allowed.

Use explicit IAM policy statements; do not use `grant_read_data`.

- Product handler: `dynamodb:Query` only, scoped to the Products
  `slug-index` ARN:
  `arn:...:table/<products>/index/slug-index`.
- Site-config handler: `dynamodb:GetItem` only, scoped to the SiteConfig table
  ARN.

IAM tests inspect inline policies only and assert exact action lists. The
managed basic-execution/logging policy is out of scope for these assertions.
Do not allow wildcard IAM resources or any write actions.

## CloudFront domain reference and deployment order

`BackendStack` needs the frontend's generated CloudFront domain for API CORS.
The current `FrontendStack` keeps the distribution as a local variable, so
implementation should expose its distribution domain as a stack property,
then pass that value to `BackendStack`. Referencing it across stacks creates a
CDK/CloudFormation cross-stack dependency.

Deploy order is therefore **FrontendStack first, then BackendStack**. In the
shared CDK app, synth can include both stacks; CDK will represent the
dependency, and deployment should respect it. The optional custom domain is
supplied through context and added as a separate allowed CORS origin.

## Outputs

BackendStack outputs:

- `ApiUrl`
- Products table name
- SiteConfig table name

## Tests

- **CDK assertion tests:** both tables and their fixed names, billing mode,
  PITR, retention and prod deletion protection; Products GSI key/projection;
  exactly the two GET routes; exact CORS origins; Lambda Python runtime,
  arm64 architecture, memory, timeout, asset packaging exclusions, and log
  retention. Inspect inline IAM policies only and assert exact action lists
  (`dynamodb:Query` for the slug-index ARN; `dynamodb:GetItem` for the
  SiteConfig table ARN), no wildcard resources, and no write actions.
- **Handler unit tests:** lowercase and invalid slug behavior; generic 404
  for invalid, missing, and non-published products; product allowlist and
  response headers/cache controls; missing SiteConfig 404; exact site-config
  shape and allowlist; generic errors and no-store cache control. Use fake
  table objects and verify table construction is deferred to the factory;
  tests require no AWS configuration, credentials, region, or AWS calls.

## Files expected

- Update `infra/app.py` to instantiate both stacks and connect their
  dependency.
- Update `infra/frontend_stack.py` only to expose the distribution domain for
  the cross-stack reference.
- Create `infra/backend_stack.py`.
- Create CDK tests, likely `infra/tests/test_backend_stack.py`.
- Create boto3-only handlers and supporting modules under `api/handlers/`
  (and small repository/helper modules if needed).
- Create handler unit tests under `api/tests/`.
- Update `infra/pyproject.toml` only if needed to include API code/tests in
  lint, type-check, or test configuration.

## Assumptions and risks

- Section 21's product model uses `productId` and `image {card, main}`, while
  its public detail contract names the API field `id` and says "image keys."
  Implementation should map `productId` to `id` and return only final public
  image keys; confirm the precise image response shape against frontend usage.
- Product detail keys must be sourced from the section 21 fields and mapped
  to the exact API response shape above. The frontend constructs image URLs as
  `"/" + key`; keys must already have the `media/` prefix.
- SiteConfig response fields and nested fields are explicitly limited to the
  shape above. Missing optional fields must be omitted or defaulted, not passed
  through from DynamoDB.
- A slug GSI does not enforce uniqueness. This read path will return one
  matching result; uniqueness remains a separate write-path concern.
- Cross-stack reference couples the stacks' deployment lifecycle and requires
  the frontend stack to exist first. Any FrontendStack change that replaces
  the distribution is blocked until BackendStack no longer references it.
- Fixed table names prevent easy parallel deployments into the same account
  if names are reused; the `{env}` suffix distinguishes prod and dev. Combined
  with `RETAIN`, deleting the stack leaves the tables behind, and they cannot
  be recreated under the same names until those retained tables are removed
  manually.

## Explicitly out of scope

No seed script, catalog index or its regeneration, admin APIs, Cognito, or
frontend changes are included in Phase 2a.

There is no seed data in this step. The seed script is a separate next step,
Phase 2b. After deployment, checks are limited to 404 responses, CORS
preflight/headers, and throttling until seed data exists.

## Validation commands

From the repository root, with the infra virtual environment active:

```powershell
.\infra\.venv\Scripts\ruff.exe check infra api
.\infra\.venv\Scripts\mypy.exe infra api
.\infra\.venv\Scripts\pytest.exe infra\tests api\tests
```

Then synthesize from `infra/` with the virtual environment available on `PATH`:

```powershell
Push-Location infra
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
cdk synth -c env=prod
cdk synth -c env=dev
Pop-Location
```

Validation in this step uses `cdk synth` only. No `cdk diff`, deploy,
bootstrap, or AWS-backed tests are part of validation.

For a later, separately approved deployment, review `cdk diff` first, then
deploy prod with:

```powershell
cd infra
cdk diff kedar-foods-app-prod-backend -c env=prod
cdk deploy kedar-foods-app-prod-backend -c env=prod
```

With no seed data yet, post-deployment checks are limited to 404 responses,
CORS preflight and headers, and throttling. Creating and loading seed data is
the separate Phase 2b step.
