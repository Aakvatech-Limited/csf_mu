import frappe


SETTINGS_DOCTYPE = "CSF MU Settings"
SETTINGS_DETAIL_DOCTYPE = "CSF MU Settings Detail"
SETTINGS_SINGLE_NAME = "CSF MU Settings"


def get_mra_settings():
	return frappe.get_single(SETTINGS_DOCTYPE)


def get_company_mra_settings(company, throw=True, for_update=False):
	if not company:
		if throw:
			frappe.throw("Company is required to resolve CSF MU Settings.")
		return None

	if for_update:
		rows = frappe.db.sql(
			"""
			select name
			from `tabCSF MU Settings Detail`
			where parent=%s and parenttype=%s and company=%s
			limit 1
			for update
			""",
			(SETTINGS_SINGLE_NAME, SETTINGS_DOCTYPE, company),
			as_dict=True,
		)
		row_name = rows[0].name if rows else None
	else:
		row_name = frappe.db.get_value(
			SETTINGS_DETAIL_DOCTYPE,
			{
				"parent": SETTINGS_SINGLE_NAME,
				"parenttype": SETTINGS_DOCTYPE,
				"company": company,
			},
			"name",
		)

	if not row_name:
		if throw:
			frappe.throw(
				f"CSF MU Settings Detail not configured for company: {company}."
			)
		return None

	return frappe.get_doc(SETTINGS_DETAIL_DOCTYPE, row_name)

