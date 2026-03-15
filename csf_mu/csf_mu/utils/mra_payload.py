import hashlib

import frappe
from frappe.utils import cint, get_datetime

from csf_mu.csf_mu.utils.mra_tax import get_mra_tax_map
from csf_mu.csf_mu.utils.mra_settings import get_company_mra_settings


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


def _reserve_invoice_counter(company):
	settings_detail = get_company_mra_settings(company, for_update=True)
	current = cint(settings_detail.get("mra_invoice_counter") or 0)
	next_counter = current + 1
	settings_detail.db_set("mra_invoice_counter", next_counter, update_modified=False)
	return next_counter


def _get_invoice_counter(doc):
	counter = doc.get("mra_invoice_counter")
	if counter:
		return str(counter)

	counter = _reserve_invoice_counter(doc.company)
	doc.db_set("mra_invoice_counter", counter, update_modified=False)
	return str(counter)


def _resolve_invoice_type(doc):
	if doc.get("is_return"):
		return "CRN"
	if doc.get("is_debit_note"):
		return "DRN"
	return doc.get("mra_invoice_type_desc") or "STD"


def _validate_credit_debit(doc, invoice_type_desc):
	if invoice_type_desc not in ("CRN", "DRN"):
		return
	if not doc.get("return_against"):
		frappe.throw("Return Against is required for Credit/Debit Notes (CRN/DRN).")
	if not doc.get("mra_reason_stated"):
		frappe.throw("Reason Stated is required for Credit/Debit Notes (CRN/DRN).")


def _normalize_amount(value, invoice_type_desc):
	amount = float(value or 0)
	if invoice_type_desc in ("CRN", "DRN"):
		return abs(amount)
	return amount


def _compute_previous_note_hash(previous_doc, invoice_type_desc):
	company = frappe.get_doc("Company", previous_doc.company)
	brn = company.get("mra_brn") or ""
	posting_time = previous_doc.posting_time or "00:00:00"
	date_time = _format_mra_datetime(f"{previous_doc.posting_date} {posting_time}")
	total_amt_paid = _normalize_amount(previous_doc.grand_total, invoice_type_desc)
	if int(total_amt_paid) == total_amt_paid:
		total_amt_paid = int(total_amt_paid)
	invoice_identifier = previous_doc.name

	raw = f"{date_time}{total_amt_paid}{brn}{invoice_identifier}"
	return hashlib.sha256(raw.encode()).hexdigest().upper()


def _get_previous_note_hash(doc, invoice_type_desc):
	prev_hash = doc.get("mra_previous_note_hash")
	if prev_hash:
		return prev_hash

	previous_doc_name = frappe.db.get_value(
		"Sales Invoice",
		{
			"docstatus": 1,
			"company": doc.company,
			"mra_invoice_type_desc": invoice_type_desc,
			"mra_status": "SUCCESS",
			"name": ("!=", doc.name),
		},
		"name",
		order_by="posting_date desc, posting_time desc, creation desc",
	)

	if not previous_doc_name:
		return "0"

	previous_doc = frappe.get_doc("Sales Invoice", previous_doc_name)
	return _compute_previous_note_hash(previous_doc, invoice_type_desc)


def build_mra_invoice_payload(doc):
	"""Build raw MRA invoice JSON (list with one invoice)."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Sales Invoice", doc)

	company = frappe.get_doc("Company", doc.company)
	person_type = company.get("mra_person_type") or "VATR"

	customer = frappe.get_doc("Customer", doc.customer) if doc.customer else None
	transaction_type = (customer.get("mra_transaction_type") if customer else None) or "B2C"

	invoice_type_desc = _resolve_invoice_type(doc)
	_validate_credit_debit(doc, invoice_type_desc)
	if not doc.get("mra_invoice_type_desc"):
		doc.db_set("mra_invoice_type_desc", invoice_type_desc, update_modified=False)
	invoice_ref_identifier = doc.get("return_against") if invoice_type_desc in ("CRN", "DRN") else ""
	reason_stated = doc.get("mra_reason_stated") if invoice_type_desc in ("CRN", "DRN") else ""
	invoice_counter = _get_invoice_counter(doc)

	items = []
	total_vat_amount = 0
	total_amt_wo_vat_cur = 0

	for row in doc.items:
		mapping = get_mra_tax_map(row.item_tax_template)
		tax_rate = _get_item_tax_rate(row.item_tax_template)
		amt_wo_vat = _normalize_amount(row.net_amount, invoice_type_desc)
		vat_amt = round(amt_wo_vat * tax_rate / 100, 2)
		total_price = amt_wo_vat + vat_amt
		quantity = _normalize_amount(row.qty, invoice_type_desc)

		item = {
			"itemNo": str(row.idx),
			"taxCode": mapping.get("tax_code"),
			"nature": mapping.get("nature"),
			"itemDesc": row.item_name or row.description or row.item_code,
			"productCodeMra": "",
			"productCodeOwn": row.item_code or "",
			"unitPrice": str(_normalize_amount(row.rate, invoice_type_desc)),
			"quantity": str(quantity),
			"discount": str(row.discount_amount or 0),
			"discountedValue": str(amt_wo_vat),
			"amtWoVatCur": str(amt_wo_vat),
			"vatAmt": str(vat_amt),
			"totalPrice": str(round(total_price, 2)),
		}

		if doc.currency and doc.currency != "MUR":
			item["amtWoVatMur"] = str(
				_normalize_amount(row.base_net_amount, invoice_type_desc)
			)

		items.append(item)
		total_vat_amount += vat_amt
		total_amt_wo_vat_cur += amt_wo_vat

	invoice_total = round(total_vat_amount + total_amt_wo_vat_cur, 2)
	discount_total = _normalize_amount(doc.discount_amount, invoice_type_desc)
	total_amt_paid = _normalize_amount(doc.grand_total or invoice_total, invoice_type_desc)

	posting_time = doc.posting_time or "00:00:00"
	payload = {
		"personType": person_type,
		"transactionType": transaction_type,
		"invoiceTypeDesc": invoice_type_desc,
		"invoiceIdentifier": doc.name,
		"invoiceCounter": invoice_counter,
		"invoiceRefIdentifier": invoice_ref_identifier,
		"previousNoteHash": _get_previous_note_hash(doc, invoice_type_desc),
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
		payload["totalAmtWoVatMur"] = str(
			_normalize_amount(doc.base_net_total, invoice_type_desc)
		)

	buyer = _get_buyer_details(doc.customer)
	if buyer:
		payload["buyer"] = buyer

	return [payload]
