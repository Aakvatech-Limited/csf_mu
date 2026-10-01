import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data, None, None, get_report_summary(data)


def get_columns():
	return [
		{"label": "Sales Invoice", "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 170},
		{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 170},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 170},
		{"label": "Invoice Type", "fieldname": "mra_invoice_type_desc", "fieldtype": "Data", "width": 95},
		{"label": "MRA Status", "fieldname": "mra_status", "fieldtype": "Data", "width": 105},
		{"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
		{"label": "IRN", "fieldname": "mra_uuid", "fieldtype": "Data", "width": 180},
		{"label": "Request Datetime", "fieldname": "request_datetime", "fieldtype": "Data", "width": 160},
		{"label": "Response Datetime", "fieldname": "response_datetime", "fieldtype": "Data", "width": 160},
		{"label": "Error Summary", "fieldname": "error_summary", "fieldtype": "Small Text", "width": 320},
	]


def get_data(filters):
	conditions = ["si.docstatus = 1", "COALESCE(si.mra_status, '') != ''"]
	values = {}

	if filters.get("company"):
		conditions.append("si.company = %(company)s")
		values["company"] = filters.company

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	if filters.get("status"):
		conditions.append("si.mra_status = %(status)s")
		values["status"] = filters.status

	return frappe.db.sql(
		"""
		SELECT
			si.name AS sales_invoice,
			si.posting_date,
			si.company,
			si.customer,
			si.mra_invoice_type_desc,
			si.mra_status,
			si.grand_total,
			si.currency,
			COALESCE(log.mra_uuid, si.mra_uuid) AS mra_uuid,
			log.request_datetime,
			log.response_datetime,
			log.error_summary
		FROM `tabSales Invoice` si
		LEFT JOIN `tabMRA Einvoice Log` log
			ON log.sales_invoice = si.name
		WHERE {conditions}
		ORDER BY si.posting_date DESC, si.name DESC
		""".format(conditions=" AND ".join(conditions)),
		values,
		as_dict=True,
	)


def get_report_summary(data):
	total = len(data)
	success = 0
	errors = 0
	pending = 0

	for row in data:
		status = (row.get("mra_status") or "").upper()
		if status == "SUCCESS":
			success += 1
		elif status == "PENDING":
			pending += 1
		elif status in ("ERROR", "ERRORS", "HAS_ERRORS"):
			errors += 1

	success_rate = flt(success * 100 / total, 2) if total else 0

	return [
		{"value": total, "indicator": "Blue", "label": "MRA Invoices", "datatype": "Int"},
		{"value": success, "indicator": "Green", "label": "Success", "datatype": "Int"},
		{"value": errors, "indicator": "Red", "label": "Errors", "datatype": "Int"},
		{"value": pending, "indicator": "Orange", "label": "Pending", "datatype": "Int"},
		{"value": success_rate, "indicator": "Green", "label": "Success Rate", "datatype": "Percent"},
	]
