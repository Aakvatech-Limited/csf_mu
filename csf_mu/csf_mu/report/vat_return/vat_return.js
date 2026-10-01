frappe.query_reports["VAT Return"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "time_span",
			label: __("Taxable Period"),
			fieldtype: "Select",
			options: ["This Month", "Last Month", "This Quarter", "Last Quarter", "Custom Period"],
			default: "Last Month",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.time_span == 'Custom Period'",
			mandatory_depends_on: "eval:doc.time_span == 'Custom Period'",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.time_span == 'Custom Period'",
			mandatory_depends_on: "eval:doc.time_span == 'Custom Period'",
		},
		{
			fieldname: "proportion_allowable",
			label: __("Proportion Allowable (%)"),
			fieldtype: "Float",
			default: 100,
			reqd: 1,
		},
		{
			fieldname: "deferred_vat_on_importation",
			label: __("Box 2 - Deferred VAT on Importation"),
			fieldtype: "Currency",
		},
		{
			fieldname: "penalty_on_excess_overclaimed",
			label: __("Box 4 - Penalty on Excess Overclaimed"),
			fieldtype: "Currency",
		},
		{
			fieldname: "excess_vat_brought_forward",
			label: __("Box 12 - Excess VAT Brought Forward"),
			fieldtype: "Currency",
		},
		{
			fieldname: "vat_adjustment",
			label: __("Box 13 - VAT Adjustment"),
			fieldtype: "Currency",
		},
		{
			fieldname: "proportion_claimable",
			label: __("Proportion Claimable (%)"),
			fieldtype: "Float",
		},
		{
			fieldname: "repayment_on_capital_goods",
			label: __("Box 15.1 - Repayment on Capital Goods"),
			fieldtype: "Currency",
		},
		{
			fieldname: "repayment_on_other_goods",
			label: __("Box 15.2 - Repayment on Other Goods & Services"),
			fieldtype: "Currency",
		},
		{
			fieldname: "penalty_late_submission",
			label: __("Box 17 - Penalty Late Submission"),
			fieldtype: "Currency",
		},
		{
			fieldname: "penalty_for_period",
			label: __("Box 18 - Penalty for the Period"),
			fieldtype: "Currency",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (data && data.is_section) {
			return "<span style='font-weight:700;'>" + value + "</span>";
		}
		if (data && (data.is_total || data.is_group)) {
			return "<strong>" + value + "</strong>";
		}
		return value;
	},
};
