// Copyright (c) 2026, Aakvatech and contributors
// For license information, please see license.txt

frappe.listview_settings["Sales Invoice"] = {
	onload(listview) {
		listview.page.add_action_item(__("Send to MRA (Batch Request)"), () => {
			const checked = listview.get_checked_items();
			if (!checked.length) {
				frappe.msgprint(__("Select one or more Sales Invoices first."));
				return;
			}

			const names = checked.map((row) => row.name);
			frappe.confirm(
				__("Send {0} invoice(s) to MRA in a single request?", [names.length]),
				() => {
					frappe.call({
						method: "csf_mu.csf_mu.utils.mra_invoice.batch_transmit_invoices",
						args: { sales_invoices: names },
						freeze: true,
						freeze_message: __("Queuing batch transmit..."),
						queued: (r) => {
							const queued = (r.message && r.message.queued) || names.length;
							const skipped = (r.message && r.message.skipped) || [];
							const task_id = r.task_id;
							frappe.show_alert({
								message: __("Queued {0} invoice(s) for batch transmit.", [queued]),
								indicator: "blue",
							});
							if (skipped.length) {
								frappe.msgprint(
									__("Skipped {0} invoice(s) already SUCCESS.", [skipped.length])
								);
							}

							if (task_id) {
								const handler = (data) => {
									if (data.task_id !== task_id) {
										return;
									}
									if (data.percent >= 100) {
										setTimeout(() => listview.refresh(), 500);
										frappe.realtime.off("progress", handler);
									}
								};
								frappe.realtime.on("progress", handler);
							}
						},
						callback: (r) => {
							if (r && r.exc) {
								frappe.msgprint(__("Batch transmit failed. See error logs."));
							}
						},
					});
				}
			);
		});
	},
};
