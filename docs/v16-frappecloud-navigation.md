# CSF MU v16 navigation and Frappe Cloud readiness

This branch targets `version-16-hotfix` (test branch), not production.

## Delivered
- Declares Python 3.14 runtime and external Python requirements (`requests`, `cryptography`) in `pyproject.toml`; ERPNext remains a bench-managed app dependency.
- Registers the CSF MU app entry on Frappe Desktop and declares `required_apps = ["erpnext"]`.
- Ships a native Frappe v16 Dock and Sidebar for the existing CSF MU module.
- Curates Home, VAT Operations, MRA Operations, Master Data and Settings links to existing DocTypes, reports, dashboards and the existing `MRA Integration` Workspace.
- Preserves the pre-existing Workspace dashboard blocks, eight number cards, five charts, and two dashboard documents instead of duplicating them.
- Updates CI from Frappe/ERPNext 15 to v16 on Python 3.14, Node 24 and MariaDB 11.8.
- Restores two dangling event-hook targets: sales-invoice VAT claim locking and default purchase-invoice VAT claim dates, previously preventing clean hook validation.

## Review/test on development site
1. Install/migrate on Frappe + ERPNext version-16.
2. Confirm sidebar/Dock imports and links, Desktop route, normal-user permission filtering, dashboards/cards/charts.
3. Confirm submitted VAT invoice claim locks and purchase item claim date defaults.
4. Confirm workspace filters and currency calculations against each company's settings; these existing analytics are not rewritten in this PR.
5. Review CI and Frappe Cloud build before merging; no deployed-site validation has yet been performed.

## Scope note
The v16 Dock/Sidebar definitions are based on upstream v16 JSON field schemas and have not been exported from a live development site. Existing dashboards and cards are reused, not newly recalculated.
