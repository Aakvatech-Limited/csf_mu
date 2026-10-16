import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from csf_mu.csf_mu.utils import vat_filing_engine as engine


class VATReturnFiling(Document):
    def before_insert(self):
        self._apply_company_defaults()

    def _apply_company_defaults(self):
        if not self.company:
            return
        settings = frappe.db.get_value(
            "CSF MU Company Settings",
            self.company,
            [
                "default_recovery_percentage",
                "vat_reconciliation_tolerance",
                "auto_allocate_rounding_difference",
                "block_unexplained_vat_differences",
            ],
            as_dict=True,
        )
        if not settings:
            frappe.throw(
                f"Create CSF MU Company Settings for {self.company} before VAT filing."
            )
        self.configured_recovery_percentage = settings.default_recovery_percentage
        if self.recovery_percentage is None:
            self.recovery_percentage = settings.default_recovery_percentage
        self.vat_reconciliation_tolerance = settings.vat_reconciliation_tolerance
        self.auto_allocate_rounding_difference = settings.auto_allocate_rounding_difference
        self.block_unexplained_vat_differences = settings.block_unexplained_vat_differences

    def validate(self):
        if self.company:
            engine._set_filing_currency(self)
        if self.from_date:
            self.filing_month = getdate(self.from_date).strftime("%Y-%m")
        if getdate(self.from_date) > getdate(self.to_date):
            frappe.throw("From Date cannot be after To Date.")
        if self.recovery_percentage is not None and self.configured_recovery_percentage is not None:
            if abs(float(self.recovery_percentage) - float(self.configured_recovery_percentage)) > 0.000001:
                if not self.recovery_override_reason:
                    frappe.throw("Reason is required when overriding the company VAT recovery percentage.")
        if not 0 <= float(self.recovery_percentage or 0) <= 100:
            frappe.throw("Input VAT recovery percentage must be between 0 and 100")
        if self.docstatus == 0 and self.company and self.from_date:
            opening_changed = self.is_new() or self.has_value_changed(
                "excess_brought_forward_manual"
            )
            if opening_changed and self.get("lines"):
                # Recalculate Box 12, Box 16, payable and snapshot lines together.
                engine.recalculate(self)
            else:
                # Also populate Box 12 before the first successful transaction pull.
                engine.sync_opening_credit(self)

    def before_submit(self):
        overlap = frappe.get_all(
            "VAT Return Filing",
            filters={
                "company": self.company,
                "docstatus": 1,
                "from_date": ["<=", self.to_date],
                "to_date": [">=", self.from_date],
                "name": ["!=", self.name],
            },
            pluck="name",
            limit=1,
        )
        if overlap:
            frappe.throw(f"Submitted VAT Return Filing {overlap[0]} overlaps this taxable period.")
        if not self.lines:
            frappe.throw("Pull Transactions before submitting a VAT return")
        engine._check_duplicate_claim([r.source_item for r in self.purchase_details], self.name)
        self._validate_completeness()
        self._validate_sources()
        self._validate_balances()

    def _validate_completeness(self):
        expected_sales = set()
        expected_purchases = set()
        for name in engine._invoice_names("Sales Invoice", self.company, self.from_date, self.to_date):
            source = frappe.get_doc("Sales Invoice", name)
            expected_sales.update(row.name for row in source.items)
        for name in engine._invoice_names(
            "Purchase Invoice", self.company, self.from_date, self.to_date, purchase=True
        ):
            source = frappe.get_doc("Purchase Invoice", name)
            expected_purchases.update(
                row.name for row in source.items
                if getdate(self.from_date)
                <= getdate(row.get("vat_claim_date") or source.posting_date)
                <= getdate(self.to_date)
            )
        saved_sales = {row.source_item for row in self.sales_details}
        saved_purchases = {row.source_item for row in self.purchase_details}
        if expected_sales != saved_sales or expected_purchases != saved_purchases:
            frappe.throw("The filing details do not match eligible source transactions. Pull Transactions again.")

    def _validate_sources(self):
        for fieldname, doctype in (
            ("sales_details", "Sales Invoice Item"),
            ("purchase_details", "Purchase Invoice Item"),
        ):
            seen = set()
            for row in self.get(fieldname):
                if row.source_item in seen:
                    frappe.throw(f"Duplicate invoice item in {fieldname}: {row.source_item}")
                seen.add(row.source_item)
                source = frappe.db.get_value(doctype, row.source_item, ["parent", "vat_return_type"], as_dict=True)
                if not source or source.parent != row.source_invoice:
                    frappe.throw(f"Source invoice item no longer exists: {row.source_item}")
                parent = frappe.db.get_value(row.source_doctype, row.source_invoice, ["company", "docstatus"], as_dict=True)
                if not parent or parent.docstatus != 1 or parent.company != self.company:
                    frappe.throw(f"Invalid source invoice: {row.source_invoice}")
                if source.vat_return_type != row.vat_return_type:
                    frappe.throw(f"Source classification changed: {row.source_invoice}; pull again")
                if fieldname == "purchase_details":
                    claim_date = frappe.db.get_value(doctype, row.source_item, "vat_claim_date")
                    if getdate(claim_date or row.posting_date) != getdate(row.claim_date):
                        frappe.throw(f"Claim date changed on {row.source_invoice}; pull again")
                    if not (getdate(self.from_date) <= getdate(row.claim_date) <= getdate(self.to_date)):
                        frappe.throw(f"Purchase claim is outside this filing: {row.source_invoice}")

    def _validate_balances(self):
        original = {
            "output_vat": self.output_vat,
            "input_vat": self.input_vat,
            "vat_payable": self.vat_payable,
        }
        engine.recalculate(self, validating_submission=True)
        for key, old in original.items():
            if abs(float(old or 0) - float(self.get(key) or 0)) > 0.01:
                frappe.throw(f"{key} has changed: recalculate and save before submitting")

    @frappe.whitelist()
    def pull_transactions(self):
        self.check_permission("write")
        result = engine.pull(self)
        self.save()
        return result

    @frappe.whitelist()
    def recalculate(self):
        self.check_permission("write")
        result = engine.recalculate(self)
        self.save()
        return result

    @frappe.whitelist()
    def get_breakdown(self, box: str):
        self.check_permission("read")
        return [
            row.as_dict()
            for row in list(self.sales_details) + list(self.purchase_details)
            if row.vat_return_type == box
        ]

    def on_update_after_submit(self):
        # Frappe enforces allow_on_submit on acknowledgement/status fields.
        if self.filing_status in ("Filed", "Acknowledged") and not self.filing_date:
            frappe.throw("Filing date is required when marking a return filed")
