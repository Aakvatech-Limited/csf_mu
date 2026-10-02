import frappe
from frappe.utils import cint


VAT_RETURN_TYPES = (
	("1.1", "Zero-rated supplies (Exports)", "Sales", None),
	("1.2", "Zero-rated supplies other than exports", "Sales", None),
	("1.3", "Taxable supplies made to exempt bodies or persons", "Sales", None),
	("1.4", "Other Taxable supplies", "Sales", None),
	("3", "Exempt Supplies", "Sales", None),
	("6.1", "Capital goods imported", "Purchase", None),
	("6.2", "Zero-rated imports", "Purchase", None),
	("6.3", "Other imports", "Purchase", "6.1"),
	("6.4", "Capital goods purchased locally", "Purchase", None),
	("6.5", "Zero-rated goods and services purchased locally", "Purchase", None),
	("6.6", "Other goods and services purchased locally", "Purchase", "6.4"),
	("7", "Taxable input on which no input tax is allowed as a credit", "Purchase", None),
	("8.1", "Exempt input - Imported goods", "Purchase", None),
	("8.2", "Exempt input - Goods & services purchased locally", "Purchase", None),
)


def ensure_vat_return_types():
	for box_number, title, transaction_type, capital_goods_type in VAT_RETURN_TYPES:
		if not frappe.db.exists("VAT Return Type", box_number):
			doc = frappe.new_doc("VAT Return Type")
			doc.box_number = box_number
			doc.title = title
			doc.transaction_type = transaction_type
			doc.capital_goods_vat_return_type = capital_goods_type
			doc.insert(ignore_permissions=True)
			continue
		if capital_goods_type and not frappe.db.get_value("VAT Return Type", box_number, "capital_goods_vat_return_type"):
			frappe.db.set_value("VAT Return Type", box_number, "capital_goods_vat_return_type", capital_goods_type, update_modified=False)


def _get_item_tax_template_vat_return_type(item_tax_template):
	if not item_tax_template:
		return None
	return frappe.db.get_value("Item Tax Template", item_tax_template, "vat_return_type")


def set_sales_invoice_vat_return_types(doc, method=None):
	for row in doc.get("items", []):
		if row.get("vat_return_type"):
			continue
		vat_return_type = _get_item_tax_template_vat_return_type(row.get("item_tax_template"))
		if vat_return_type:
			row.vat_return_type = vat_return_type


def set_purchase_invoice_vat_return_types(doc, method=None):
	for row in doc.get("items", []):
		default_type = _get_item_tax_template_vat_return_type(row.get("item_tax_template"))
		if not row.get("vat_return_type") and default_type:
			row.vat_return_type = default_type
		if not row.get("vat_return_type") or not default_type:
			continue
		is_fixed_asset = cint(row.get("is_fixed_asset") or 0)
		if not is_fixed_asset and row.get("item_code"):
			is_fixed_asset = cint(frappe.db.get_value("Item", row.item_code, "is_fixed_asset") or 0)
		if not is_fixed_asset or row.vat_return_type != default_type:
			continue
		capital_goods_type = frappe.db.get_value("VAT Return Type", row.vat_return_type, "capital_goods_vat_return_type")
		if capital_goods_type:
			row.vat_return_type = capital_goods_type


def backfill_vat_return_types(company=None):
	sales = _backfill_invoice_items(
		"Sales Invoice",
		"Sales Invoice Item",
		False,
		company=company,
	)
	purchases = _backfill_invoice_items(
		"Purchase Invoice",
		"Purchase Invoice Item",
		True,
		company=company,
	)
	return {
		"sales": sales,
		"purchases": purchases,
		"updated": sales["updated"] + purchases["updated"],
		"already_classified": sales["already_classified"]
		+ purchases["already_classified"],
		"missing_item_tax_template": sales["missing_item_tax_template"]
		+ purchases["missing_item_tax_template"],
		"unmapped_item_tax_template": sales["unmapped_item_tax_template"]
		+ purchases["unmapped_item_tax_template"],
		"capital_goods": purchases["capital_goods"],
		"sales_invoices_updated": sales["invoices_updated"],
		"purchase_invoices_updated": purchases["invoices_updated"],
	}


def _backfill_invoice_items(
	parent_doctype,
	child_doctype,
	apply_capital_goods,
	company=None,
):
	Parent = frappe.qb.DocType(parent_doctype)
	Child = frappe.qb.DocType(child_doctype)
	query = (
		frappe.qb.from_(Child)
		.join(Parent)
		.on(Child.parent == Parent.name)
		.select(
			Child.name,
			Child.parent,
			Child.item_code,
			Child.item_tax_template,
			Child.vat_return_type,
		)
		.where(Parent.docstatus == 1)
	)
	if company:
		query = query.where(Parent.company == company)

	rows = query.run(as_dict=True)
	stats = {
		"scanned": len(rows),
		"updated": 0,
		"already_classified": 0,
		"missing_item_tax_template": 0,
		"unmapped_item_tax_template": 0,
		"capital_goods": 0,
		"invoices_updated": 0,
	}
	updated_invoices = set()

	for row in rows:
		if row.vat_return_type:
			stats["already_classified"] += 1
			continue
		if not row.item_tax_template:
			stats["missing_item_tax_template"] += 1
			continue

		vat_return_type = _get_item_tax_template_vat_return_type(
			row.item_tax_template
		)
		if not vat_return_type:
			stats["unmapped_item_tax_template"] += 1
			continue

		if apply_capital_goods and row.item_code:
			is_fixed_asset = cint(
				frappe.db.get_value("Item", row.item_code, "is_fixed_asset") or 0
			)
			if is_fixed_asset:
				capital_goods_type = frappe.db.get_value(
					"VAT Return Type",
					vat_return_type,
					"capital_goods_vat_return_type",
				)
				if capital_goods_type:
					vat_return_type = capital_goods_type
					stats["capital_goods"] += 1

		# Update the submitted invoice child row directly. This deliberately
		# bypasses Document.save(), so neither the child nor parent modified
		# timestamp changes and no Version record is created.
		frappe.db.set_value(
			child_doctype,
			row.name,
			"vat_return_type",
			vat_return_type,
			update_modified=False,
		)
		stats["updated"] += 1
		updated_invoices.add(row.parent)

	stats["invoices_updated"] = len(updated_invoices)
	return stats
