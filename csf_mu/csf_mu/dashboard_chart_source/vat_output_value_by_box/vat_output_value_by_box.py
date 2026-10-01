import frappe

from csf_mu.csf_mu.utils.vat_dashboard import SALES_BOXES, get_box_values


@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None, **kwargs):
	return get_box_values("Sales Invoice", "Sales Invoice Item", SALES_BOXES, filters)
