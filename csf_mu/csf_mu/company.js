frappe.ui.form.on("Company", {
	refresh(frm) {
		frm.add_custom_button(__("Create MRA Item Tax Templates"), () => {
			frappe.call({
				method: "csf_mu.csf_mu.custom_api.create_mra_item_tax_templates",
				args: {
					company: frm.doc.name,
				},
				callback(r) {
					if (!r.exc) {
						frappe.msgprint(__("MRA Item Tax Templates created/updated."));
					}
				},
			});
		});
	},
});
