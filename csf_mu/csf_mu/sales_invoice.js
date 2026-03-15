// Copyright (c) 2026, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		frm.trigger("load_prf_trn_setting");

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
	is_return(frm) {
		frm.trigger("set_mra_invoice_type");
	},
	is_debit_note(frm) {
		frm.trigger("set_mra_invoice_type");
	},
	company(frm) {
		frm.trigger("load_prf_trn_setting");
	},
	load_prf_trn_setting(frm) {
		if (!frm.doc.company) {
			frm._allow_prf_trn = false;
			frm.toggle_display("mra_invoice_type_desc", false);
			frm.trigger("set_mra_invoice_type");
			return;
		}
		frappe.call({
			method: "csf_mu.csf_mu.utils.mra_invoice.get_prf_trn_setting",
			args: { company: frm.doc.company },
			callback: (r) => {
				frm._allow_prf_trn = !!(r && r.message);
				frm.toggle_display("mra_invoice_type_desc", frm._allow_prf_trn);
				frm.trigger("set_mra_invoice_type");
			},
		});
	},
	set_mra_invoice_type(frm) {
		const is_return = !!frm.doc.is_return;
		const is_debit_note = !!frm.doc.is_debit_note;
		const allow_prf_trn = !!frm._allow_prf_trn;
		let invoice_type = frm.doc.mra_invoice_type_desc || "STD";
		if (is_return) {
			invoice_type = "CRN";
		} else if (is_debit_note) {
			invoice_type = "DRN";
		} else if (!allow_prf_trn) {
			invoice_type = "STD";
		} else if (!["STD", "PRF", "TRN"].includes(invoice_type)) {
			invoice_type = "STD";
		}

		if (frm.doc.mra_invoice_type_desc !== invoice_type) {
			frm.set_value("mra_invoice_type_desc", invoice_type);
			if (["CRN", "DRN"].includes(invoice_type)) {
				frappe.show_alert({
					message: __("MRA invoice type set to {0}", [invoice_type]),
					indicator: "orange",
				});
			}
		}

		const needs_ref = ["CRN", "DRN"].includes(invoice_type);
		frm.toggle_reqd("mra_reason_stated", needs_ref);
		frm.toggle_reqd("return_against", needs_ref);
	},
});
