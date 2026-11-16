"""Regression coverage for purchase VAT classified to MRA Box 13."""
from unittest import TestCase
from unittest.mock import patch

from frappe import _dict

from csf_mu.csf_mu.utils import vat_filing_engine as engine


class TestPurchaseBox13(TestCase):
    def test_purchase_line_13_is_accepted_and_keeps_expense_value(self):
        invoice = _dict(
            doctype="Purchase Invoice", name="PINV-LATE", supplier="Supplier",
            posting_date="2026-11-10", bill_date="2026-08-20",
            items=[_dict(
                name="PINV-LINE", idx=1, item_code="ITEM", item_name="Service",
                base_net_amount=100000, vat_return_type="13", vat_claim_date="2026-11-10",
                vat_recovery_treatment="Full",
            )],
        )
        with patch.object(engine, "_item_vat", return_value={"PINV-LINE": 15000}):
            rows = engine._source_rows(invoice, True, "2026-11-01", "2026-11-30", 71)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vat_return_type"], "13")
        self.assertEqual(rows[0]["taxable_value"], 100000)
        self.assertEqual(rows[0]["recoverable_vat"], 15000)

    def test_box13_recovery_and_no_double_count(self):
        doc = _dict(
            docstatus=0, company="Test Company", currency=None,
            recovery_percentage=71, excess_brought_forward_manual=0,
            sales_details=[], adjustments=[],
            purchase_details=[
                _dict(source_invoice="PINV-A", vat_return_type="6.6", taxable_value=200,
                      vat_amount=30, recovery_treatment="Full"),
                _dict(source_invoice="PINV-LATE", vat_return_type="13", taxable_value=1000,
                      vat_amount=150, recovery_treatment="Shared"),
            ],
        )
        doc.set = lambda key, value: doc.update({key: value})
        with (
            patch.object(engine, "_set_filing_currency", side_effect=lambda d: d.update(currency="MUR")),
            patch.object(engine.frappe, "get_all", return_value=[]),
        ):
            engine.recalculate(doc)
        lines = {row["box"]: row for row in doc.lines}
        self.assertEqual(lines["6.6"]["value_amount"], 200)
        self.assertEqual(lines["9"]["value_amount"], 200)
        self.assertEqual(lines["10"]["vat_amount"], 30)
        self.assertAlmostEqual(lines["13"]["vat_amount"], -106.5)
        self.assertAlmostEqual(doc.box_16_excess_carried_forward, 136.5)
