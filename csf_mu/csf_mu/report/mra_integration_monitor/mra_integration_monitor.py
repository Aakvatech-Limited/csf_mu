import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data, None, None, get_report_summary(data)


def get_columns():
	return [
		{
			"label": "Sales Invoice",
			"fieldname": "sales_invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 170,
		},
		{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
		{
			"label": "Company",
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 170,
		},
		{
			"label": "Customer",
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 170,
		},
		{
			"label": "Invoice Type",
			"fieldname": "mra_invoice_type_desc",
			"fieldtype": "Data",
			"width": 95,
		},
		{"label": "MRA Status", "fieldname": "mra_status", "fieldtype": "Data", "width": 105},
		{
			"label": "Grand Total",
			"fieldname": "grand_total",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": "Currency",
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 80,
		},
		{"label": "IRN", "fieldname": "mra_uuid", "fieldtype": "Data", "width": 180},
		{
			"label": "Request Datetime",
			"fieldname": "request_datetime",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": "Response Datetime",
			"fieldname": "response_datetime",
			"fieldtype": "Data",
			"width": 160,
		},
		{"label": "Error Summary", "fieldname": "error_summary", "fieldtype": "Data", "width": 320},
	]


def get_data(filters):
	invoice_filters = {
		"docstatus": 1,
		"mra_status": ["!=", ""],
	}

	if filters.get("company"):
		invoice_filters["company"] = filters.company

	if filters.get("from_date") and filters.get("to_date"):
		invoice_filters["posting_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		invoice_filters["posting_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		invoice_filters["posting_date"] = ["<=", filters.to_date]

	if filters.get("status"):
		invoice_filters["mra_status"] = filters.status

	invoices = frappe.get_list(
		"Sales Invoice",
		filters=invoice_filters,
		fields=[
			"name",
			"posting_date",
			"company",
			"customer",
			"mra_invoice_type_desc",
			"mra_status",
			"grand_total",
			"currency",
			"mra_uuid",
		],
		order_by="posting_date desc, name desc",
	)

	if not invoices:
		return []

	invoice_names = [row.name for row in invoices]
	logs = frappe.get_all(
		"MRA Einvoice Log",
		filters={"sales_invoice": ["in", invoice_names]},
		fields=[
			"sales_invoice",
			"mra_uuid",
			"request_datetime",
			"response_datetime",
			"error_summary",
		],
	)
	log_by_invoice = {row.sales_invoice: row for row in logs}

	data = []
	for invoice in invoices:
		log = log_by_invoice.get(invoice.name) or {}
		data.append(
			{
				"sales_invoice": invoice.name,
				"posting_date": invoice.posting_date,
				"company": invoice.company,
				"customer": invoice.customer,
				"mra_invoice_type_desc": invoice.mra_invoice_type_desc,
				"mra_status": invoice.mra_status,
				"grand_total": invoice.grand_total,
				"currency": invoice.currency,
				"mra_uuid": log.get("mra_uuid") or invoice.mra_uuid,
				"request_datetime": log.get("request_datetime"),
				"response_datetime": log.get("response_datetime"),
				"error_summary": log.get("error_summary"),
			}
		)

	return data


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
		{
			"value": success_rate,
			"indicator": "Green",
			"label": "Success Rate",
			"datatype": "Percent",
		},
	]
