import frappe
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, today

OUTPUT_VALUE_BOXES=("1.1","1.2","1.3","1.4","3")
INPUT_VALUE_BOXES=("6.1","6.2","6.3","6.4","6.5","6.6","7","8.1","8.2")
INPUT_VAT_BOXES=("6.1","6.3","6.4","6.6","7")

def execute(filters=None):
	filters=frappe._dict(filters or {})
	company=filters.get("company")
	if not company: frappe.throw("Company is required.")
	from_date,to_date=get_period(filters)
	currency=frappe.db.get_value("Company",company,"default_currency") or ""
	box={key:0.0 for key in OUTPUT_VALUE_BOXES+INPUT_VALUE_BOXES}
	vat={"1.4":0.0,"6.1":0.0,"6.3":0.0,"6.4":0.0,"6.6":0.0,"7":0.0}
	sales=get_invoice_items("Sales Invoice","Sales Invoice Item",company,from_date,to_date)
	purchases=get_invoice_items("Purchase Invoice","Purchase Invoice Item",company,from_date,to_date,True)
	validate_classification(sales,"Sales Invoice")
	validate_classification(purchases,"Purchase Invoice")
	for row in sales:
		if row.vat_return_type in OUTPUT_VALUE_BOXES: box[row.vat_return_type]+=flt(row.base_net_amount)
	for row in purchases:
		if row.vat_return_type in INPUT_VALUE_BOXES: box[row.vat_return_type]+=flt(row.base_net_amount)
	vat["1.4"]=get_sales_vat(company,from_date,to_date)
	for key,value in allocate_purchase_vat(company,from_date,to_date,purchases).items(): vat[key]=value
	box["7"]+=vat["7"]
	b2=flt(filters.get("deferred_vat_on_importation")); b4=flt(filters.get("penalty_on_excess_overclaimed"))
	b5v=sum(box[k] for k in OUTPUT_VALUE_BOXES); b5t=vat["1.4"]+b2+b4
	b9v=sum(box[k] for k in INPUT_VALUE_BOXES); b9t=vat["6.1"]+vat["6.3"]+vat["6.4"]+vat["6.6"]
	pa=flt(filters.get("proportion_allowable")); pc=flt(filters.get("proportion_claimable")); b10=b9t*pa/100.0
	b11=b5t-b10
	manual_b12=filters.get("excess_vat_brought_forward")
	b12=flt(manual_b12) if manual_b12 not in (None,"") else get_excess_vat_brought_forward(company,from_date)
	b13=flt(filters.get("vat_adjustment")); raw=b11-b12+b13
	b151=flt(filters.get("repayment_on_capital_goods")); b152=flt(filters.get("repayment_on_other_goods")); b153=b151+b152
	b17=flt(filters.get("penalty_late_submission")); b18=flt(filters.get("penalty_for_period"))
	if raw>=0: b14=raw+b17+b18; b16=0.0
	else: b14=b17+b18; b16=-raw-b153
	return get_columns(),build_rows(box,vat,b2,b4,b5v,b5t,b9v,b9t,b10,b11,b12,b13,b14,b151,b152,b153,b16,b17,b18,pa,pc,currency)

def get_period(filters):
	span=filters.get("time_span") or "Last Month"; current=today()
	if span=="This Month": return get_first_day(current),get_last_day(current)
	if span=="Last Month":
		previous=add_months(current,-1); return get_first_day(previous),get_last_day(previous)
	months=(getdate(current).month-1)%3; quarter=get_first_day(add_months(current,-months))
	if span=="This Quarter": return quarter,get_last_day(add_months(quarter,2))
	if span=="Last Quarter":
		start=add_months(quarter,-3); return start,get_last_day(add_months(start,2))
	if span=="Custom Period":
		start=filters.get("from_date"); end=filters.get("to_date")
		if not start or not end: frappe.throw("From Date and To Date are required for Custom Period.")
		if getdate(start)>getdate(end): frappe.throw("From Date cannot be after To Date.")
		return start,end
	frappe.throw("Unsupported Taxable Period.")

def get_invoice_items(parent_doctype,child_doctype,company,from_date,to_date,use_vat_claim_date=False):
	Parent=frappe.qb.DocType(parent_doctype); Child=frappe.qb.DocType(child_doctype)
	query=(frappe.qb.from_(Child).join(Parent).on(Child.parent==Parent.name).select(Child.parent,Child.idx,Child.item_code,Child.base_net_amount,Child.vat_return_type).where(Parent.docstatus==1).where(Parent.company==company))
	if use_vat_claim_date:
		query=query.where(Child.vat_claim_date>=from_date).where(Child.vat_claim_date<=to_date)
	else:
		query=query.where(Parent.posting_date>=from_date).where(Parent.posting_date<=to_date)
	if frappe.get_meta(parent_doctype).has_field("is_opening"): query=query.where(Parent.is_opening!="Yes")
	return query.run(as_dict=True)

def validate_classification(rows,parent_doctype):
	missing=[]
	for row in rows:
		if not row.vat_return_type:
			missing.append("row "+str(row.idx)+" of "+row.parent)
			if len(missing)>=20: break
	if missing: frappe.throw(parent_doctype+" items are missing VAT Return Type: "+", ".join(missing)+". Update the invoice item classification before generating the VAT Return.")

def get_previous_vat_return_filing(company,from_date):
	previous=frappe.get_all(
		"VAT Return Filing",
		filters={
			"company": company,
			"docstatus": 1,
			"to_date": ["<", from_date],
		},
		fields=["name","box_16_excess_carried_forward"],
		order_by="to_date desc",
		limit=1,
	)
	return previous[0] if previous else None


def get_excess_vat_brought_forward(company,from_date):
	previous=get_previous_vat_return_filing(company,from_date)
	if not previous: return 0.0
	return flt(previous.box_16_excess_carried_forward)

def get_sales_vat(company,from_date,to_date):
	Invoice=frappe.qb.DocType("Sales Invoice"); Taxes=frappe.qb.DocType("Sales Taxes and Charges")
	rows=(frappe.qb.from_(Taxes).join(Invoice).on(Taxes.parent==Invoice.name).select(Taxes.base_tax_amount_after_discount_amount).where(Taxes.parenttype=="Sales Invoice").where(Invoice.docstatus==1).where(Invoice.company==company).where(Invoice.posting_date>=from_date).where(Invoice.posting_date<=to_date).where(Invoice.is_opening!="Yes").run(as_dict=True))
	return sum(flt(row.base_tax_amount_after_discount_amount) for row in rows)

def allocate_purchase_vat(company,from_date,to_date,purchases):
	invoice_names=[]
	selected_net={}
	for row in purchases:
		if row.parent not in invoice_names: invoice_names.append(row.parent)
		if row.vat_return_type not in INPUT_VAT_BOXES: continue
		selected_net.setdefault(row.parent,{})
		selected_net[row.parent].setdefault(row.vat_return_type,0.0)
		selected_net[row.parent][row.vat_return_type]+=flt(row.base_net_amount)
	allocated={key:0.0 for key in INPUT_VAT_BOXES}
	if not invoice_names: return allocated
	Item=frappe.qb.DocType("Purchase Invoice Item")
	all_items=(frappe.qb.from_(Item).select(Item.parent,Item.base_net_amount,Item.vat_return_type).where(Item.parent.isin(invoice_names)).run(as_dict=True))
	invoice_total_net={}
	for row in all_items:
		if row.vat_return_type not in INPUT_VAT_BOXES: continue
		invoice_total_net[row.parent]=invoice_total_net.get(row.parent,0.0)+flt(row.base_net_amount)
	Invoice=frappe.qb.DocType("Purchase Invoice"); Taxes=frappe.qb.DocType("Purchase Taxes and Charges")
	rows=(frappe.qb.from_(Taxes).join(Invoice).on(Taxes.parent==Invoice.name).select(Taxes.parent,Taxes.add_deduct_tax,Taxes.base_tax_amount_after_discount_amount).where(Taxes.parenttype=="Purchase Invoice").where(Invoice.docstatus==1).where(Invoice.company==company).where(Invoice.name.isin(invoice_names)).where(Invoice.is_opening!="Yes").run(as_dict=True))
	invoice_vat={}
	for row in rows:
		amount=flt(row.base_tax_amount_after_discount_amount)
		if row.add_deduct_tax=="Deduct": amount=-amount
		invoice_vat[row.parent]=invoice_vat.get(row.parent,0.0)+amount
	for name,total_vat in invoice_vat.items():
		total_net=invoice_total_net.get(name) or 0.0
		if not total_net: continue
		for target,net in (selected_net.get(name) or {}).items():
			allocated[target]+=total_vat*net/total_net
	return allocated

def get_columns():
	return [{"label":"Box","fieldname":"box","fieldtype":"Data","width":70},{"label":"Description","fieldname":"description","fieldtype":"Data","width":460},{"label":"Value","fieldname":"value_amount","fieldtype":"Currency","options":"currency","width":170,"precision":0},{"label":"VAT","fieldname":"vat_amount","fieldtype":"Currency","options":"currency","width":170,"precision":0},{"label":"Currency","fieldname":"currency","fieldtype":"Data","hidden":1}]

def build_rows(box,vat,b2,b4,b5v,b5t,b9v,b9t,b10,b11,b12,b13,b14,b151,b152,b153,b16,b17,b18,pa,pc,currency):
	lines=[("","OUTPUT - Taxable supplies "+str(pa)+" % of total annual turnover",None,None,"SECTION"),("1","Taxable Supplies",None,None,"GROUP"),("1.1","      Zero-rated supplies (Exports)",box["1.1"],None,""),("1.2","      Zero-rated supplies other than exports",box["1.2"],None,""),("1.3","      Taxable supplies made to exempt bodies or persons",box["1.3"],None,""),("1.4","      Other Taxable supplies",box["1.4"],vat["1.4"],""),("2","Deferred VAT on Importation",None,b2,""),("3","Exempt Supplies",box["3"],None,""),("4","Penalty on excess amount overclaimed",None,b4,""),("5","TOTAL",b5v,b5t,"TOTAL"),("","INPUT - Imports and Purchases",None,None,"SECTION"),("6","Taxable input on which input tax is allowed as a credit",None,None,"GROUP"),("6.1","      Capital goods imported",box["6.1"],vat["6.1"],""),("6.2","      Zero-rated imports",box["6.2"],None,""),("6.3","      Other imports",box["6.3"],vat["6.3"],""),("6.4","      Capital goods purchased locally",box["6.4"],vat["6.4"],""),("6.5","      Zero-rated goods and services purchased locally",box["6.5"],None,""),("6.6","      Other goods and services purchased locally",box["6.6"],vat["6.6"],""),("7","Taxable input on which no input tax is allowed as a credit",box["7"],None,""),("8","Exempt input",None,None,"GROUP"),("8.1","      Imported goods",box["8.1"],None,""),("8.2","      Goods & services purchased locally",box["8.2"],None,""),("9","Total",b9v,b9t,"TOTAL"),("10","Input tax deductible - Proportion allowable "+str(pa)+" %",None,b10,""),("","VAT ACCOUNT",None,None,"SECTION"),("11","VAT payable for the taxable period",None,b11,""),("12","(Excess VAT brought forward)",None,b12,""),("13","VAT Adjustment - Decrease",None,b13,""),("14","VAT due and payable",None,b14,"TOTAL"),("15","Claim for repayment - Proportion claimable "+str(pc)+" %",None,None,"GROUP"),("15.1","      On capital goods",None,b151,""),("15.2","      In respect of other goods and services",None,b152,""),("15.3","      Total repayment claimed",None,b153,"TOTAL"),("16","Excess VAT Carried forward",None,b16,""),("17","Penalty late submission after due date",None,b17,""),("18","Penalty for the month / quarter shown above",None,b18,"")]
	data=[]
	for number,description,value_amount,vat_amount,style in lines:
		data.append({"box":number,"description":description,"value_amount":None if value_amount is None else flt(value_amount,0),"vat_amount":None if vat_amount is None else flt(vat_amount,0),"currency":currency,"is_section":1 if style=="SECTION" else 0,"is_group":1 if style=="GROUP" else 0,"is_total":1 if style=="TOTAL" else 0})
	return data
