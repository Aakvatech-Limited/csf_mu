import json
from uuid import uuid4

import frappe
from frappe.utils import cint

from csf_mu.csf_mu.utils.mra_api import sign_payload, transmit_invoice
from csf_mu.csf_mu.utils.mra_payload import build_mra_invoice_payload
from csf_mu.csf_mu.utils.mra_settings import (
	get_company_mra_settings,
	get_mra_settings,
)


def _reset_or_create_log(doc, payload_json, allow_existing_log=True):
	existing = frappe.db.exists("MRA Einvoice Log", {"sales_invoice": doc.name})
	if existing and not allow_existing_log:
		return None

	if existing:
		log = frappe.get_doc("MRA Einvoice Log", existing)
		log.status = "PENDING"
		log.error_summary = ""
		log.request_json = payload_json
		log.response_json = ""
		log.request_id = ""
		log.request_datetime = ""
		log.response_id = ""
		log.response_datetime = ""
		log.mra_uuid = ""
		log.mra_qr_code = ""
		log.save(ignore_permissions=True)
	else:
		log = frappe.new_doc("MRA Einvoice Log")
		log.sales_invoice = doc.name
		log.company = doc.company
		log.status = "PENDING"
		log.invoice_identifier = doc.name
		log.request_json = payload_json
		log.insert(ignore_permissions=True)

	doc.db_set("mra_status", "PENDING", update_modified=False)
	return log


def _send_invoice_to_mra(doc, allow_existing_log=False):
	settings = get_mra_settings()
	settings_detail = get_company_mra_settings(doc.company, throw=False)
	if not settings_detail or not settings_detail.public_key_certificate:
		log = _reset_or_create_log(doc, "[]", allow_existing_log=allow_existing_log)
		if not log:
			return
		log.status = "ERRORS"
		log.error_summary = (
			f"CSF MU Settings Detail with Public Key Certificate is required for company {doc.company}."
		)
		log.save(ignore_permissions=True)
		doc.db_set("mra_status", "ERRORS", update_modified=False)
		return

	payload_list = build_mra_invoice_payload(doc)
	payload_json = json.dumps(payload_list)

	log = _reset_or_create_log(doc, payload_json, allow_existing_log=allow_existing_log)
	if not log:
		return

	try:
		signed_hash = sign_payload(payload_json, settings_detail)
		request_payload, response = transmit_invoice(
			payload_json,
			signed_hash,
			company=doc.company,
			settings=settings,
			settings_detail=settings_detail,
		)
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
		log.error_summary = json.dumps(errors)
	elif (response.get("status") or "").upper() in ("ERROR", "ERRORS", "HAS_ERRORS"):
		log.error_summary = json.dumps(response.get("errorMessages") or [])

	log.save(ignore_permissions=True)
	doc.db_set("mra_status", log.status, update_modified=False)


def create_invoice_log(doc, method=None):
	settings_detail = get_company_mra_settings(doc.company, throw=False)
	if not settings_detail:
		return
	if not cint(settings_detail.auto_send_to_mra_on_submit):
		return
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


@frappe.whitelist()
def get_prf_trn_setting(company=None):
	if not company:
		return 0
	settings_detail = get_company_mra_settings(company, throw=False)
	return (settings_detail.enable_prf_trn if settings_detail else 0) or 0


@frappe.whitelist()
def batch_transmit_invoices(sales_invoices):
	if isinstance(sales_invoices, str):
		try:
			sales_invoices = json.loads(sales_invoices)
		except Exception:
			sales_invoices = [s.strip() for s in sales_invoices.splitlines() if s.strip()]

	if not sales_invoices:
		frappe.throw("Select one or more Sales Invoices for batch transmit.")

	eligible_docs = []
	skipped = []
	companies = set()
	for name in sales_invoices:
		doc = frappe.get_doc("Sales Invoice", name)
		if doc.docstatus != 1:
			frappe.throw(f"Sales Invoice {name} must be submitted before sending to MRA.")
		status = (doc.get("mra_status") or "").upper()
		if status == "SUCCESS":
			skipped.append(name)
			continue
		eligible_docs.append(doc)
		companies.add(doc.company)

	if not eligible_docs:
		frappe.throw("All selected invoices are already SUCCESS.")

	if len(companies) > 1:
		frappe.throw("Batch transmit currently supports one company per request.")

	company = eligible_docs[0].company
	settings_detail = get_company_mra_settings(company)
	max_per_request = settings_detail.max_invoices_per_request or 500
	if len(eligible_docs) > max_per_request:
		frappe.throw(f"Maximum invoices per request is {max_per_request}.")

	total_items = sum(len(doc.items or []) for doc in eligible_docs)
	if total_items > 5000:
		frappe.throw("Maximum total items per request is 5000.")

	task_id = uuid4().hex
	frappe.enqueue(
		"csf_mu.csf_mu.utils.mra_invoice.batch_transmit_job",
		queue="long",
		sales_invoices=[doc.name for doc in eligible_docs],
		company=company,
		task_id=task_id,
	)
	frappe.local.response["task_id"] = task_id
	return {"queued": len(eligible_docs), "skipped": skipped}


def batch_transmit_job(sales_invoices, company=None, task_id=None):
	title = "MRA Batch Transmit"
	frappe.publish_progress(0, title=title, description="Preparing invoices...", task_id=task_id)

	docs = []
	for name in sales_invoices:
		doc = frappe.get_doc("Sales Invoice", name)
		if company and doc.company != company:
			continue
		docs.append(doc)

	if not docs:
		frappe.publish_progress(100, title=title, description="No invoices to process.", task_id=task_id)
		return

	company = company or docs[0].company
	settings = get_mra_settings()
	settings_detail = get_company_mra_settings(company, throw=False)
	if not settings_detail or not settings_detail.public_key_certificate:
		for doc in docs:
			log = _reset_or_create_log(doc, "[]", allow_existing_log=True)
			if not log:
				continue
			log.status = "ERRORS"
			log.error_summary = (
				f"CSF MU Settings Detail with Public Key Certificate is required for company {company}."
			)
			log.save(ignore_permissions=True)
			doc.db_set("mra_status", "ERRORS", update_modified=False)
		frappe.publish_progress(100, title=title, description="Failed.", task_id=task_id)
		return

	payload_list = []
	for idx, doc in enumerate(docs, start=1):
		payload_list.extend(build_mra_invoice_payload(doc))
		percent = int(idx / max(len(docs), 1) * 10)
		frappe.publish_progress(
			percent,
			title=title,
			description=f"Building payload ({idx}/{len(docs)})",
			task_id=task_id,
		)

	payload_json = json.dumps(payload_list)

	logs = {}
	for doc in docs:
		log = _reset_or_create_log(doc, payload_json, allow_existing_log=True)
		if log:
			logs[doc.name] = log

	try:
		signed_hash = sign_payload(payload_json, settings_detail)
		request_payload, response = transmit_invoice(
			payload_json,
			signed_hash,
			company=company,
			settings=settings,
			settings_detail=settings_detail,
		)
	except Exception as exc:
		for doc in docs:
			log = logs.get(doc.name)
			if not log:
				continue
			log.status = "ERRORS"
			log.error_summary = str(exc)
			log.save(ignore_permissions=True)
			doc.db_set("mra_status", "ERRORS", update_modified=False)
		frappe.publish_progress(100, title=title, description="Failed.", task_id=task_id)
		return

	inv_map = {}
	for inv in response.get("fiscalisedInvoices") or []:
		if inv.get("invoiceIdentifier"):
			inv_map[inv.get("invoiceIdentifier")] = inv

	for idx, doc in enumerate(docs, start=1):
		log = logs.get(doc.name)
		if not log:
			continue

		log.request_id = request_payload.get("requestId")
		log.request_datetime = request_payload.get("requestDateTime")
		log.response_id = response.get("responseId")
		log.response_datetime = response.get("responseDateTime")
		log.response_json = json.dumps(response)

		inv_resp = inv_map.get(doc.name)
		if not inv_resp:
			log.status = "ERRORS"
			log.error_summary = "No response for invoice in batch transmit."
			log.save(ignore_permissions=True)
			doc.db_set("mra_status", log.status, update_modified=False)
			continue

		log.status = inv_resp.get("status") or response.get("status") or "ERROR"

		irn = inv_resp.get("irn") or inv_resp.get("uuid")
		qr_code = inv_resp.get("qrCode")
		errors = inv_resp.get("errorMessages") or []

		log.mra_uuid = irn or ""
		log.mra_qr_code = qr_code or ""

		if irn:
			doc.db_set("mra_uuid", irn, update_modified=False)
		if qr_code:
			doc.db_set("mra_qr_code", qr_code, update_modified=False)

		if errors:
			log.error_summary = json.dumps(errors)
		elif (log.status or "").upper() in ("ERROR", "ERRORS", "HAS_ERRORS"):
			log.error_summary = json.dumps(response.get("errorMessages") or [])
		else:
			log.error_summary = ""

		log.save(ignore_permissions=True)
		doc.db_set("mra_status", log.status, update_modified=False)

		percent = int(idx / max(len(docs), 1) * 100)
		frappe.publish_progress(
			percent,
			title=title,
			description=f"Processed {idx}/{len(docs)}",
			task_id=task_id,
		)

	frappe.publish_progress(100, title=title, description="Completed.", task_id=task_id)
