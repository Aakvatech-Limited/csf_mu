"""Read v16 row-linked VAT allocations without changing posted amounts."""

from unittest import TestCase

import frappe

from csf_mu.csf_mu.utils import vat_filing_engine as engine


def make_invoice(doctype="Purchase Invoice", conversion_rate=1):
	return frappe._dict(
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
