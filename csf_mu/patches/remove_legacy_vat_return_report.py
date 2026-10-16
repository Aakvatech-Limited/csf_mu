"""Replace the old query report with the transaction-backed VAT Return Filing."""

import frappe


def execute():
	if frappe.db.exists("Report", "VAT Return"):
		frappe.delete_doc("Report", "VAT Return", ignore_permissions=True, force=True)
