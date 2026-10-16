frappe.ui.form.on("VAT Return Filing", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(
				__("Pull Transactions"),
				() => {
					frappe.confirm(
						__(
							"Refresh source transactions for this draft filing? The sales and purchase detail snapshots will be replaced; manual adjustment rows remain."
						),
						() =>
							frm.call("pull_transactions").then((r) => {
								frm.reload_doc();
								if (r.message) {
									frappe.show_alert({
										message: __(
											"Pulled {0} sales items and {1} purchase items",
											[r.message.sales_items, r.message.purchase_items]
										),
										indicator: "green",
									});
								}
							})
					);
				},
				__("VAT Filing")
			);
			frm.add_custom_button(
				__("Backfill Missing VAT Return Types"),
				() => {
					frappe.confirm(
						__(
							"Fill blank VAT Return Types from Item Tax Templates for submitted invoices eligible in this filing month? Existing classifications will not be overwritten."
						),
						() =>
							frm.call("backfill_missing_vat_types").then((r) => {
								const result = r.message || {};
								frappe.msgprint({
									title: __("Period VAT Classification Backfill"),
									message: __(
										"Sales items updated: {0}<br>Purchase items updated: {1}<br>Already classified: {2}<br>Missing Item Tax Template: {3}<br>Unmapped Item Tax Template: {4}<br>Locked: {5}<br>Capital goods: {6}<br><br>Click Pull Transactions to refresh this draft filing.",
										[
											result.sales_updated || 0,
											result.purchases_updated || 0,
											result.already_classified || 0,
											result.missing_item_tax_template || 0,
											result.unmapped_item_tax_template || 0,
											result.locked || 0,
											result.capital_goods || 0,
										]
									),
								});
							})
					);
				},
				__("VAT Filing")
			);
			frm.add_custom_button(
				__("Recalculate"),
				() => {
					frm.call("recalculate").then(() => frm.reload_doc());
				},
				__("VAT Filing")
			);
		}
		if (frm.is_new()) return;
		frm.add_custom_button(
			__("View Breakdown"),
			() => {
				const box = frappe.prompt(
					[
						{
							fieldname: "mra_box",
							label: __("MRA Box"),
							fieldtype: "Select",
							options: (frm.doc.lines || []).map((row) => row.box).filter(Boolean),
							reqd: 1,
						},
					],
					(values) => {
						frm.call("get_breakdown", { box: values.mra_box }).then((r) => {
							const rows = r.message || [];
							const d = new frappe.ui.Dialog({
								title: __("MRA Box {0} - {1} Items", [
									values.mra_box,
									rows.length,
								]),
								size: "extra-large",
								fields: [{ fieldtype: "HTML", fieldname: "detail" }],
							});
							const esc = frappe.utils.escape_html;
							const tbody = rows
								.map((row) => {
									const route = frappe.utils.get_form_link(
										row.source_doctype,
										row.source_invoice,
										true
									);
									return `<tr><td><a href="${route}">${esc(
										row.source_invoice
									)}</a></td>
                            <td>${esc(row.party || "")}</td><td>${esc(row.item_code || "")}</td>
                            <td>${esc(row.posting_date || "")}</td><td>${esc(
										row.claim_date || ""
									)}</td>
                            <td class="text-right">${format_currency(
								row.taxable_value,
								frm.doc.currency
							)}</td>
                            <td class="text-right">${format_currency(
								row.vat_amount,
								frm.doc.currency
							)}</td></tr>`;
								})
								.join("");
							d.fields_dict.detail.$wrapper
								.html(`<div style="overflow:auto;max-height:65vh"><table class="table table-bordered">
                        <thead><tr><th>Invoice</th><th>Party</th><th>Item</th><th>Posting</th><th>Claim</th><th>Base</th><th>VAT</th></tr></thead><tbody>${tbody}</tbody></table></div>`);
							d.show();
						});
					},
					__("View")
				);
			},
			__("VAT Filing")
		);
		const query = new URLSearchParams({ name: frm.doc.name }).toString();
		frm.add_custom_button(
			__("Download Excel"),
			() =>
				window.open(
					"/api/method/csf_mu.csf_mu.utils.vat_filing_export.download_excel?" + query
				),
			__("Export")
		);
		frm.add_custom_button(
			__("Download MNS Annex"),
			() =>
				window.open(
					"/api/method/csf_mu.csf_mu.utils.vat_filing_export.download_mns_annex?" + query
				),
			__("Export")
		);
		frm.add_custom_button(
			__("Print MRA VAT Return"),
			() =>
				window.open(
					"/printview?doctype=VAT%20Return%20Filing&name=" +
						encodeURIComponent(frm.doc.name) +
						"&format=MRA%20VAT%20Return"
				),
			__("Export")
		);
	},
});
