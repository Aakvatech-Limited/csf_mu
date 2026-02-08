// Copyright (c) 2026, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) {
			return;
		}

		const status = (frm.doc.mra_status || "").toUpperCase();
		if (!["ERROR", "ERRORS"].includes(status)) {
			return;
		}

		frm.add_custom_button(__("Re-Send to MRA"), () => {
			frappe.call({
				method: "csf_mu.csf_mu.utils.mra_invoice.resend_invoice_to_mra",
				args: { sales_invoice: frm.doc.name },
				freeze: true,
				callback: () => {
					frm.reload_doc();
				},
			});
		}, __("MRA"));
	},
});
