"""Regression fixtures from BDCEL June-August 2026 accounting working papers.

The MRA filed whole-rupee returns and the source Excel have small differences.
Do not silently rewrite calculated source VAT to fit the submitted totals.
"""
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from csf_mu.csf_mu.utils import vat_filing_engine as engine


class TestVATReturnFiling(FrappeTestCase):
    def test_june_2026_reference_calculation(self):
        output = 1123478.70
        current_input = 308915.4665 * 0.71
        prior_adjustment = 66585.298 * 0.71
        calculated = output - current_input - prior_adjustment
        self.assertAlmostEqual(calculated, 856873.157, places=2)
        # The return filed for June was Rs 856,872 after MRA presentation.
        self.assertLessEqual(abs(calculated - 856872), 2)

    def test_july_2026_reference_calculation(self):
        output = 1248939.61
        current_input = 291030.588 * 0.71
        previous_input = 29565.429 * 0.71
        calculated = output - current_input - previous_input
        self.assertAlmostEqual(calculated, 1021316.43793, places=2)
        self.assertAlmostEqual(calculated, 1021316, delta=1)

    def test_august_2026_sales_working(self):
        standard = 7316894.34
        zero = 788995.50
        exempt = 811418.80
        output = 1097534.08
        self.assertAlmostEqual(standard + zero + exempt, 8917308.64, places=2)
        self.assertAlmostEqual(standard + zero + exempt + output, 10014842.72, places=2)

    def test_prior_posting_claimed_in_future_month(self):
        invoice = SimpleNamespace(**{
            "doctype": "Purchase Invoice",
            "name": "TEST-LATE",
            "supplier": "Test Supplier",
            "posting_date": "2026-07-10",
            "bill_date": "2026-06-20",
            "items": [
                frappe._dict({
                    "name": "late-item-1",
                    "idx": 1,
                    "item_code": "ITEM-1",
                    "base_net_amount": 100000,
                    "vat_claim_date": "2026-08-01",
                    "vat_return_type": "6.6",
                    "vat_recovery_treatment": "Shared",
                }),
            ],
        })
        with patch.object(engine, "_item_vat", return_value={"late-item-1": 15000}):
            july = engine._source_rows(invoice, True, "2026-07-01", "2026-07-31", 71)
            august = engine._source_rows(invoice, True, "2026-08-01", "2026-08-31", 71)
        self.assertEqual(july, [])
        self.assertEqual(len(august), 1)
        self.assertEqual(august[0]["recoverable_vat"], 10650)
        self.assertEqual(august[0]["posting_date"], "2026-07-10")

    def test_recovery_treatments(self):
        self.assertEqual(15000 * 0.71, 10650)
        self.assertEqual(15000 * 1, 15000)
        self.assertEqual(15000 * 0, 0)
