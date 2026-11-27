import frappe

SETTINGS_DOCTYPE = "CSF MU Settings"


def get_mra_settings():
	return frappe.get_single(SETTINGS_DOCTYPE)


def get_company_mra_settings(company, throw=True, for_update=False):
	if not company:
		if throw:
			frappe.throw(_("Company is required to resolve EBS Setting."))
		return None

	if for_update:
		rows = frappe.db.sql(
			"select name from `tabEBS Setting` where name=%s limit 1 for update",
			(company,),
			as_dict=True,
		)
		if not rows:
			if throw:
				frappe.throw(_("EBS Setting not configured for company: {0}.").format(company))
			return None
	elif not frappe.db.exists("EBS Setting", company):
		if throw:
			frappe.throw(_("EBS Setting not configured for company: {0}.").format(company))
		return None

	return frappe.get_doc("EBS Setting", company)
