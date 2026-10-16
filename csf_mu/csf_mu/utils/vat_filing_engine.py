"""Transaction snapshots and tax calculations for Mauritius VAT filings.

Never infer an invoice's VAT allocation from withholding tax or invoice grand totals.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

import frappe
from frappe.utils import flt, getdate


SALES_BOXES = ("1.1", "1.2", "1.3", "1.4", "3")
PURCHASE_BOXES = ("6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "7", "8.1", "8.2")
VAT_PURCHASE_BOXES = ("6.1", "6.3", "6.4", "6.6")


def money(value):
    return flt(value, 6)


def whole(value):
    """MRA-style whole-rupee presentation; preserve underlying decimals in details."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _vat_tax_rows(invoice):
    rows = []
    for tax in invoice.get("taxes") or []:
        # A withholding tax must NEVER be misclassified as input VAT.
        if "vat" not in (tax.get("account_head") or "").lower():
            continue
        if tax.get("add_deduct_tax") == "Deduct":
            continue
        rows.append(tax)
    return rows


def _item_vat(invoice):
    """Read ERPNext's actual item-wise VAT charges, including source rounding.

    Repeated item codes share a single item-wise tax amount pro rata on base value.
    Mixed invoices without an actual item-wise allocation are rejected.
    """
    grouped = defaultdict(list)
    for item in invoice.items:
        grouped[item.item_code].append(item)
    totals = defaultdict(float)
    tax_rows = _vat_tax_rows(invoice)
    for tax in tax_rows:
        details = tax.get("item_wise_tax_detail")
        try:
            details = frappe.parse_json(details) if details else {}
        except (ValueError, TypeError):
            frappe.throw(f"Invalid item-wise VAT details on {invoice.name}")
        if not details and abs(money(tax.base_tax_amount_after_discount_amount)) > 0.01:
            frappe.throw(f"Missing item-wise VAT allocation on {invoice.name}; review tax row {tax.idx}")
        for key, calculation in (details or {}).items():
            if not isinstance(calculation, (list, tuple)) or len(calculation) < 2:
                frappe.throw(f"Unexpected item-wise VAT allocation on {invoice.name}: {key}")
            if key not in grouped:
                matches = [item for item in invoice.items if item.name == key]
                if len(matches) != 1:
                    frappe.throw(f"Unmatched VAT item {key} in {invoice.name}")
                grouped[key] = matches
            pool = grouped[key]
            total = sum(abs(money(item.base_net_amount)) for item in pool)
            if not total and abs(money(calculation[1])) > 0.01:
                frappe.throw(f"Zero net value with VAT in {invoice.name}")
            # Item-wise tax detail is in transaction currency; convert to company currency.
            vat = money(calculation[1]) * flt(invoice.conversion_rate or 1)
            for item in pool:
                totals[item.name] += vat * (abs(money(item.base_net_amount)) / total if total else 0)
    expected = sum(money(tax.base_tax_amount_after_discount_amount) for tax in tax_rows)
    actual = sum(totals.values())
    if abs(expected - actual) > max(0.03, 0.01 * len(invoice.items)):
        frappe.throw(f"VAT tax detail does not reconcile for {invoice.name}: {actual} vs {expected}")
    return totals


def _invoice_names(parent, company, start, end, purchase=False):
    P = frappe.qb.DocType(parent)
    if not purchase:
        q = (frappe.qb.from_(P).select(P.name)
             .where(P.company == company).where(P.docstatus == 1)
             .where(P.posting_date.between(start, end)))
    else:
        I = frappe.qb.DocType("Purchase Invoice Item")
        from pypika.functions import Coalesce
        q = (frappe.qb.from_(P).join(I).on(I.parent == P.name)
             .select(P.name).distinct()
             .where(P.company == company).where(P.docstatus == 1)
             .where(P.posting_date <= end)
             .where(Coalesce(I.vat_claim_date, P.posting_date).between(start, end)))
    return [row.name for row in q.run(as_dict=True)]


def _source_rows(invoice, purchase, from_date, to_date, recovery):
    tax_by_item = _item_vat(invoice)
    result = []
    for item in invoice.items:
        claim = item.get("vat_claim_date") or invoice.posting_date
        if purchase and not (getdate(from_date) <= getdate(claim) <= getdate(to_date)):
            continue
        box = item.get("vat_return_type")
        permitted = PURCHASE_BOXES if purchase else SALES_BOXES
        if not box or box not in permitted:
            frappe.throw(f"Invalid or missing VAT Return Type for {invoice.name} item {item.idx}")
        value = money(item.base_net_amount)
        vat = money(tax_by_item.get(item.name, 0))
        if box not in ((*VAT_PURCHASE_BOXES, "7") if purchase else ("1.4",)) and abs(vat) > 0.03:
            frappe.throw(f"VAT on an incompatible category ({box}): {invoice.name} item {item.idx}")
        treatment = ((item.get("vat_recovery_treatment") or "Shared") if box in VAT_PURCHASE_BOXES else "None") if purchase else ""
        result.append({
            "source_doctype": invoice.doctype,
            "source_invoice": invoice.name,
            "source_item": item.name,
            "party": invoice.supplier if purchase else invoice.customer,
            "invoice_date": invoice.bill_date if purchase else invoice.posting_date,
            "posting_date": invoice.posting_date,
            "claim_date": claim if purchase else invoice.posting_date,
            "vat_return_type": box,
            "item_code": item.item_code,
            "taxable_value": value,
            "vat_amount": vat,
            "recovery_treatment": treatment,
            "recoverable_vat": (vat if treatment == "Full" else vat * recovery / 100 if treatment == "Shared" else 0) if purchase else 0,
            "notes": "Prior accounting period" if purchase and getdate(invoice.posting_date) < getdate(from_date) else "",
        })
    return result


def _check_duplicate_claim(item_ids, current_filing):
    if not item_ids:
        return
    duplicates = frappe.get_all(
        "VAT Return Purchase Detail",
        filters={"source_item": ["in", item_ids], "parent": ["!=", current_filing or ""]},
        fields=["source_item", "parent"],
        limit_page_length=0,
    )
    filed = [d for d in duplicates if frappe.db.get_value("VAT Return Filing", d.parent, "docstatus") == 1]
    if filed:
        frappe.throw(f"Purchase item already claimed in submitted filing {filed[0].parent} ({filed[0].source_item})")


def pull(doc):
    if doc.docstatus:
        frappe.throw("Only Draft VAT Return Filings can pull transactions.")
    if not doc.company or not doc.from_date or not doc.to_date:
        frappe.throw("Company and taxable dates are required")
    if getdate(doc.from_date) > getdate(doc.to_date):
        frappe.throw("From Date cannot exceed To Date")
    recovery = flt(doc.recovery_percentage)
    if not 0 <= recovery <= 100:
        frappe.throw("Recovery percentage must be between 0 and 100")
    sales, purchases = [], []
    for name in _invoice_names("Sales Invoice", doc.company, doc.from_date, doc.to_date):
        sales.extend(_source_rows(frappe.get_doc("Sales Invoice", name), False, doc.from_date, doc.to_date, recovery))
    for name in _invoice_names("Purchase Invoice", doc.company, doc.from_date, doc.to_date, purchase=True):
        purchases.extend(_source_rows(frappe.get_doc("Purchase Invoice", name), True, doc.from_date, doc.to_date, recovery))
    _check_duplicate_claim([row["source_item"] for row in purchases], doc.name)
    doc.set("sales_details", sorted(sales, key=lambda d: (d["source_invoice"], d["source_item"])))
    doc.set("purchase_details", sorted(purchases, key=lambda d: (d["source_invoice"], d["source_item"])))
    recalculate(doc)
    return {"sales_items": len(sales), "purchase_items": len(purchases)}


def recalculate(doc, validating_submission=False):
    if doc.docstatus and not validating_submission:
        frappe.throw("A submitted filing cannot be recalculated.")
    pct = flt(doc.recovery_percentage)
    if pct < 0 or pct > 100:
        frappe.throw("Recovery percentage must be between 0 and 100.")
    box = defaultdict(float)
    vat = defaultdict(float)
    for row in doc.get("sales_details") or []:
        if row.vat_return_type not in SALES_BOXES:
            frappe.throw(f"Invalid sales category {row.vat_return_type}")
        box[row.vat_return_type] += flt(row.taxable_value)
        vat[row.vat_return_type] += flt(row.vat_amount)
    for row in doc.get("purchase_details") or []:
        if row.vat_return_type not in PURCHASE_BOXES:
            frappe.throw(f"Invalid purchase category {row.vat_return_type}")
        box[row.vat_return_type] += flt(row.taxable_value)
        vat[row.vat_return_type] += flt(row.vat_amount)
        if row.vat_return_type in VAT_PURCHASE_BOXES:
            if row.recovery_treatment not in ("Full", "Shared", "None"):
                frappe.throw(f"Invalid recovery treatment on {row.source_invoice}")
            row.recoverable_vat = (
                flt(row.vat_amount)
                if row.recovery_treatment == "Full"
                else flt(row.vat_amount) * pct / 100
                if row.recovery_treatment == "Shared"
                else 0
            )
            vat["deductible"] += row.recoverable_vat
    adjustments = defaultdict(float)
    for row in doc.get("adjustments") or []:
        if not row.reference or not row.reason:
            frappe.throw("Adjustment requires a reference and reason")
        adjustments[row.mra_box] += flt(row.vat_amount)
    output = vat["1.4"] + adjustments["2"] + adjustments["4"]
    input_claim = vat["deductible"]
    previous = frappe.get_all("VAT Return Filing", filters={"company":doc.company,"docstatus":1,"to_date":["<",doc.from_date]},fields=["name","box_16_excess_carried_forward"],order_by="to_date desc",limit=1)
    opening = flt(doc.excess_brought_forward_manual) if doc.excess_brought_forward_manual else flt(previous[0].box_16_excess_carried_forward) if previous else 0
    if doc.excess_brought_forward_manual and not doc.opening_credit_reason:
        frappe.throw("Opening VAT credit override requires a supporting reference")
    net = output - input_claim - opening + adjustments["13"]
    doc.output_vat, doc.input_vat = output, input_claim
    doc.box_12_excess_brought_forward = opening
    doc.brought_forward_from = None if doc.excess_brought_forward_manual else previous[0].name if previous else None
    repayment = adjustments["15.1"] + adjustments["15.2"]
    if repayment < 0 or repayment > max(0, -net):
        frappe.throw("Repayment claim must not exceed available excess VAT")
    doc.box_16_excess_carried_forward = max(0, -net - repayment)
    doc.vat_payable = max(0, net) + adjustments["17"] + adjustments["18"]
    summaries = [
        ("1.1","Zero-rated supplies (Exports)",box["1.1"],0),
        ("1.2","Other zero-rated supplies",box["1.2"],0),
        ("1.3","Taxable supplies made to exempt bodies",box["1.3"],0),
        ("1.4","Other taxable supplies",box["1.4"],vat["1.4"]),
        ("2","Deferred import VAT",0,adjustments["2"]),
        ("3","Exempt supplies",box["3"],0),
        ("4","Penalty on excess overclaim",0,adjustments["4"]),
        ("5","Total output",sum(box[x] for x in SALES_BOXES),output),
        *[(x,"Input purchases "+x,box[x],vat[x] if x in VAT_PURCHASE_BOXES else 0) for x in PURCHASE_BOXES],
        ("9","Total input",sum(box[x] for x in PURCHASE_BOXES),sum(vat[x] for x in VAT_PURCHASE_BOXES)),
        ("10","Input VAT deductible",0,input_claim),
        ("11","VAT payable for period",0,output-input_claim),
        ("12","Excess VAT brought forward",0,-opening),
        ("13","VAT adjustment",0,adjustments["13"]),
        ("14","VAT due and payable",0,doc.vat_payable),
        ("15.1","Repayment on capital goods",0,adjustments["15.1"]),
        ("15.2","Repayment on other goods",0,adjustments["15.2"]),
        ("15.3","Total repayment claim",0,adjustments["15.1"]+adjustments["15.2"]),
        ("16","Excess VAT carried forward",0,doc.box_16_excess_carried_forward),
        ("17","Late submission penalty",0,adjustments["17"]),
        ("18","Other penalty",0,adjustments["18"]),
    ]
    doc.set("lines",[])
    for number,description,value,tax in summaries:
        doc.append("lines",{"box":number,"description":description,"value_amount":money(value),"vat_amount":money(tax),"currency":doc.currency})
    doc.return_data_json = frappe.as_json([{"box":b,"description":d,"value_amount":v,"vat_amount":t} for b,d,v,t in summaries])
    return {"output_vat":output,"input_vat":input_claim,"vat_payable":doc.vat_payable}
