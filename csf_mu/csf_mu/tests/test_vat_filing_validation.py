"""Regression tests for aggregate VAT transaction validation."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from frappe import _dict

from csf_mu.csf_mu.utils import vat_filing_engine as engine


def invoice_item(name, idx, vat_return_type, item_name=None):
	return _dict(
		name=name,
		idx=idx,
		item_name=item_name or name,
		item_code=None,
		vat_return_type=vat_return_type,
		base_net_amount=100,
		vat_claim_date=None,
		vat_recovery_treatment=None,
	)


class TestVatFilingValidation(TestCase):
	def test_collects_all_invalid_sales_classifications(self):
		invoice = SimpleNamespace(
			name="SINV-TEST-1",
			items=[
				invoice_item("ITEM-1", 1, None),
				invoice_item("ITEM-2", 2, "6.6"),
				invoice_item("ITEM-3", 3, "1.4"),
			],
		)
		errors = []
		engine._validate_sales_return_types(invoice, errors)
		self.assertEqual(len(errors), 2)
		self.assertIn("Row 1", errors[0])
		self.assertIn("Row 2", errors[1])

	def test_collects_multiple_unmatched_tax_keys(self):
		invoice = _dict(
			name="SINV-TEST-2",
			items=[invoice_item("ITEM-1", 1, "1.4", "Existing Item")],
			taxes=[
				_dict(
					idx=1,
					account_head="Output VAT",
					add_deduct_tax="Add",
					item_wise_tax_detail='{"Missing A": [15, 15], "Missing B": [15, 15]}',
					base_tax_amount_after_discount_amount=30,
				)
			],
			conversion_rate=1,
		)
		errors = []
		engine._item_vat(invoice, errors)
		self.assertEqual(len(errors), 2)
		self.assertIn("Missing A", errors[0])
		self.assertIn("Missing B", errors[1])

	def test_failed_pull_preserves_existing_snapshot(self):
		doc = _dict(
			docstatus=0,
			name="VAT-TEST",
			company="Test Company",
			from_date="2026-09-01",
			to_date="2026-09-30",
			recovery_percentage=100,
			sales_details=[{"source_item": "EXISTING"}],
			purchase_details=[],
		)
		doc.set = lambda field, value: doc.update({field: value})
		with (
			patch.object(engine, "_invoice_names", side_effect=[["SINV-1", "SINV-2"], []]),
			patch.object(
				engine.frappe,
				"get_doc",
				side_effect=[
					_dict(name="SINV-1"),
					_dict(name="SINV-2"),
				],
			),
			patch.object(
				engine,
				"_source_rows",
				side_effect=lambda inv, *args: (
					args[-1].append(f"Sales Invoice {inv.name}: invalid type") or []
				),
			),
			patch.object(engine.frappe, "throw", side_effect=ValueError) as throw,
		):
			with self.assertRaises(ValueError):
				engine.pull(doc)
		self.assertEqual(doc.sales_details, [{"source_item": "EXISTING"}])
		self.assertEqual(doc.purchase_details, [])
		self.assertIn("2 VAT validation error(s)", throw.call_args.args[0])
