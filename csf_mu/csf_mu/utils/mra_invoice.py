import frappe


def create_invoice_log(doc, method=None):
	existing = frappe.db.exists("MRA Invoice Log", {"sales_invoice": doc.name})
	if existing:
		return

	log = frappe.new_doc("MRA Invoice Log")
	log.sales_invoice = doc.name
	log.company = doc.company
	log.status = "PENDING"
	log.invoice_identifier = doc.name
	log.request_id = doc.name
	log.request_datetime = frappe.utils.now_datetime()
	log.insert(ignore_permissions=True)

	doc.db_set("mra_invoice_log", log.name, update_modified=False)
	doc.db_set("mra_status", "PENDING", update_modified=False)
