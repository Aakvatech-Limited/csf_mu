frappe.ui.form.on("CSF MU Settings", {
	refresh(frm) {
		toggle_runtime_fields(frm);
	},
	token(frm) {
		toggle_runtime_fields(frm);
	},
	token_expiry(frm) {
		toggle_runtime_fields(frm);
	}
});

function toggle_runtime_fields(frm) {
	const has_token = !!frm.doc.token;
	const has_expiry = !!frm.doc.token_expiry;
	frm.toggle_display("token", has_token);
	frm.toggle_display("token_expiry", has_expiry);
}
