import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class VATReturnFiling(Document):
	def validate(self):
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw("From Date cannot be after To Date.")

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
			frappe.throw(
				f"Submitted VAT Return Filing {overlap[0]} overlaps this taxable period."
			)
		if not self.filing_date:
			self.filing_date = today()
