import frappe
from frappe.utils import get_datetime

from csf_mu.csf_mu.utils.mra_tax import get_mra_tax_map


MRA_DATETIME_FORMAT = "%Y%m%d %H:%M:%S"


def _format_mra_datetime(dt):
	if not dt:
		return ""
	return get_datetime(dt).strftime(MRA_DATETIME_FORMAT)


def _get_item_tax_rate(item_tax_template):
	if not item_tax_template:
		return 0
	row = frappe.get_all(
		"Item Tax Template Detail",
		filters={"parent": item_tax_template},
		fields=["tax_rate"],
		limit=1,
	)
	if not row or row[0].get("tax_rate") is None:
		return 0
	return float(row[0].get("tax_rate"))


def _get_company_details(company_name):
	company = frappe.get_doc("Company", company_name)
	return {
		"name": company.company_name,
		"tradeName": company.get("mra_trade_name") or "",
		"tan": company.get("mra_tan") or company.get("tax_id") or "",
		"brn": company.get("mra_brn") or "",
		"businessAddr": company.get("mra_business_addr") or "",
		"businessPhoneNo": company.get("mra_business_phone") or "",
		"ebsCounterNo": "",
		"cashierID": "",
	}


def _get_buyer_details(customer_name):
	if not customer_name:
		return {}
	customer = frappe.get_doc("Customer", customer_name)
	buyer_type = customer.get("mra_buyer_type")
	if not buyer_type:
		buyer_type = "VATR" if customer.get("mra_tan") or customer.get("tax_id") else "NVTR"
	return {
		"name": customer.customer_name,
		"buyerType": buyer_type,
		"tan": customer.get("mra_tan") or customer.get("tax_id") or "",
		"brn": customer.get("mra_brn") or "",
		"businessAddr": customer.get("mra_business_addr") or "",
		"nic": customer.get("mra_nic") or "",
	}


def build_mra_invoice_payload(doc):
	"""Build raw MRA invoice JSON (list with one invoice)."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Sales Invoice", doc)

	company = frappe.get_doc("Company", doc.company)
	person_type = company.get("mra_person_type") or "VATR"

	customer = frappe.get_doc("Customer", doc.customer) if doc.customer else None
	transaction_type = (customer.get("mra_transaction_type") if customer else None) or "B2C"

	invoice_type_desc = doc.get("mra_invoice_type_desc") or "STD"
	invoice_ref_identifier = doc.get("return_against") if invoice_type_desc in ("CRN", "DRN") else ""
	reason_stated = doc.get("mra_reason_stated") if invoice_type_desc in ("CRN", "DRN") else ""

	items = []
	total_vat_amount = 0
	total_amt_wo_vat_cur = 0

	for row in doc.items:
		mapping = get_mra_tax_map(row.item_tax_template)
		tax_rate = _get_item_tax_rate(row.item_tax_template)
		amt_wo_vat = float(row.net_amount or 0)
		vat_amt = round(amt_wo_vat * tax_rate / 100, 2)
		total_price = amt_wo_vat + vat_amt

		item = {
			"itemNo": str(row.idx),
			"taxCode": mapping.get("tax_code"),
			"nature": mapping.get("nature"),
			"itemDesc": row.item_name or row.description or row.item_code,
			"productCodeMra": "",
			"productCodeOwn": row.item_code or "",
			"unitPrice": str(row.rate or 0),
			"quantity": str(row.qty or 0),
			"discount": str(row.discount_amount or 0),
			"discountedValue": str(amt_wo_vat),
			"amtWoVatCur": str(amt_wo_vat),
			"vatAmt": str(vat_amt),
			"totalPrice": str(round(total_price, 2)),
		}

		if doc.currency and doc.currency != "MUR":
			item["amtWoVatMur"] = str(float(row.base_net_amount or 0))

		items.append(item)
		total_vat_amount += vat_amt
		total_amt_wo_vat_cur += amt_wo_vat

	invoice_total = round(total_vat_amount + total_amt_wo_vat_cur, 2)
	discount_total = float(doc.discount_amount or 0)
	total_amt_paid = float(doc.grand_total or invoice_total)

	posting_time = doc.posting_time or "00:00:00"
	payload = {
		"personType": person_type,
		"transactionType": transaction_type,
		"invoiceTypeDesc": invoice_type_desc,
		"invoiceIdentifier": doc.name,
		"invoiceCounter": doc.name,
		"invoiceRefIdentifier": invoice_ref_identifier,
		"previousNoteHash": doc.get("mra_previous_note_hash") or "0",
		"reasonStated": reason_stated,
		"dateTimeInvoiceIssued": _format_mra_datetime(f"{doc.posting_date} {posting_time}"),
		"totalVatAmount": str(round(total_vat_amount, 2)),
		"totalAmtWoVatCur": str(round(total_amt_wo_vat_cur, 2)),
		"currency": doc.currency or "MUR",
		"invoiceTotal": str(invoice_total),
		"discountTotalAmount": str(round(discount_total, 2)) if discount_total else "0",
		"totalAmtPaid": str(round(total_amt_paid, 2)),
		"salesTransactions": "CASH" if doc.is_pos else "CREDIT",
		"seller": _get_company_details(doc.company),
		"itemList": items,
	}

	if doc.currency and doc.currency != "MUR":
		payload["totalAmtWoVatMur"] = str(float(doc.base_net_total or 0))

	buyer = _get_buyer_details(doc.customer)
	if buyer:
		payload["buyer"] = buyer

	return [payload]
