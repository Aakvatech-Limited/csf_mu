import frappe

from csf_mu.csf_mu.utils.vat_dashboard import PURCHASE_BOXES, get_box_values


@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None, **kwargs):
	return get_box_values("Purchase Invoice", "Purchase Invoice Item", PURCHASE_BOXES, filters)
