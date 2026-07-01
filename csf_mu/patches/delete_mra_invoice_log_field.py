import frappe

def execute():
	if frappe.db.exists("Custom Field", "Sales Invoice-mra_invoice_log"):
		frappe.delete_doc("Custom Field", "Sales Invoice-mra_invoice_log", ignore_permissions=True)
