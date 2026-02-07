import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Sales Invoice": [
			{
				"fieldname": "mra_section",
				"fieldtype": "Section Break",
				"insert_after": "taxes_and_charges",
				"label": "MRA",
			},
			{
				"fieldname": "mra_invoice_type_desc",
				"fieldtype": "Select",
				"insert_after": "mra_section",
				"label": "Invoice Type (MRA)",
				"options": "STD\nPRF\nTRN\nCRN\nDRN",
				"default": "STD",
			},
			{
				"fieldname": "mra_reason_stated",
				"fieldtype": "Small Text",
				"insert_after": "mra_invoice_type_desc",
				"label": "Reason Stated (MRA)",
			},
			{
				"fieldname": "mra_previous_note_hash",
				"fieldtype": "Data",
				"insert_after": "mra_reason_stated",
				"label": "Previous Note Hash (MRA)",
				"read_only": 1,
			},
			{
				"fieldname": "mra_status",
				"fieldtype": "Select",
				"insert_after": "mra_previous_note_hash",
				"label": "MRA Status",
				"options": "PENDING\nSUCCESS\nERRORS\nHAS_ERRORS",
				"read_only": 1,
			},
			{
				"fieldname": "mra_uuid",
				"fieldtype": "Data",
				"insert_after": "mra_status",
				"label": "IRN",
				"read_only": 1,
			},
			{
				"fieldname": "mra_qr_code",
				"fieldtype": "Long Text",
				"insert_after": "mra_uuid",
				"label": "MRA QR Code",
				"read_only": 1,
			},
			{
				"fieldname": "mra_invoice_log",
				"fieldtype": "Link",
				"insert_after": "mra_qr_code",
				"label": "MRA Invoice Log",
				"options": "MRA Invoice Log",
				"read_only": 1,
			},
		]
	}

	create_custom_fields(fields, ignore_validate=True)
