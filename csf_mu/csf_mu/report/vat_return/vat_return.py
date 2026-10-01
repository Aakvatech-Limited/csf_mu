import frappe
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, today


OUTPUT_VALUE_BOXES = ("1.1", "1.2", "1.3", "1.4", "3")
INPUT_VALUE_BOXES = ("6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "7", "8.1", "8.2")
INPUT_VAT_BOXES = ("6.1", "6.3", "6.4", "6.6", "7")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	company = filters.get("company")
	if not company:
		frappe.throw("Company is required.")

	from_date, to_date = get_period(filters)
	company_currency = frappe.db.get_value("Company", company, "default_currency") or ""

	box = {key: 0.0 for key in OUTPUT_VALUE_BOXES + INPUT_VALUE_BOXES}
	vat = {"1.4": 0.0, "6.1": 0.0, "6.3": 0.0, "6.4": 0.0, "6.6": 0.0, "7": 0.0}

	sales_items = get_invoice_items("Sales Invoice", "Sales Invoice Item", company, from_date, to_date)
	purchase_items = get_invoice_items("Purchase Invoice", "Purchase Invoice Item", company, from_date, to_date)

	validate_classification(sales_items, "Sales Invoice")
	validate_classification(purchase_items, "Purchase Invoice")

	for row in sales_items:
		if row.vat_return_type in OUTPUT_VALUE_BOXES:
			box[row.vat_return_type] += flt(row.base_net_amount)

	for row in purchase_items:
		if row.vat_return_type in INPUT_VALUE_BOXES:
			box[row.vat_return_type] += flt(row.base_net_amount)

	vat["1.4"] = get_sales_vat(company, from_date, to_date)
	purchase_vat = allocate_purchase_vat(company, from_date, to_date, purchase_items)
	for target_box in purchase_vat:
		vat[target_box] = purchase_vat[target_box]

	# MRA Box 7 reports non-claimable input inclusive of the disallowed VAT.
	box["7"] += vat["7"]

	box_2_vat = flt(filters.get("deferred_vat_on_importation"))
	box_4_vat = flt(filters.get("penalty_on_excess_overclaimed"))

	box_5_value = sum(box[key] for key in OUTPUT_VALUE_BOXES)
	box_5_vat = vat["1.4"] + box_2_vat + box_4_vat

	box_9_value = sum(box[key] for key in INPUT_VALUE_BOXES)
	box_9_vat = vat["6.1"] + vat["6.3"] + vat["6.4"] + vat["6.6"]

	proportion_allowable = flt(filters.get("proportion_allowable"))
	proportion_claimable = flt(filters.get("proportion_claimable"))
	box_10_vat = box_9_vat * proportion_allowable / 100.0

	box_11 = box_5_vat - box_10_vat
	box_12 = flt(filters.get("excess_vat_brought_forward"))
	box_13 = flt(filters.get("vat_adjustment"))
	box_14_raw = box_11 - box_12 + box_13

	box_15_1 = flt(filters.get("repayment_on_capital_goods"))
	box_15_2 = flt(filters.get("repayment_on_other_goods"))
	box_15_3 = box_15_1 + box_15_2
	box_17 = flt(filters.get("penalty_late_submission"))
	box_18 = flt(filters.get("penalty_for_period"))

	if box_14_raw >= 0:
		box_14 = box_14_raw + box_17 + box_18
		box_16 = 0.0
	else:
		box_14 = box_17 + box_18
		box_16 = -box_14_raw - box_15_3

	rows = build_rows(
		box,
		vat,
		box_2_vat,
		box_4_vat,
		box_5_value,
		box_5_vat,
		box_9_value,
		box_9_vat,
		box_10_vat,
		box_11,
		box_12,
		box_13,
		box_14,
		box_15_1,
		box_15_2,
		box_15_3,
		box_16,
		box_17,
		box_18,
		proportion_allowable,
		proportion_claimable,
		company_currency,
	)
	return get_columns(), rows


def get_period(filters):
	time_span = filters.get("time_span") or "Last Month"
	current_date = today()

	if time_span == "This Month":
		return get_first_day(current_date), get_last_day(current_date)

	if time_span == "Last Month":
		previous_month = add_months(current_date, -1)
		return get_first_day(previous_month), get_last_day(previous_month)

	months_into_quarter = (getdate(current_date).month - 1) % 3
	this_quarter_start = get_first_day(add_months(current_date, -months_into_quarter))

	if time_span == "This Quarter":
		return this_quarter_start, get_last_day(add_months(this_quarter_start, 2))

	if time_span == "Last Quarter":
		from_date = add_months(this_quarter_start, -3)
		return from_date, get_last_day(add_months(from_date, 2))

	if time_span == "Custom Period":
		from_date = filters.get("from_date")
		to_date = filters.get("to_date")
		if not from_date or not to_date:
			frappe.throw("From Date and To Date are required for Custom Period.")
		if getdate(from_date) > getdate(to_date):
			frappe.throw("From Date cannot be after To Date.")
		return from_date, to_date

	frappe.throw("Unsupported Taxable Period.")


def get_invoice_items(parent_doctype, child_doctype, company, from_date, to_date):
	Parent = frappe.qb.DocType(parent_doctype)
	Child = frappe.qb.DocType(child_doctype)
	query = (
		frappe.qb.from_(Child)
		.join(Parent)
		.on(Child.parent == Parent.name)
		.select(
			Child.parent,
			Child.idx,
			Child.item_code,
			Child.base_net_amount,
			Child.vat_return_type,
		)
		.where(Parent.docstatus == 1)
		.where(Parent.company == company)
		.where(Parent.posting_date >= from_date)
		.where(Parent.posting_date <= to_date)
	)
	if frappe.get_meta(parent_doctype).has_field("is_opening"):
		query = query.where(Parent.is_opening != "Yes")
	return query.run(as_dict=True)


def validate_classification(rows, parent_doctype):
	missing = []
	for row in rows:
		if not row.vat_return_type:
			missing.append("row " + str(row.idx) + " of " + row.parent)
			if len(missing) >= 20:
				break
	if missing:
		frappe.throw(
			parent_doctype
			+ " items are missing VAT Return Type: "
			+ ", ".join(missing)
			+ ". Update the invoice item classification before generating the VAT Return."
		)


def get_sales_vat(company, from_date, to_date):
	SalesInvoice = frappe.qb.DocType("Sales Invoice")
	Taxes = frappe.qb.DocType("Sales Taxes and Charges")
	rows = (
		frappe.qb.from_(Taxes)
		.join(SalesInvoice)
		.on(Taxes.parent == SalesInvoice.name)
		.select(Taxes.base_tax_amount_after_discount_amount)
		.where(Taxes.parenttype == "Sales Invoice")
		.where(SalesInvoice.docstatus == 1)
		.where(SalesInvoice.company == company)
		.where(SalesInvoice.posting_date >= from_date)
		.where(SalesInvoice.posting_date <= to_date)
		.where(SalesInvoice.is_opening != "Yes")
		.run(as_dict=True)
	)
	return sum(flt(row.base_tax_amount_after_discount_amount) for row in rows)


def allocate_purchase_vat(company, from_date, to_date, purchase_items):
	invoice_box_net = {}
	for row in purchase_items:
		if row.vat_return_type not in INPUT_VAT_BOXES:
			continue
		invoice_box_net.setdefault(row.parent, {})
		invoice_box_net[row.parent].setdefault(row.vat_return_type, 0.0)
		invoice_box_net[row.parent][row.vat_return_type] += flt(row.base_net_amount)

	PurchaseInvoice = frappe.qb.DocType("Purchase Invoice")
	Taxes = frappe.qb.DocType("Purchase Taxes and Charges")
	tax_rows = (
		frappe.qb.from_(Taxes)
		.join(PurchaseInvoice)
		.on(Taxes.parent == PurchaseInvoice.name)
		.select(
			Taxes.parent,
			Taxes.add_deduct_tax,
			Taxes.base_tax_amount_after_discount_amount,
		)
		.where(Taxes.parenttype == "Purchase Invoice")
		.where(PurchaseInvoice.docstatus == 1)
		.where(PurchaseInvoice.company == company)
		.where(PurchaseInvoice.posting_date >= from_date)
		.where(PurchaseInvoice.posting_date <= to_date)
		.where(PurchaseInvoice.is_opening != "Yes")
		.run(as_dict=True)
	)

	invoice_vat = {}
	for row in tax_rows:
		amount = flt(row.base_tax_amount_after_discount_amount)
		if row.add_deduct_tax == "Deduct":
			amount = -amount
		invoice_vat[row.parent] = invoice_vat.get(row.parent, 0.0) + amount

	allocated = {key: 0.0 for key in INPUT_VAT_BOXES}
	for invoice_name in invoice_vat:
		box_net = invoice_box_net.get(invoice_name) or {}
		total_net = sum(box_net.values())
		if not total_net:
			continue
		for target_box in box_net:
			allocated[target_box] += invoice_vat[invoice_name] * box_net[target_box] / total_net

	return allocated


def get_columns():
	return [
		{"label": "Box", "fieldname": "box", "fieldtype": "Data", "width": 70},
		{"label": "Description", "fieldname": "description", "fieldtype": "Data", "width": 460},
		{
			"label": "Value",
			"fieldname": "value_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 170,
			"precision": 2,
		},
		{
			"label": "VAT",
			"fieldname": "vat_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 170,
			"precision": 2,
		},
		{"label": "Currency", "fieldname": "currency", "fieldtype": "Data", "hidden": 1},
	]


def build_rows(
	box,
	vat,
	box_2_vat,
	box_4_vat,
	box_5_value,
	box_5_vat,
	box_9_value,
	box_9_vat,
	box_10_vat,
	box_11,
	box_12,
	box_13,
	box_14,
	box_15_1,
	box_15_2,
	box_15_3,
	box_16,
	box_17,
	box_18,
	proportion_allowable,
	proportion_claimable,
	currency,
):
	lines = [
		("", "OUTPUT - Taxable supplies " + str(proportion_allowable) + " % of total annual turnover", None, None, "SECTION"),
		("1", "Taxable Supplies", None, None, "GROUP"),
		("1.1", "      Zero-rated supplies (Exports)", box["1.1"], None, ""),
		("1.2", "      Zero-rated supplies other than exports", box["1.2"], None, ""),
		("1.3", "      Taxable supplies made to exempt bodies or persons", box["1.3"], None, ""),
		("1.4", "      Other Taxable supplies", box["1.4"], vat["1.4"], ""),
		("2", "Deferred VAT on Importation", None, box_2_vat, ""),
		("3", "Exempt Supplies", box["3"], None, ""),
		("4", "Penalty on excess amount overclaimed", None, box_4_vat, ""),
		("5", "TOTAL", box_5_value, box_5_vat, "TOTAL"),
		("", "INPUT - Imports and Purchases", None, None, "SECTION"),
		("6", "Taxable input on which input tax is allowed as a credit", None, None, "GROUP"),
		("6.1", "      Capital goods imported", box["6.1"], vat["6.1"], ""),
		("6.2", "      Zero-rated imports", box["6.2"], None, ""),
		("6.3", "      Other imports", box["6.3"], vat["6.3"], ""),
		("6.4", "      Capital goods purchased locally", box["6.4"], vat["6.4"], ""),
		("6.5", "      Zero-rated goods and services purchased locally", box["6.5"], None, ""),
		("6.6", "      Other goods and services purchased locally", box["6.6"], vat["6.6"], ""),
		("7", "Taxable input on which no input tax is allowed as a credit", box["7"], None, ""),
		("8", "Exempt input", None, None, "GROUP"),
		("8.1", "      Imported goods", box["8.1"], None, ""),
		("8.2", "      Goods & services purchased locally", box["8.2"], None, ""),
		("9", "Total", box_9_value, box_9_vat, "TOTAL"),
		("10", "Input tax deductible - Proportion allowable " + str(proportion_allowable) + " %", None, box_10_vat, ""),
		("", "VAT ACCOUNT", None, None, "SECTION"),
		("11", "VAT payable for the taxable period", None, box_11, ""),
		("12", "(Excess VAT brought forward)", None, box_12, ""),
		("13", "VAT Adjustment - Decrease", None, box_13, ""),
		("14", "VAT due and payable", None, box_14, "TOTAL"),
		("15", "Claim for repayment - Proportion claimable " + str(proportion_claimable) + " %", None, None, "GROUP"),
		("15.1", "      On capital goods", None, box_15_1, ""),
		("15.2", "      In respect of other goods and services", None, box_15_2, ""),
		("15.3", "      Total repayment claimed", None, box_15_3, "TOTAL"),
		("16", "Excess VAT Carried forward", None, box_16, ""),
		("17", "Penalty late submission after due date", None, box_17, ""),
		("18", "Penalty for the month / quarter shown above", None, box_18, ""),
	]

	data = []
	for box_number, description, value_amount, vat_amount, style in lines:
		data.append(
			{
				"box": box_number,
				"description": description,
				"value_amount": value_amount,
				"vat_amount": vat_amount,
				"currency": currency,
				"is_section": 1 if style == "SECTION" else 0,
				"is_group": 1 if style == "GROUP" else 0,
				"is_total": 1 if style == "TOTAL" else 0,
			}
		)
	return data
