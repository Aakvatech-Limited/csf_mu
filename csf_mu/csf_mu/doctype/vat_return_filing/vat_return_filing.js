frappe.ui.form.on("VAT Return Filing", {
    refresh(frm) {
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frm.add_custom_button(__("Pull Transactions"), () => {
                frappe.confirm(
                    __("Refresh source transactions for this draft filing? The sales and purchase detail snapshots will be replaced, and manually entered values in Boxes 12 and 16 will be reset to calculated amounts. Manual adjustment rows remain."),
                    () => frm.call("pull_transactions").then(r => {
                        frm.reload_doc();
                        if (r.message) {
                            frappe.show_alert({
                                message: __("Pulled {0} sales items and {1} purchase items", [
                                    r.message.sales_items, r.message.purchase_items,
                                ]),
                                indicator: "green",
                            });
                        }
                    })
                );
            }, __("VAT Filing"));
            frm.add_custom_button(__("Recalculate"), () => {
                frappe.confirm(
                    __("Recalculate this VAT return? Manually entered values in Boxes 12 and 16 will be replaced by calculated amounts."),
                    () => frm.call("recalculate").then(() => frm.reload_doc())
                );
            }, __("VAT Filing"));
        }
        if (frm.is_new()) return;
        frm.add_custom_button(__("View Breakdown"), () => {
            const box = frappe.prompt([{
                fieldname: "mra_box", label: __("MRA Box"), fieldtype: "Select",
                options: (frm.doc.lines || []).map(row => row.box).filter(Boolean),
                reqd: 1,
            }], values => {
                frm.call("get_breakdown", {box: values.mra_box}).then(r => {
                    const rows = r.message || [];
                    const d = new frappe.ui.Dialog({
                        title: __("MRA Box {0} - {1} Items", [values.mra_box, rows.length]),
                        size: "extra-large",
                        fields: [{fieldtype: "HTML", fieldname: "detail"}],
                    });
                    const esc = frappe.utils.escape_html;
                    const tbody = rows.map(row => {
                        const route = frappe.utils.get_form_link(row.source_doctype, row.source_invoice, true);
                        return `<tr><td><a href="${route}">${esc(row.source_invoice)}</a></td>
                            <td>${esc(row.party || "")}</td><td>${esc(row.item_code || "")}</td>
                            <td>${esc(row.posting_date || "")}</td><td>${esc(row.claim_date || "")}</td>
                            <td class="text-right">${format_currency(row.taxable_value, frm.doc.currency)}</td>
                            <td class="text-right">${format_currency(row.vat_amount, frm.doc.currency)}</td></tr>`;
                    }).join("");
                    d.fields_dict.detail.$wrapper.html(`<div style="overflow:auto;max-height:65vh"><table class="table table-bordered">
                        <thead><tr><th>Invoice</th><th>Party</th><th>Item</th><th>Posting</th><th>Claim</th><th>Base</th><th>VAT</th></tr></thead><tbody>${tbody}</tbody></table></div>`);
                    d.show();
                });
            }, __("View"));
        }, __("VAT Filing"));
        const query = new URLSearchParams({name: frm.doc.name}).toString();
        frm.add_custom_button(__("Download Excel"), () =>
            window.open("/api/method/csf_mu.csf_mu.utils.vat_filing_export.download_excel?" + query)
        , __("Export"));
        frm.add_custom_button(__("Download MNS Annex"), () =>
            window.open("/api/method/csf_mu.csf_mu.utils.vat_filing_export.download_mns_annex?" + query)
        , __("Export"));
        frm.add_custom_button(__("Print MRA VAT Return"), () =>
            window.open("/printview?doctype=VAT%20Return%20Filing&name=" + encodeURIComponent(frm.doc.name) + "&format=MRA%20VAT%20Return")
        , __("Export"));
    },
});
