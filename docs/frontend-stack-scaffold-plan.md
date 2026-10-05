# FrontendStack Scaffold Plan

**Status:** Proposed; no infrastructure code or AWS resources created.

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
                                      infra/**/__pycache__)
```

Keep the existing root Next.js project and the Phase 0 routing function as-is.
CDK will load `scripts/cloudfront-routing-function.js` using
`FunctionCode.from_file()` with a path resolved from `frontend_stack.py`'s
`__file__`, not the shell's working directory.

## Stack design

- Use Python 3.12, `aws-cdk-lib`, and `constructs`; type-hint new Python code.
- `infra/app.py` reads context `env` (default `prod`), rejects values other
  than `prod` and `dev` clearly, and creates only `Frontend-prod` or
  `Frontend-dev` in `ap-south-1`.
- Create frontend and media/data S3 buckets with generated names, all public
  access blocked, SSL enforced, and `RemovalPolicy.RETAIN`.
- Add a 7-day lifecycle expiration for `incoming/` on the media/data bucket.
- Add S3 POST CORS. Assumption for review: prod uses the configured site domain
  as the exact origin; dev allows `https://*.cloudfront.net` because the
  generated distribution hostname is not available as a bucket CORS value
  without introducing a bucket/distribution dependency cycle. This dev-only
  wildcard permits other CloudFront origins too; if unacceptable, use an
  explicit post-deployment CORS update or another approved design.
- Create one Price Class 200 CloudFront distribution with HTTPS-only viewer
  protocol, Brotli/gzip compression, both origins using OAC, and:
  `/data/*` and `/media/*` to media/data; `/_next/*` and default to frontend.
- Use a short origin-cache-respecting policy for `/data/*`, long-lived policies
  for `/media/*` and `/_next/*`, and short TTL for HTML/default requests.
- Attach the existing routing CloudFront Function to the default behavior at
  viewer request. Set frontend-origin 403/404 custom errors to `/404.html`,
  response code 404, error TTL 10 seconds; never use index or product shell as
  an error fallback.
- Add a response headers policy for HSTS, `nosniff`, Referrer-Policy,
  Permissions-Policy, and report-only CSP.
- Use optional `domainName` and `certificateArn` context values only for prod;
  dev uses the generated CloudFront domain. Do not create ACM resources.
- Output generated frontend bucket name, media/data bucket name, distribution
  ID, and site domain.
- Use CDK assertion tests for bucket privacy/block-public-access, OAC,
  behaviors/path patterns, price class, RETAIN, lifecycle, custom errors and
  TTL, and equality of deployed function source to the checked-in routing file.

## Local setup and validation after approval

From PowerShell at the repository root:

```powershell
py -3.12 -m venv infra/.venv
.\infra\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r infra\requirements-dev.txt
npm install -g aws-cdk
npm run build
node scripts/test-routing-function.mjs
ruff check infra
mypy infra
pytest infra\tests
cd infra
cdk synth -c env=dev
```

Installing the CDK CLI is needed only if `cdk --version` is unavailable. No
bootstrap or deploy command will be run.

## Assumptions / review points

- `dev` S3 CORS uses an HTTPS CloudFront-host wildcard to avoid a dependency
  cycle; `prod` uses the configured custom site domain. Confirm this is
  acceptable before implementation.
- Custom domain and certificate are supplied together for prod; if either is
  absent, use the default CloudFront domain rather than creating ACM resources.
- `Permissions-Policy` and report-only CSP values will be conservative explicit
  policy strings; no application changes or admin-route changes are planned.
- Root `package.json` changes will add only scripts for the existing routing
  test and the infra pytest suite.
- Existing unrelated worktree changes, including the current `PROJECT_PLAN.md`
  modification, will be preserved.
