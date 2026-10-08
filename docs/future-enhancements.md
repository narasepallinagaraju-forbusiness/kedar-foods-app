# Future enhancements (not scheduled)

Ideas the owner has parked so they are not forgotten. Move an item into a phase
plan when it is approved.

| Item | Why it was parked | Notes |
|---|---|---|
| "Rebuild public list" button on the admin dashboard | The public list already refreshes on every save, so it is not needed now | The backend route `POST /admin/catalog-index/rebuild` already exists; a persistent button is a small frontend change. It currently appears only after a failed refresh. |
| Cognito login with MFA instead of the shared admin key and `admin` / `kedar123` | Planned before public launch | See `PROJECT_PLAN.md` section 8. |
| Custom domain (Route 53) and certificate | Domain bought; attach during hardening | CDK already supports `domainName` and `certificateArn`; also update `siteOrigin`. |
| CSP from report-only to enforcing | Needs report-only testing first | Phase 6. |
| Automatic cleanup of old picture versions | Costs cents; low priority | Needs a safe "not referenced" check. |
| AWS Budget alert | Cost safety | Billing > Budgets, e.g. $5 per month with email. |
| Remove unused old files (`useProducts.js`, `useSiteOffer.js`, admin parts of `data.js`) | Left from the mock-data days | Check nothing imports them first. |
| Decide the home page "Enquire on WhatsApp" buttons | Product page button was removed; home page still has two | Phase 5. |
| CloudWatch alarms, backup/restore test, sitemap | Production hardening | Phase 6. |
