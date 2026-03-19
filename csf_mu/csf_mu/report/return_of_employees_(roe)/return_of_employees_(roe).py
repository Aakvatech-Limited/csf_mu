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
			"label": _("SN"),
			"fieldname": "sn",
			"fieldtype": "Int",
			"width": 70,
		},
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
			"label": _("Total Gross Pay"),
			"fieldname": "total_gross_pay",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 170,
		},
		{
			"label": _("Total PAYE"),
			"fieldname": "total_paye",
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
	paye_components = get_paye_components()
	paye_components_sql = ", ".join(frappe.db.escape(component) for component in paye_components)

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
			SUM(ss.gross_pay) AS total_gross_pay,
			SUM(COALESCE(sd.amount, 0)) AS total_paye
		FROM `tabSalary Slip` ss
		LEFT JOIN `tabSalary Detail` sd
			ON sd.parent = ss.name
			AND sd.parenttype = 'Salary Slip'
			AND sd.parentfield = 'deductions'
			AND sd.salary_component IN ({paye_components_sql})
		WHERE {' AND '.join(conditions)}
		GROUP BY ss.employee, ss.employee_name, ss.department, ss.designation
		ORDER BY ss.employee
	"""

	rows = frappe.db.sql(query, filters, as_dict=True)

	for index, row in enumerate(rows, start=1):
		row.sn = index
		row.total_gross_pay = flt(row.total_gross_pay)
		row.total_paye = flt(row.total_paye)
		row.currency = currency

	return rows


def get_paye_components():
	components = frappe.get_all(
		"Salary Component",
		filters={"type": "Deduction"},
		pluck="name",
	)

	paye_components = [component for component in components if "PAYE" in component.upper()]
	if paye_components:
		return paye_components

	return ["PAYE", "PAYE Payable"]
