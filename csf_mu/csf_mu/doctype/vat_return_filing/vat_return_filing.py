import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class VATReturnFiling(Document):
	def validate(self):
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw("From Date cannot be after To Date.")

	def before_submit(self):
		duplicate = frappe.db.exists(
			"VAT Return Filing",
			{
				"company": self.company,
				"from_date": self.from_date,
				"to_date": self.to_date,
				"docstatus": 1,
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(
				"VAT Return Filing {0} is already submitted for this company and period.".format(
					duplicate
				)
			)
		if not self.filing_date:
			self.filing_date = today()
