frappe.query_reports["Return of Employees (ROE)"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: getPayrollYearRange().from_date,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: getPayrollYearRange().to_date,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
			get_query: () => {
				const company = frappe.query_report.get_filter_value("company");
				return company ? { filters: { company } } : {};
			},
		},
		{
			fieldname: "designation",
			label: __("Designation"),
			fieldtype: "Link",
			options: "Designation",
		},
	],
};

function getPayrollYearRange() {
	const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
	const year = today.getMonth() >= 6 ? today.getFullYear() : today.getFullYear() - 1;
	return {
		from_date: `${year}-07-01`,
		to_date: `${year + 1}-06-30`,
	};
}
