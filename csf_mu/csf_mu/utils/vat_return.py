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

		updates = {}
		if capital_goods_type and not frappe.db.get_value(
			"VAT Return Type", box_number, "capital_goods_vat_return_type"
		):
			updates["capital_goods_vat_return_type"] = capital_goods_type
		if updates:
			frappe.db.set_value("VAT Return Type", box_number, updates, update_modified=False)


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
			is_fixed_asset = cint(
				frappe.db.get_value("Item", row.item_code, "is_fixed_asset") or 0
			)

		if not is_fixed_asset:
			continue

		# Preserve an explicit pre-submit override. A row still carrying the
		# Item Tax Template default is treated as automatically classified.
		if row.vat_return_type != default_type:
			continue

		capital_goods_type = frappe.db.get_value(
			"VAT Return Type",
			row.vat_return_type,
			"capital_goods_vat_return_type",
		)
		if capital_goods_type:
			row.vat_return_type = capital_goods_type


def backfill_vat_return_types():
	_backfill_invoice_items("Sales Invoice", "Sales Invoice Item", False)
	_backfill_invoice_items("Purchase Invoice", "Purchase Invoice Item", True)


def _backfill_invoice_items(parent_doctype, child_doctype, apply_capital_goods):
	Parent = frappe.qb.DocType(parent_doctype)
	Child = frappe.qb.DocType(child_doctype)
	rows = (
		frappe.qb.from_(Child)
		.join(Parent)
		.on(Child.parent == Parent.name)
		.select(
			Child.name,
			Child.item_code,
			Child.item_tax_template,
			Child.vat_return_type,
		)
		.where(Parent.docstatus == 1)
		.run(as_dict=True)
	)

	for row in rows:
		if row.vat_return_type or not row.item_tax_template:
			continue

		vat_return_type = _get_item_tax_template_vat_return_type(row.item_tax_template)
		if not vat_return_type:
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

		frappe.db.set_value(
			child_doctype,
			row.name,
			"vat_return_type",
			vat_return_type,
			update_modified=False,
		)
