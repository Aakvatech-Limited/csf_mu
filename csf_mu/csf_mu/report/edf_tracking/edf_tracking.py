import frappe
from frappe import _
from frappe.utils import flt

import erpnext


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	currency = erpnext.get_company_currency(filters.company)
	columns = get_columns()
	data = get_data(filters, currency)

	return columns, data


def validate_filters(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	if not filters.get("company"):
		frappe.throw(_("Company is required."))


def get_columns():
	return [
		{
			"label": _("Employee ID"),
			"fieldname": "employee_id",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
		{
			"label": _("Employee Name"),
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": _("Department"),
			"fieldname": "department",
			"fieldtype": "Link",
			"options": "Department",
			"width": 160,
		},
		{
			"label": _("Designation"),
			"fieldname": "designation",
			"fieldtype": "Link",
			"options": "Designation",
			"width": 160,
		},
		{
			"label": _("Total Emoluments"),
			"fieldname": "total_emoluments",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 170,
		},
		{
			"label": _("EDF Rate"),
			"fieldname": "edf_rate",
			"fieldtype": "Percent",
			"width": 120,
		},
		{
			"label": _("EDF Contribution"),
			"fieldname": "edf_contribution",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 170,
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Data",
			"hidden": 1,
		},
	]


def get_data(filters, currency):
	rate_field = get_employee_edf_rate_field()
	rate_expr = f"COALESCE(e.`{rate_field}`, 0)" if rate_field else "0"
	rate_group_by = f", e.`{rate_field}`" if rate_field else ""

	conditions = ["ss.docstatus = 1", "ss.company = %(company)s", "ss.start_date >= %(from_date)s", "ss.end_date <= %(to_date)s"]

	if filters.get("employee"):
		conditions.append("ss.employee = %(employee)s")
	if filters.get("department"):
		conditions.append("ss.department = %(department)s")
	if filters.get("designation"):
		conditions.append("ss.designation = %(designation)s")

	query = f"""
		SELECT
			ss.employee AS employee_id,
			ss.employee_name,
			ss.department,
			ss.designation,
			SUM(ss.gross_pay) AS total_emoluments,
			{rate_expr} AS edf_rate
		FROM `tabSalary Slip` ss
		LEFT JOIN `tabEmployee` e ON e.name = ss.employee
		WHERE {' AND '.join(conditions)}
		GROUP BY ss.employee, ss.employee_name, ss.department, ss.designation{rate_group_by}
		ORDER BY ss.employee
	"""

	rows = frappe.db.sql(query, filters, as_dict=True)

	for row in rows:
		row.total_emoluments = flt(row.total_emoluments)
		row.edf_rate = flt(row.edf_rate)
		row.edf_contribution = flt(row.total_emoluments * row.edf_rate / 100)
		row.currency = currency

	return rows


def get_employee_edf_rate_field():
	candidates = [
		"edf_rate",
		"custom_edf_rate",
		"edf_contribution_rate",
		"custom_edf_contribution_rate",
	]

	for fieldname in candidates:
		if frappe.db.has_column("Employee", fieldname):
			return fieldname

	return None
