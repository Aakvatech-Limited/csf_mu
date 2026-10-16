import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CSFMUCompanySettings(Document):
    def validate(self):
        if not self.company:
            frappe.throw("Company is required")
        self.currency = frappe.db.get_value("Company", self.company, "default_currency")
        if not self.currency:
            frappe.throw("The company must have a default currency")
        if not 0 <= flt(self.default_recovery_percentage) <= 100:
            frappe.throw("Default recovery percentage must be between 0 and 100")
        if flt(self.vat_reconciliation_tolerance) < 0:
            frappe.throw("VAT reconciliation tolerance cannot be negative")
