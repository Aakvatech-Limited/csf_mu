"""MRA summary/notes workbook and MNS annex generated only from filing snapshots."""

import csv
import io
from collections import defaultdict

import frappe
from frappe.utils import flt, getdate
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def _filing(name):
	doc = frappe.get_doc("VAT Return Filing", name)
	doc.check_permission("read")
	return doc


def _download(filename, content, content_type):
	frappe.local.response.filename = filename
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"
	frappe.local.response.content_type = content_type


@frappe.whitelist()
def download_excel(name: str):
	doc = _filing(name)
	book = Workbook()
	summary = book.active
	summary.title = "VAT Return Summary"
	summary.append(["Company", doc.company, "From", str(doc.from_date), "To", str(doc.to_date)])
	summary.append(["Filing date", str(doc.filing_date or ""), "Recovery %", flt(doc.recovery_percentage)])
	summary.append(
		["MRA reference", doc.mra_acknowledgement_reference or "", "Status", doc.filing_status or "Prepared"]
	)
	summary.append([])
	summary.append(["MRA box", "Description", "Value (MUR)", "VAT (MUR)"])
	for row in doc.lines:
		summary.append([row.box, row.description, flt(row.value_amount), flt(row.vat_amount)])
	details = book.create_sheet("Notes - Breakdown")
	details.append(
		[
			"Source",
			"Invoice",
			"Source item",
			"Party",
			"Invoice date",
			"Posting date",
			"VAT claim date",
			"MRA box",
			"Item",
			"Taxable value (MUR)",
			"VAT (MUR)",
			"Recovery treatment",
			"Recoverable VAT (MUR)",
			"Notes",
		]
	)
	for row in list(doc.sales_details) + list(doc.purchase_details):
		details.append(
			[
				row.source_doctype,
				row.source_invoice,
				row.source_item,
				row.party,
				str(row.invoice_date or ""),
				str(row.posting_date or ""),
				str(row.claim_date or ""),
				row.vat_return_type,
				row.item_code,
				flt(row.taxable_value),
				flt(row.vat_amount),
				row.recovery_treatment,
				flt(row.recoverable_vat),
				row.notes,
			]
		)
	details.append([])
	details.append(["ADJUSTMENTS"])
	details.append(["MRA box", "Reference", "Reason", "VAT amount (MUR)"])
	for row in doc.adjustments:
		details.append([row.mra_box, row.reference, row.reason, flt(row.vat_amount)])
	for sheet in book:
		sheet.freeze_panes = "A6" if sheet == summary else "A2"
		for cell in sheet[5 if sheet == summary else 1]:
			cell.font = Font(color="FFFFFF", bold=True)
			cell.fill = PatternFill("solid", fgColor="17365D")
		for column, width in {
			"A": 24,
			"B": 42,
			"C": 27,
			"D": 29,
			"E": 18,
			"F": 20,
			"G": 22,
			"H": 16,
			"I": 20,
			"J": 24,
			"K": 20,
			"L": 22,
			"M": 26,
			"N": 45,
		}.items():
			sheet.column_dimensions[column].width = width
	output = io.BytesIO()
	book.save(output)
	_download(
		f"VAT_Return_{doc.company}_{doc.from_date}_{doc.to_date}.xlsx",
		output.getvalue(),
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	)


@frappe.whitelist()
def download_mns_annex(name: str):
	"""Prepare the MNS VT03 CSV format from source invoice details.

	Detailed source customer registry data must be present; never invent missing IDs.
	"""
	doc = _filing(name)
	company = frappe.get_doc("Company", doc.company)
	needed = ("mra_tan", "mra_brn")
	if any(not company.get(field) for field in needed):
		frappe.throw(frappe._("Company TAN and BRN are mandatory for the MNS annex."))
	if not doc.declarant_name or not doc.declarant_email:
		frappe.throw(frappe._("MRA declarant name and email are required for the annex."))
	if not (doc.declarant_phone or doc.declarant_mobile or company.get("mra_business_phone")):
		frappe.throw(frappe._("A declarant or business contact number is required for the annex."))
	output = io.StringIO(newline="")
	writer = csv.writer(output, lineterminator="\r\n")
	writer.writerow(["MNS", "VT03", "V1.0", "", "", "", "", ""])
	writer.writerow(
		[
			"VAT Payer TAN",
			"VAT Payer Business Registrtaion Number (BRN)",
			"VAT Payer Full Name",
			"VAT Period",
			"Telephone Number",
			"Mobile Number",
			"Name of Declarant",
			"Email Address",
		]
	)
	filing_month = getdate(doc.from_date).strftime("%Y%m")
	writer.writerow(
		[
			company.mra_tan,
			company.mra_brn,
			company.company_name,
			filing_month,
			doc.declarant_phone or company.get("mra_business_phone") or "",
			doc.declarant_mobile or "",
			doc.declarant_name,
			doc.declarant_email,
		]
	)
	writer.writerow(
		[
			"VAT Registration No. of person to whom supplies is made",
			"Name of person to whom supplies is made",
			"Value of Supplies OR Credit note (MUR)",
			"VAT Amount",
			"Date of Invoice OR Credit Note (MUR)",
			"Invoice OR Credit Note Number",
			"BRN of person to whom supplies is made",
			"",
		]
	)
	groups = defaultdict(lambda: {"value": 0.0, "vat": 0.0, "date": None, "party": None})
	for row in doc.sales_details:
		if row.vat_return_type not in ("1.1", "1.2", "1.3", "1.4"):
			continue
		data = groups[row.source_invoice]
		data["value"] += flt(row.taxable_value)
		data["vat"] += flt(row.vat_amount)
		data["date"] = row.invoice_date
		data["party"] = row.party
	for invoice, data in sorted(groups.items()):
		customer = frappe.get_doc("Customer", data["party"])
		if not (customer.get("mra_tan") or customer.get("mra_brn")):
			# The MNS annex lists identified VAT registrants; consumer
			# supplies remain in the return and aggregate sales breakdown.
			continue
		writer.writerow(
			[
				customer.get("mra_tan") or "",
				customer.customer_name,
				round(data["value"]),
				round(data["vat"]),
				getdate(data["date"]).strftime("%Y%m%d"),
				invoice,
				customer.get("mra_brn") or "",
				"",
			]
		)
	_download(
		f"MNS_VAT_Annex_{filing_month}.csv",
		output.getvalue().encode("utf-8-sig"),
		"text/csv",
	)
