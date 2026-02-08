import json

import frappe

from csf_mu.csf_mu.utils.mra_api import sign_payload, transmit_invoice
from csf_mu.csf_mu.utils.mra_payload import build_mra_invoice_payload


def _send_invoice_to_mra(doc, allow_existing_log=False):
	existing = frappe.db.exists("MRA Invoice Log", {"sales_invoice": doc.name})
	if existing and not allow_existing_log:
		return

	payload_list = build_mra_invoice_payload(doc)
	payload_json = json.dumps(payload_list)

	if existing:
		log = frappe.get_doc("MRA Invoice Log", existing)
		log.status = "PENDING"
		log.error_summary = ""
		log.request_json = payload_json
		log.response_json = ""
		log.request_id = ""
		log.request_datetime = ""
		log.response_id = ""
		log.response_datetime = ""
		log.set("errors", [])
		log.save(ignore_permissions=True)
	else:
		log = frappe.new_doc("MRA Invoice Log")
		log.sales_invoice = doc.name
		log.company = doc.company
		log.status = "PENDING"
		log.invoice_identifier = doc.name
		log.request_json = payload_json
		log.insert(ignore_permissions=True)
		doc.db_set("mra_invoice_log", log.name, update_modified=False)

	doc.db_set("mra_status", "PENDING", update_modified=False)

	settings = frappe.get_single("CSF MU Settings")
	if not settings.public_key_certificate:
		log.status = "ERRORS"
		log.error_summary = "Public Key Certificate is required in CSF MU Settings."
		log.save(ignore_permissions=True)
		doc.db_set("mra_status", "ERRORS", update_modified=False)
		return

	try:
		signed_hash = sign_payload(payload_json, settings)
		request_payload, response = transmit_invoice(payload_json, signed_hash)
	except Exception as exc:
		log.status = "ERRORS"
		log.error_summary = str(exc)
		log.save(ignore_permissions=True)
		doc.db_set("mra_status", "ERRORS", update_modified=False)
		return

	log.request_id = request_payload.get("requestId")
	log.request_datetime = request_payload.get("requestDateTime")
	log.response_id = response.get("responseId")
	log.response_datetime = response.get("responseDateTime")
	log.status = response.get("status") or "ERROR"
	log.response_json = json.dumps(response)

	irn = None
	qr_code = None
	errors = []
	for inv in response.get("fiscalisedInvoices") or []:
		if inv.get("invoiceIdentifier") == doc.name:
			irn = inv.get("irn") or inv.get("uuid")
			qr_code = inv.get("qrCode")
			errors = inv.get("errorMessages") or []
			break

	if irn:
		log.mra_uuid = irn
		doc.db_set("mra_uuid", irn, update_modified=False)

	if qr_code:
		log.mra_qr_code = qr_code
		doc.db_set("mra_qr_code", qr_code, update_modified=False)

	if errors:
		log.error_summary = errors[0].get("description") if errors else ""
		log.set("errors", [])
		for err in errors:
			log.append(
				"errors",
				{
					"invoice_identifier": doc.name,
					"code": err.get("code"),
					"description": err.get("description"),
				},
			)

	log.save(ignore_permissions=True)
	doc.db_set("mra_status", log.status, update_modified=False)


def create_invoice_log(doc, method=None):
	_send_invoice_to_mra(doc, allow_existing_log=False)


@frappe.whitelist()
def resend_invoice_to_mra(sales_invoice):
	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	if doc.docstatus != 1:
		frappe.throw("Only submitted Sales Invoices can be re-sent to MRA.")
	status = (doc.get("mra_status") or "").upper()
	if status not in ("ERROR", "ERRORS"):
		frappe.throw("Re-send is allowed only for invoices with status ERROR or ERRORS.")
	_send_invoice_to_mra(doc, allow_existing_log=True)
	return {"status": doc.get("mra_status")}
