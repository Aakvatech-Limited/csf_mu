"""Protect invoice lines included in a submitted VAT Return Filing."""

import frappe


def _linked_filing(doctype: str, source_item: str | None = None, source_invoice: str | None = None):
	"""Query the appropriate predefined detail table, without dynamic SQL."""
	if doctype == "Purchase Invoice":
		Detail = frappe.qb.DocType("VAT Return Purchase Detail")
	elif doctype == "Sales Invoice":
		Detail = frappe.qb.DocType("VAT Return Sales Detail")
	else:
		frappe.throw(frappe._("Unsupported VAT source document"))
	Filing = frappe.qb.DocType("VAT Return Filing")
	query = (
		frappe.qb.from_(Detail)
		.join(Filing)
		.on(Filing.name == Detail.parent)
		.select(Filing.name)
		.where(Filing.docstatus == 1)
	)
	if source_item:
		query = query.where(Detail.source_item == source_item)
	if source_invoice:
		query = query.where(Detail.source_invoice == source_invoice)
	matches = query.limit(1).run(as_dict=True)
	return matches[0].name if matches else None


def validate_purchase_invoice_claims(doc, method=None):
	previous = doc.get_doc_before_save()
	if not previous:
		return
	previous_rows = {row.name: row for row in previous.items}
	for row in doc.items:
		prior = previous_rows.get(row.name)
		if not prior:
			continue
		if (
			row.vat_claim_date != prior.vat_claim_date
			or row.vat_return_type != prior.vat_return_type
			or row.get("vat_recovery_treatment") != prior.get("vat_recovery_treatment")
			or row.base_net_amount != prior.base_net_amount
		):
			filed = _linked_filing(doc.doctype, source_item=row.name)
			if filed:
				frappe.throw(
					f"Purchase item {row.idx} is already included in submitted VAT Return Filing {filed}."
				)


def before_cancel_invoice(doc, method=None):
	filed = _linked_filing(doc.doctype, source_invoice=doc.name)
	if filed:
		frappe.throw(
			f"Cannot cancel an invoice included in submitted VAT Return Filing {filed}. Cancel/amend the filing first."
		)
