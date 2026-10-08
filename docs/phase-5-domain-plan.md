# Phase 5: Custom domain (kedharfoods.in) plan

Status: PLAN ONLY. No code changed, no AWS calls made. Awaiting owner approval.

## 1. Goal
Serve the site at `https://kedharfoods.in`, with `https://www.kedharfoods.in`
redirecting to it. The old CloudFront address keeps working during the move.
Show the brand as **Kedhar Foods** in the UI (internal names such as stack names,
buckets and folders stay `kedar-...`; renaming them would recreate resources).

## 2. Owner tasks (AWS console, I cannot do these)
1. Buy `kedharfoods.in` in Route 53 (Registered domains). Verify the email AWS sends.
   `.in` can need extra details and a wait of minutes to hours.
2. Confirm a **public hosted zone** for the domain exists in Route 53 (created
   automatically on purchase). Note its Hosted zone ID.
3. Switch the console region to **us-east-1 (N. Virginia)**, open Certificate
   Manager, request a public certificate for `kedharfoods.in` and
   `www.kedharfoods.in`, DNS validation, then click "Create records in Route 53".
   Wait for status Issued. Send me the certificate ARN (it contains `:us-east-1:`).
   (Free. If you prefer, I can run this with the CLI after your approval.)

## 3. Code changes (local first, tests included)
| # | Change | File |
|---|--------|------|
| 1 | Add `www.<domain>` as a second CloudFront alias when a domain is set | `infra/frontend_stack.py` |
| 2 | Redirect `www` to the apex with a 301 in the existing CloudFront Function (keeps path and query) | `infra/` function source + `scripts/test-routing-function.mjs` |
| 3 | New optional context `hostedZoneId`; when given with the domain, create Route 53 A and AAAA alias records for apex and `www` pointing at the distribution. Without it, no DNS records are made | `infra/frontend_stack.py` |
| 4 | Validation: `hostedZoneId` requires `domainName`; domain must look like a bare hostname (no scheme, no slash, no `www.`) | `infra/frontend_stack.py` |
| 5 | Backend: API CORS already allows `https://<domain>`; add a test that apex is allowed and the CloudFront URL still is | `infra/tests` |
| 6 | UI brand text "Kedar Foods" to "Kedhar Foods" (Header, Footer, layout metadata, admin pages, WhatsApp message defaults, product page title) | `components/`, `app/`, `scripts/product-shell.js` |
| 7 | Docs: runbook with rollback | `docs/` |

Not changed: stack names, bucket names, SSM parameter, API.

WhatsApp message text lives in the saved site config in DynamoDB too. If the stored
messages say "Kedar Foods", you edit them in the DB or I change them in a
step you approve (admin write, no CDK).

## 4. Deploy sequence (each AWS write needs your approval)
1. `cdk synth` for dev, prod, and prod with domain + certificate + hostedZoneId.
2. `cdk diff` frontend stack. Expected: aliases + certificate on the distribution,
   function code update, 4 Route 53 records. No bucket or table replacement.
3. Deploy frontend stack (with `-c domainName=kedharfoods.in -c certificateArn=...
   -c hostedZoneId=...`), then the backend stack with the same domainName.
   **Always pass the same context on every future deploy**, or the alias is removed.
4. Rebuild and redeploy the frontend (brand text), invalidate CloudFront.
5. Verify: `https://kedharfoods.in`, `https://www.kedharfoods.in` (redirects),
   `/catalogue`, a product page, `/admin` login, an image upload, the CSV import
   (these exercise the API CORS), and the old CloudFront URL.

## 5. Cost
Domain about 1-3 USD/year (`.in`), hosted zone 0.50 USD/month, DNS queries
about 0.40 USD per million, certificate free. No CloudFront change.

## 6. Risks and rollback
- DNS and certificate delays: only affects the new name; the old URL keeps working.
- Forgetting the context on a later deploy removes the alias. Mitigation: a
  `deploy` note in the runbook, and a saved `cdk.context`-style command in docs.
- The CloudFront distribution `Aliases` fail if the domain is already attached to
  another distribution (not the case here).
- Rollback: redeploy without `domainName`, `certificateArn` and `hostedZoneId`;
  the old CloudFront URL is unaffected throughout.
- Admin key and login are unchanged. Cognito stays deferred (see
  `future-enhancements.md`); note the admin pages will now also be reachable on
  the public domain.

## 7. Open questions
1. Redirect direction: apex is canonical and `www` redirects (recommended). OK?
2. Buy the cert and DNS records through the console (you) or CLI (me, with approval)?
3. Rename the brand text to "Kedhar Foods" in this phase (recommended)?
