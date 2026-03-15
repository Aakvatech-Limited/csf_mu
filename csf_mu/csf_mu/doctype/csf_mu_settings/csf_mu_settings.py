import frappe
from frappe.model.document import Document


class CSFMUSettings(Document):
	def validate(self):
		companies = set()
		for row in self.get("settings_details", []):
			if not row.company:
				continue
			if row.company in companies:
				frappe.throw(f"Duplicate company in Settings Details: {row.company}")
			companies.add(row.company)
