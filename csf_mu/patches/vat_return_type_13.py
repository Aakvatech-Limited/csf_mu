"""Ensure Box 13 can be selected on Purchase Invoice Items."""

import frappe


def execute():
    if frappe.db.exists("VAT Return Type", "13"):
        return
    frappe.get_doc({
        "doctype": "VAT Return Type",
        "box_number": "13",
        "title": "Prior-period input VAT adjustment",
        "transaction_type": "Purchase",
        "description": "Late-received prior-period purchase VAT claimed through Box 13.",
    }).insert(ignore_permissions=True)
