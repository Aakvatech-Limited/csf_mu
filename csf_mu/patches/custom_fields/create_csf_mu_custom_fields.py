import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Company": [
			{
				"fieldname": "mra_tab",
				"fieldtype": "Tab Break",
				"insert_after": "default_operating_cost_account",
				"label": "MRA",
			},
			{
				"fieldname": "mra_section",
				"fieldtype": "Section Break",
				"insert_after": "mra_tab",
				"label": "MRA",
			},
			{
				"fieldname": "mra_tan",
				"fieldtype": "Data",
				"insert_after": "mra_section",
				"label": "TAN",
				"reqd": 1,
			},
			{
				"fieldname": "mra_brn",
				"fieldtype": "Data",
				"insert_after": "mra_tan",
				"label": "BRN",
				"reqd": 1,
			},
			{
				"fieldname": "mra_column_break_1",
				"fieldtype": "Column Break",
				"insert_after": "mra_brn",
			},
			{
				"fieldname": "mra_trade_name",
				"fieldtype": "Data",
				"insert_after": "mra_column_break_1",
				"label": "Trade Name",
			},
			{
				"fieldname": "mra_business_addr",
				"fieldtype": "Small Text",
				"insert_after": "mra_trade_name",
				"label": "Business Address",
				"reqd": 1,
			},
			{
				"fieldname": "mra_business_phone",
				"fieldtype": "Data",
				"insert_after": "mra_business_addr",
				"label": "Business Phone",
			},
			{
				"fieldname": "mra_person_type",
				"fieldtype": "Select",
				"insert_after": "mra_business_phone",
				"label": "Person Type",
				"options": "VATR\nNVTR",
				"default": "VATR",
			},
		],
		"Customer": [
			{
				"fieldname": "mra_section",
				"fieldtype": "Section Break",
				"insert_after": "tax_id",
				"label": "MRA",
			},
			{
				"fieldname": "mra_buyer_type",
				"fieldtype": "Select",
				"insert_after": "mra_section",
				"label": "Buyer Type",
				"options": "VATR\nNVTR\nEXMP",
				"mandatory_depends_on": "eval:doc.mra_transaction_type=='B2B' || doc.mra_transaction_type=='B2G'",
			},
			{
				"fieldname": "mra_transaction_type",
				"fieldtype": "Select",
				"insert_after": "mra_buyer_type",
				"label": "Transaction Type",
				"options": "B2B\nB2G\nB2C\nEXP\nB2E",
				"default": "B2C",
			},
			{
				"fieldname": "mra_tan",
				"fieldtype": "Data",
				"insert_after": "mra_transaction_type",
				"label": "TAN",
				"mandatory_depends_on": "eval:doc.mra_transaction_type=='B2B' || doc.mra_transaction_type=='B2G'",
			},
			{
				"fieldname": "mra_brn",
				"fieldtype": "Data",
				"insert_after": "mra_tan",
				"label": "BRN",
				"mandatory_depends_on": "eval:doc.mra_transaction_type=='B2B'",
			},
			{
				"fieldname": "mra_business_addr",
				"fieldtype": "Small Text",
				"insert_after": "mra_brn",
				"label": "Business Address",
			},
			{
				"fieldname": "mra_nic",
				"fieldtype": "Data",
				"insert_after": "mra_business_addr",
				"label": "NIC / NCID",
			},
		],
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
				"no_copy": 1,
				"read_only": 1,
			},
			{
				"fieldname": "mra_column_break_1",
				"fieldtype": "Column Break",
				"insert_after": "mra_previous_note_hash",
			},
			{
				"fieldname": "mra_status",
				"fieldtype": "Data",
				"insert_after": "mra_column_break_1",
				"in_list_view": 1,
				"label": "MRA Status",
				"no_copy": 1,
				"read_only": 1,
			},
			{
				"fieldname": "mra_invoice_counter",
				"fieldtype": "Int",
				"insert_after": "mra_status",
				"label": "Invoice Counter (MRA)",
				"no_copy": 1,
				"read_only": 1,
			},
			{
				"fieldname": "mra_uuid",
				"fieldtype": "Data",
				"insert_after": "mra_invoice_counter",
				"label": "IRN",
				"no_copy": 1,
				"read_only": 1,
			},
			{
				"fieldname": "mra_qr_code",
				"fieldtype": "Long Text",
				"insert_after": "mra_uuid",
				"hidden": 1,
				"label": "MRA QR Code",
				"no_copy": 1,
				"read_only": 1,
			},
			{
				"fieldname": "mra_invoice_log",
				"fieldtype": "Link",
				"insert_after": "mra_qr_code",
				"label": "MRA Invoice Log",
				"no_copy": 1,
				"options": "MRA Invoice Log",
				"read_only": 1,
			},
		]
	}

	create_custom_fields(fields, ignore_validate=True)
