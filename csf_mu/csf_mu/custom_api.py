import frappe

from csf_mu.csf_mu.utils.vat_return import backfill_vat_return_types


@frappe.whitelist()
def backfill_vat_return_type(company):
	if not company:
		frappe.throw("Company is required")

	company_doc = frappe.get_doc("Company", company)
	company_doc.check_permission("write")

	return backfill_vat_return_types(company=company)


@frappe.whitelist()
def create_vat_return_filing(filters):
	from csf_mu.csf_mu.report.vat_return.vat_return import execute, get_period

	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	company = filters.get("company")
	if not company:
		frappe.throw("Company is required")
	if not frappe.has_permission("VAT Return Filing", ptype="create"):
		frappe.throw("You do not have permission to create VAT Return Filing.")

	from_date, to_date = get_period(frappe._dict(filters))
	submitted = frappe.db.get_value(
		"VAT Return Filing",
		{
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"docstatus": 1,
		},
		"name",
	)
	if submitted:
		return {"name": submitted, "submitted": 1}

	columns, rows = execute(filters)
	box_map = {row.get("box"): row for row in rows if row.get("box")}
	draft = frappe.db.get_value(
		"VAT Return Filing",
		{
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"docstatus": 0,
		},
		"name",
	)
	if draft:
		doc = frappe.get_doc("VAT Return Filing", draft)
		doc.check_permission("write")
	else:
		doc = frappe.new_doc("VAT Return Filing")

	doc.company = company
	doc.from_date = from_date
	doc.to_date = to_date
	doc.currency = frappe.db.get_value("Company", company, "default_currency")
	doc.box_12_excess_brought_forward = (box_map.get("12") or {}).get("vat_amount") or 0
	doc.box_16_excess_carried_forward = (box_map.get("16") or {}).get("vat_amount") or 0
	doc.filters_json = frappe.as_json(filters)
	doc.return_data_json = frappe.as_json(rows)
	doc.set("lines", [])
	for row in rows:
		doc.append(
			"lines",
			{
				"box": row.get("box"),
				"description": row.get("description"),
				"value_amount": row.get("value_amount"),
				"vat_amount": row.get("vat_amount"),
				"currency": row.get("currency"),
			},
		)

	if doc.is_new():
		doc.insert()
	else:
		doc.save()
	return {"name": doc.name, "submitted": 0}


@frappe.whitelist()
def create_mra_item_tax_templates(company):
	if not company:
		frappe.throw("Company is required")

	company_doc = frappe.get_doc("Company", company)
	abbr = company_doc.abbr or company_doc.name

	tax_account = _get_default_vat_account(company)
	if not tax_account:
		frappe.throw(
			"No VAT tax account found. Please create a VAT tax account for this company."
		)

	tax_templates = _get_mra_tax_templates(abbr)

	created = []
	for tmpl in tax_templates:
		title = tmpl["title"]
		template_name = frappe.db.get_value(
			"Item Tax Template", {"title": title, "company": company}, "name"
		)
		if not template_name:
			legacy_title = f"{title} - {abbr}"
			template_name = frappe.db.get_value(
				"Item Tax Template", {"title": legacy_title, "company": company}, "name"
			)

		if not template_name:
			doc = frappe.new_doc("Item Tax Template")
			doc.title = title
			doc.company = company
			doc.append(
				"taxes",
				{"tax_type": tax_account, "tax_rate": tmpl["tax_rate"]},
			)
			doc.insert(ignore_permissions=True)
			template_name = doc.name
			created.append(template_name)

		_map_tax_code(template_name, tmpl["tax_code"], tmpl["nature"])

	return {
		"created": created,
		"tax_account": tax_account,
	}


def _get_default_vat_account(company):
	accounts = frappe.get_all(
		"Account",
		filters={"company": company, "account_type": "Tax"},
		fields=["name", "account_name"],
	)
	for acc in accounts:
		if "vat" in (acc.get("account_name") or "").lower():
			return acc.get("name")
	return accounts[0].get("name") if accounts else None


def _map_tax_code(item_tax_template, tax_code, nature):
	exists = frappe.db.exists(
		"MRA Tax Code Map",
		{"item_tax_template": item_tax_template},
	)
	if exists:
		return

	map_doc = frappe.new_doc("MRA Tax Code Map")
	map_doc.item_tax_template = item_tax_template
	map_doc.tax_code = tax_code
	map_doc.nature = nature
	map_doc.insert(ignore_permissions=True)


def _get_mra_tax_templates(abbr):
	# Create both GOODS and SERVICES templates for each tax code
	codes = [
		{"tax_code": "TC01", "label": "Standard", "tax_rate": 15},
		{"tax_code": "TC02", "label": "Zero Rated", "tax_rate": 0},
		{"tax_code": "TC03", "label": "Exempt", "tax_rate": 0},
		{"tax_code": "TC04", "label": "Non Fiscal", "tax_rate": 0},
		{"tax_code": "TC05", "label": "Std to Exempt", "tax_rate": 15},
		{"tax_code": "TC06", "label": "Out of Scope", "tax_rate": 0},
	]

	templates = []
	for code in codes:
		for nature in ("GOODS", "SERVICES"):
			templates.append(
				{
					"title": f"MRA {code['tax_code']} {nature}",
					"tax_code": code["tax_code"],
					"nature": nature,
					"tax_rate": code["tax_rate"],
				}
			)
	return templates
