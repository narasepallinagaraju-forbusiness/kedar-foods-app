# FrontendStack Scaffold Plan

**Status:** Implemented; local validation passed.

## Scope

Create a Python AWS CDK v2 scaffold under `infra/` with one
`Frontend-{env}` stack only. The context defaults to `prod`, accepts only
`prod` or `dev`, and deploy-region configuration is `ap-south-1`. No
BackendStack, bootstrap, deploy, or AWS API calls are in scope.

## Files to create or update

```text
infra/
  app.py
  cdk.json
  requirements.txt
  requirements-dev.txt
  pyproject.toml
  frontend_stack.py
  tests/
    test_frontend_stack.py
package.json                         (add routing and infra-test scripts)
.gitignore                           (ignore infra/.venv, infra/cdk.out,
                                      infra/**/__pycache__, infra/.pytest_cache,
                                      infra/.mypy_cache, infra/.ruff_cache)
```

Keep the existing root Next.js project and the Phase 0 routing function as-is.
CDK will load `scripts/cloudfront-routing-function.js` using
`FunctionCode.from_file()` with a path resolved from `frontend_stack.py`'s
`__file__`, not the shell's working directory.

## Stack design

- Use Python 3.12, a recent pinned `aws-cdk-lib` 2.x version with an upper
  bound below 3, and `constructs`; type-hint new Python code.
- `infra/app.py` reads context `env` (default `prod`), rejects values other
  than `prod` and `dev` clearly, and creates only
  `kedar-foods-app-{env}-frontend` with
  `Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
  region="ap-south-1")`. Add `Project` and `Env` tags. Enable termination
  protection for the prod stack.
- Name the frontend and media/data S3 buckets
  `kedar-foods-app-{env}-frontend` and
  `kedar-foods-app-{env}-data-media`; block public access, enforce SSL, and
  use `RemovalPolicy.RETAIN`. These exact bucket names are globally unique
  across AWS and may be unavailable if already claimed.
- Add a 7-day lifecycle expiration for `incoming/` on the media/data bucket.
- Add optional context `siteOrigin`. If absent, configure no S3 CORS rule. If
  present, require an `https://` origin and use that exact origin for POST.
  Never configure a wildcard CORS origin.
- Create one Price Class 200 CloudFront distribution with HTTPS-only viewer
  protocol, Brotli/gzip compression, both origins using OAC, and:
  `/data/*` and `/media/*` to media/data; `/_next/*` and default to frontend.
- Define cache keys with no cookies, headers, or query strings. Use min/default/
  max TTLs of 0/60/300 seconds for `/data/*` and default HTML; use one year for
  min/default/max TTLs on `/media/*` and `/_next/*`.
- Attach the existing routing CloudFront Function to the default behavior at
  viewer request, explicitly set `FunctionRuntime.JS_2_0`, and load its source
  with `FunctionCode.from_file()`. Set frontend-origin 403/404 custom errors to
  `/404.html`, response code 404, error TTL 10 seconds; never use index or
  product shell as an error fallback. Document that custom error responses are
  distribution-wide and therefore also apply to missing `/data/*` and
  `/media/*` objects.
- Add a response headers policy with HSTS max-age 31536000 (without
  `includeSubDomains` or `preload`), `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, Referrer-Policy, Permissions-Policy, and CSP in
  report-only mode.
- Name CloudFront cache policies, OACs, the response headers policy, and
  routing function with the `kedar-foods-app-{env}-<purpose>` prefix.
  CloudFront distribution IDs remain AWS-generated.
- `domainName` and `certificateArn` must either both be supplied or both be
  absent; supplying exactly one fails synthesis with a clear error. A supplied
  certificate ARN must contain `:us-east-1:`. Reject both values when
  `env=dev`. Do not create ACM resources.
- Output generated frontend bucket name, media/data bucket name, distribution
  ID, and site domain.
- Use CDK assertion tests for bucket privacy/block-public-access, OAC,
  behaviors/path patterns, price class, RETAIN, lifecycle, custom errors and
  TTL, and equality of deployed function source to the checked-in routing file.
  Also test: no wildcard CORS origin, no bucket policy statement with
  `Principal: "*"`, SSL enforcement, unmatched domain/certificate inputs,
  dev with domain/certificate inputs, and rejection of an invalid `env`.

## Local validation

From PowerShell at the repository root, install the declared infra development
dependencies into `infra/.venv`, then run:

```powershell
.\infra\.venv\Scripts\ruff.exe check infra
.\infra\.venv\Scripts\mypy.exe infra
.\infra\.venv\Scripts\pytest.exe infra\tests
node scripts/test-routing-function.mjs
```

The routing test requires the existing `out/` folder. If it is absent, stop
and report that fact; do not run a build. After these checks, run the following
three synthesis contexts from `infra/`, with its virtual environment available
on `PATH`:

```powershell
cdk synth -c env=prod
cdk synth -c env=prod -c domainName=example.com `
  -c certificateArn=arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000
cdk synth -c env=dev
```

Do not commit, build, make AWS calls, bootstrap, or deploy. No frontend upload,
`BucketDeployment`, or changes to existing Next.js/admin code are in scope.
`Permissions-Policy` and report-only CSP values are conservative explicit
policy strings. Root `package.json` adds scripts for the routing test and
infra pytest suite.
