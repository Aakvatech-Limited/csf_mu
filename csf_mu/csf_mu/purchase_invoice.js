function set_missing_vat_claim_dates(frm) {
	if (!frm.doc.posting_date) {
		return;
	}

	(frm.doc.items || []).forEach((row) => {
		if (!row.vat_claim_date) {
			frappe.model.set_value(
				row.doctype,
				row.name,
				"vat_claim_date",
				frm.doc.posting_date
			);
		}
	});
}

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		set_missing_vat_claim_dates(frm);
	},

	posting_date(frm) {
		set_missing_vat_claim_dates(frm);
	},

	items_add(frm) {
		set_missing_vat_claim_dates(frm);
	},
});
