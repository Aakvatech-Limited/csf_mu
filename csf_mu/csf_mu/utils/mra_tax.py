import frappe


def get_mra_tax_map(item_tax_template: str) -> dict:
	"""Return mapping for the given Item Tax Template.

	Raises frappe.ValidationError if mapping is missing.
	"""
	if not item_tax_template:
		frappe.throw("Item Tax Template is required to map MRA tax codes.")

	mapping = frappe.get_all(
		"MRA Tax Code Map",
		filters={"item_tax_template": item_tax_template, "disabled": 0},
		fields=["name", "tax_code", "nature"],
		limit=1,
	)
	if not mapping:
		frappe.throw(
			f"No MRA Tax Code Map found for Item Tax Template: {item_tax_template}."
		)

	return mapping[0]


def validate_sales_invoice_items_for_mra(doc, method=None):
	"""Validate Item Tax Template presence and MRA mapping for each Sales Invoice item.

	Validation is only enforced when CSF MU Settings is configured.
	"""
	public_key = frappe.db.get_single_value("CSF MU Settings", "public_key_certificate")
	if not public_key:
		return
	if doc.get("is_return"):
		doc.mra_invoice_type_desc = "CRN"
	elif doc.get("is_debit_note"):
		doc.mra_invoice_type_desc = "DRN"
	elif not doc.get("mra_invoice_type_desc"):
		doc.mra_invoice_type_desc = "STD"

	if doc.mra_invoice_type_desc in ("CRN", "DRN"):
		if not doc.get("return_against"):
			frappe.throw("Return Against is required for Credit/Debit Notes (CRN/DRN).")
		if not doc.get("mra_reason_stated"):
			frappe.throw("Reason Stated is required for Credit/Debit Notes (CRN/DRN).")
	missing_templates = []
	missing_maps = []

	for row in doc.get("items", []):
		if not row.item_tax_template:
			missing_templates.append(row.idx)
			continue
		mapping = frappe.db.exists(
			"MRA Tax Code Map",
			{"item_tax_template": row.item_tax_template, "disabled": 0},
		)
		if not mapping:
			missing_maps.append((row.idx, row.item_tax_template))

	if missing_templates or missing_maps:
		parts = []
		if missing_templates:
			parts.append(
				"Missing Item Tax Template on rows: " + ", ".join(map(str, missing_templates))
			)
		if missing_maps:
			parts.append(
				"No MRA Tax Code Map for: "
				+ ", ".join([f"row {idx} ({tmpl})" for idx, tmpl in missing_maps])
			)
		frappe.throw("; ".join(parts))
