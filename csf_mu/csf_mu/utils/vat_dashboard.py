import frappe
from frappe.utils import flt


SALES_BOXES = ("1.1", "1.2", "1.3", "1.4", "3")
PURCHASE_BOXES = ("6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "7", "8.1", "8.2")


def get_box_values(parent_doctype, child_doctype, boxes, filters=None):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	Parent = frappe.qb.DocType(parent_doctype)
	Child = frappe.qb.DocType(child_doctype)

	query = (
		frappe.qb.from_(Child)
		.join(Parent)
		.on(Child.parent == Parent.name)
		.select(
			Child.vat_return_type,
			Child.base_net_amount,
		)
		.where(Parent.docstatus == 1)
		.where(Child.vat_return_type.isin(list(boxes)))
	)

	if filters.get("company"):
		query = query.where(Parent.company == filters.get("company"))
	if filters.get("from_date"):
		query = query.where(Parent.posting_date >= filters.get("from_date"))
	if filters.get("to_date"):
		query = query.where(Parent.posting_date <= filters.get("to_date"))
	if frappe.get_meta(parent_doctype).has_field("is_opening"):
		query = query.where(Parent.is_opening != "Yes")

	values = {box: 0.0 for box in boxes}
	for row in query.run(as_dict=True):
		values[row.vat_return_type] = values[row.vat_return_type] + flt(row.base_net_amount)

	return {
		"labels": list(boxes),
		"datasets": [
			{
				"name": "Net Value",
				"values": [flt(values[box], 0) for box in boxes],
			}
		],
	}
