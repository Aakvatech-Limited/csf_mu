"""Read v16 row-linked VAT allocations without changing posted amounts."""

import json
from unittest import TestCase

import frappe

from csf_mu.csf_mu.utils import vat_filing_engine as engine


class InvoiceFixture(frappe._dict):
	"""Expose the child table as a Document does, rather than dict.items()."""

	@property
	def items(self):
		return self["items"]


def make_invoice(doctype="Purchase Invoice", conversion_rate=1):
	return InvoiceFixture(
		doctype=doctype,
		name="TEST-V16-VAT",
		supplier="Test Supplier",
		customer="Test Customer",
		posting_date="2026-07-28",
		bill_date="2026-07-28",
		conversion_rate=conversion_rate,
		items=[
			frappe._dict(
				name="taxable",
				idx=1,
				item_code="SAME-CODE",
				base_net_amount=100,
				vat_return_type="6.6" if doctype == "Purchase Invoice" else "1.4",
				vat_recovery_treatment="Shared",
			),
			frappe._dict(
				name="zero",
				idx=2,
				item_code="SAME-CODE",
				base_net_amount=50,
				vat_return_type="7" if doctype == "Purchase Invoice" else "1.2",
			),
		],
		taxes=[
			frappe._dict(
				name="vat-tax",
				idx=1,
				account_head="VAT Input",
				rate=15,
				base_tax_amount_after_discount_amount=15,
			)
		],
		item_wise_tax_details=[
			frappe._dict(idx=1, item_row="taxable", tax_row="vat-tax", rate=15, amount=15),
			frappe._dict(idx=2, item_row="zero", tax_row="vat-tax", rate=0, amount=0),
		],
	)


class TestVATItemWiseDetails(TestCase):
	def migration_invoice(self, case="exempt"):
		# Synthetic values only; no client invoice data belongs in repository fixtures.
		invoice = make_invoice()
		invoice.taxes[0].charge_type = "On Net Total"
		if case == "signed":
			bases = [2000, -1000, -40, 40]
			rates = [15, 0, 15, 0]
			stored = [300, -294, -6, 12]
			posted = 294
		elif case == "balanced":
			bases, rates, stored, posted = [100, 50], [15, 0], [14.8, 0.2], 15
		elif case == "control":
			bases, rates, stored, posted = [100, 50], [15, 0], [15, 0], 15
		else:
			bases, rates, stored, posted = [1000, 200], [15, 0], [150, 25], 150
		invoice["items"] = []
		invoice.item_wise_tax_details = []
		invoice.taxes[0].base_tax_amount_after_discount_amount = posted
		for idx, base in enumerate(bases):
			name = "row-" + str(idx + 1)
			invoice["items"].append(
				frappe._dict(
					name=name,
					idx=idx + 1,
					item_code="SHARED-CODE",
					base_net_amount=base,
					vat_return_type="6.6" if rates[idx] else "8.2",
					item_tax_rate=json.dumps({"VAT Input": rates[idx]}),
					vat_recovery_treatment="Shared",
				)
			)
			invoice.item_wise_tax_details.append(
				frappe._dict(
					idx=idx + 1,
					item_row=name,
					tax_row="vat-tax",
					rate=rates[idx],
					amount=stored[idx],
				)
			)
		return invoice

	def test_migrated_samples_reconcile_without_mutating_invoice(self):
		for case in ("exempt", "signed", "balanced", "control"):
			with self.subTest(case=case):
				invoice = self.migration_invoice(case)
				before = json.dumps(dict(invoice), sort_keys=True)
				rows = engine._source_rows(invoice, True, "2026-07-01", "2026-07-31", 71, tolerance=0.5)
				self.assertAlmostEqual(
					sum(row["vat_amount"] for row in rows),
					invoice.taxes[0].base_tax_amount_after_discount_amount,
					places=6,
				)
				for row in rows:
					if row["vat_return_type"] in ("7", "8.2"):
						self.assertEqual(row["vat_amount"], 0)
				self.assertEqual(json.dumps(dict(invoice), sort_keys=True), before)

	def test_reconstruction_preserves_negative_taxable_adjustment(self):
		invoice = self.migration_invoice("signed")
		amounts = engine._item_vat(invoice, tolerance=0.5)
		self.assertEqual([amounts[item.name] for item in invoice.items], [300, 0, -6, 0])

	def test_valid_control_preserves_posted_row_rounding(self):
		invoice = self.migration_invoice("control")
		amounts = engine._item_vat(invoice, tolerance=0.5)
		for detail in invoice.item_wise_tax_details:
			self.assertEqual(amounts[detail.item_row], detail.amount)

	def test_missing_saved_rate_does_not_reconstruct(self):
		invoice = self.migration_invoice()
		invoice.items[1].item_tax_rate = "{}"
		with self.assertRaisesRegex(frappe.ValidationError, "does not reconcile"):
			engine._item_vat(invoice, tolerance=0.5)

	def test_unsupported_charge_or_discount_does_not_reconstruct(self):
		for charge_type, discount in (("Actual", 0), ("On Net Total", 10)):
			with self.subTest(charge_type=charge_type, discount=discount):
				invoice = self.migration_invoice()
				invoice.taxes[0].charge_type = charge_type
				invoice.base_discount_amount = discount
				with self.assertRaisesRegex(frappe.ValidationError, "does not reconcile"):
					engine._item_vat(invoice, tolerance=0.5)

	def test_unexplained_posted_vat_is_not_scaled_to_fit(self):
		invoice = self.migration_invoice()
		invoice.taxes[0].base_tax_amount_after_discount_amount = 200
		with self.assertRaisesRegex(frappe.ValidationError, "does not reconcile"):
			engine._item_vat(invoice, tolerance=0.5)

	def test_reconstruction_respects_rounding_switch_and_tolerance(self):
		invoice = self.migration_invoice()
		invoice.taxes[0].base_tax_amount_after_discount_amount = 150.0005
		with self.assertRaisesRegex(frappe.ValidationError, "Auto-Allocate"):
			engine._item_vat(invoice, tolerance=0.5, auto_allocate=False)
		with self.assertRaisesRegex(frappe.ValidationError, "does not reconcile"):
			engine._item_vat(invoice, tolerance=0)

	def test_invalid_saved_rate_does_not_reconstruct(self):
		invoice = self.migration_invoice()
		invoice.items[1].item_tax_rate = '{"VAT Input": "NaN"}'
		with self.assertRaisesRegex(frappe.ValidationError, "does not reconcile"):
			engine._item_vat(invoice, tolerance=0.5)

	def test_purchase_mixed_rates_with_duplicate_codes(self):
		rows = engine._source_rows(make_invoice(), True, "2026-07-01", "2026-07-31", 71)
		self.assertEqual([row["vat_amount"] for row in rows], [15, 0])
		self.assertAlmostEqual(rows[0]["recoverable_vat"], 10.65)
		self.assertEqual(rows[1]["recoverable_vat"], 0)

	def test_sales_base_currency_is_not_converted_again(self):
		invoice = make_invoice("Sales Invoice", conversion_rate=54)
		rows = engine._source_rows(invoice, False, "2026-07-01", "2026-07-31", 100)
		self.assertEqual([row["vat_amount"] for row in rows], [15, 0])

	def test_legacy_json_fallback(self):
		invoice = make_invoice()
		invoice.item_wise_tax_details = []
		invoice.taxes[0].item_wise_tax_detail = '{"taxable":[15,15],"zero":[0,0]}'
		self.assertEqual(dict(engine._item_vat(invoice)), {"taxable": 15, "zero": 0})

	def test_child_details_take_precedence_over_legacy_json(self):
		invoice = make_invoice()
		invoice.taxes[0].item_wise_tax_detail = "invalid stale JSON"
		self.assertEqual(dict(engine._item_vat(invoice)), {"taxable": 15, "zero": 0})

	def test_missing_details_still_fail(self):
		invoice = make_invoice()
		invoice.item_wise_tax_details = []
		with self.assertRaisesRegex(frappe.ValidationError, "missing item-wise VAT allocation"):
			engine._item_vat(invoice)

	def test_invalid_item_link_fails(self):
		invoice = make_invoice()
		invoice.item_wise_tax_details[0].item_row = "missing"
		with self.assertRaisesRegex(frappe.ValidationError, "unmatched VAT item row"):
			engine._item_vat(invoice)

	def test_invalid_tax_link_fails(self):
		invoice = make_invoice()
		invoice.item_wise_tax_details[0].tax_row = "missing"
		with self.assertRaisesRegex(frappe.ValidationError, "unmatched tax row"):
			engine._item_vat(invoice)

	def test_duplicate_allocation_fails(self):
		invoice = make_invoice()
		invoice.item_wise_tax_details.append(frappe._dict(invoice.item_wise_tax_details[0]))
		with self.assertRaisesRegex(frappe.ValidationError, "duplicate VAT allocation"):
			engine._item_vat(invoice)

	def test_invalid_amount_fails(self):
		for amount in (None, "invalid", "NaN", "Infinity"):
			with self.subTest(amount=amount):
				invoice = make_invoice()
				invoice.item_wise_tax_details[0].amount = amount
				with self.assertRaisesRegex(frappe.ValidationError, "invalid VAT amount"):
					engine._item_vat(invoice)

	def test_tax_rows_must_reconcile_independently(self):
		invoice = make_invoice()
		invoice.taxes.append(
			frappe._dict(
				name="vat-tax-2",
				idx=2,
				account_head="VAT Other",
				base_tax_amount_after_discount_amount=10,
			)
		)
		invoice.item_wise_tax_details[0].amount = 10
		invoice.item_wise_tax_details.append(
			frappe._dict(
				idx=3,
				item_row="taxable",
				tax_row="vat-tax-2",
				rate=15,
				amount=15,
			)
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Tax row 1: VAT tax detail does not reconcile"):
			engine._item_vat(invoice)

	def test_return_preserves_negative_vat(self):
		invoice = make_invoice()
		invoice.taxes[0].base_tax_amount_after_discount_amount = -15
		invoice.item_wise_tax_details[0].amount = -15
		self.assertEqual(engine._item_vat(invoice)["taxable"], -15)

	def test_child_details_respect_rounding_controls(self):
		invoice = make_invoice()
		invoice.taxes[0].base_tax_amount_after_discount_amount = 15.20
		self.assertAlmostEqual(engine._item_vat(invoice, tolerance=0.5)["taxable"], 15.20)
		with self.assertRaisesRegex(frappe.ValidationError, "exceeds base-currency tolerance"):
			engine._item_vat(invoice, tolerance=0.1)
		with self.assertRaisesRegex(frappe.ValidationError, "Auto-Allocate"):
			engine._item_vat(invoice, tolerance=0.5, auto_allocate=False)
