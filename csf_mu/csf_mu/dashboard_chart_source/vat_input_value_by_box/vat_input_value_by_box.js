frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["VAT Input Value by Box"] = {
	method: "csf_mu.csf_mu.dashboard_chart_source.vat_input_value_by_box.vat_input_value_by_box.get",
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
	],
};
