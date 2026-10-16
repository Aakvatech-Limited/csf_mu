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

    def test_name_only_sales_item_uses_its_vat_return_type(self):
        item = frappe._dict({
            "name": "sales-row-1", "idx": 1, "item_code": None,
            "item_name": "POLOSHIRT BEIGE", "base_net_amount": 1000,
            "vat_return_type": "1.4",
        })
        invoice = frappe._dict({
            "doctype": "Sales Invoice", "name": "SINV-BDCEL-2026-00090",
            "customer": "Test Customer", "posting_date": "2026-06-15",
            "conversion_rate": 1, "items": [item],
            "taxes": [frappe._dict({
                "account_head": "Output VAT 15%", "add_deduct_tax": "Add",
                "base_tax_amount_after_discount_amount": 150, "idx": 1,
                "item_wise_tax_detail": '{"POLOSHIRT BEIGE": [15, 150]}',
            })],
        })
        rows = engine._source_rows(invoice, False, "2026-06-01", "2026-06-30", 71)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vat_return_type"], "1.4")
        self.assertEqual(rows[0]["vat_amount"], 150)
        self.assertIsNone(rows[0]["item_code"])

    def test_name_only_sales_without_valid_type_raises(self):
        for category in (None, "6.6", "99"):
            with self.subTest(category=category):
                invoice = frappe._dict({
                    "name": "SINV-TEST", "items": [frappe._dict({
                        "name": "row-1", "idx": 1, "item_code": None,
                        "item_name": "POLOSHIRT BEIGE", "vat_return_type": category,
                    })],
                })
                with self.assertRaises(frappe.ValidationError):
                    engine._validate_sales_return_types(invoice)

    def test_repeated_item_names_are_apportioned_by_value(self):
        invoice = frappe._dict({
            "name": "SINV-REPEATED", "conversion_rate": 1,
            "items": [
                frappe._dict({"name": "row-1", "item_code": None, "item_name": "POLOSHIRT BEIGE", "base_net_amount": 100}),
                frappe._dict({"name": "row-2", "item_code": None, "item_name": "POLOSHIRT BEIGE", "base_net_amount": 300}),
            ],
            "taxes": [frappe._dict({
                "account_head": "Output VAT 15%", "add_deduct_tax": "Add",
                "base_tax_amount_after_discount_amount": 60, "idx": 1,
                "item_wise_tax_detail": '{"POLOSHIRT BEIGE": [15, 60]}',
            })],
        })
        totals = engine._item_vat(invoice)
        self.assertAlmostEqual(totals["row-1"], 15)
        self.assertAlmostEqual(totals["row-2"], 45)

    def test_conflicting_code_and_name_matches_raise(self):
        invoice = frappe._dict({
            "name": "SINV-AMBIGUOUS", "conversion_rate": 1,
            "items": [
                frappe._dict({"name": "row-1", "item_code": "ABC", "item_name": "Named ABC", "base_net_amount": 100}),
                frappe._dict({"name": "row-2", "item_code": None, "item_name": "ABC", "base_net_amount": 100}),
            ],
            "taxes": [frappe._dict({
                "account_head": "Output VAT 15%", "add_deduct_tax": "Add",
                "base_tax_amount_after_discount_amount": 15, "idx": 1,
                "item_wise_tax_detail": '{"ABC": [15, 15]}',
            })],
        })
        with self.assertRaises(frappe.ValidationError):
            engine._item_vat(invoice)

    def test_foreign_currency_vat_uses_posted_invoice_conversion_rate(self):
        for currency, rate in (("MUR", 1), ("USD", 46), ("EUR", 50)):
            with self.subTest(currency=currency):
                invoice = frappe._dict({
                    "name": f"SINV-{currency}",
                    "doctype": "Sales Invoice",
                    "customer": "Test Customer",
                    "posting_date": "2026-10-01",
                    "currency": currency,
                    "conversion_rate": rate,
                    "items": [frappe._dict({
                        "name": "line-1", "idx": 1, "item_code": "TEST",
                        "item_name": "Test Item", "vat_return_type": "1.4",
                        "net_amount": 1000, "base_net_amount": 1000 * rate,
                    })],
                    "taxes": [frappe._dict({
                        "idx": 1, "account_head": "Output VAT",
                        "add_deduct_tax": "Add",
                        "item_wise_tax_detail": frappe.as_json({"TEST": [15, 150 * rate]}),
                        "base_tax_amount_after_discount_amount": 150 * rate,
                    })],
                })
                rows = engine._source_rows(
                    invoice, False, "2026-10-01", "2026-10-31", 100
                )
                self.assertEqual(len(rows), 1)
                self.assertAlmostEqual(rows[0]["taxable_value"], 1000 * rate)
                self.assertAlmostEqual(rows[0]["vat_amount"], 150 * rate)

    def test_purchase_vat_stays_at_original_exchange_rate_when_claimed_later(self):
        invoice = frappe._dict({
            "name": "PINV-USD-DEFERRED",
            "doctype": "Purchase Invoice",
            "supplier": "Test Supplier",
            "posting_date": "2026-07-01",
            "bill_date": "2026-07-01",
            "conversion_rate": 46,
            "items": [frappe._dict({
                "name": "purchase-line-1", "idx": 1,
                "item_code": "TEST", "item_name": "Test Item",
                "vat_return_type": "6.6", "vat_claim_date": "2026-10-01",
                "vat_recovery_treatment": "Full",
                "base_net_amount": 46000,
            })],
            "taxes": [frappe._dict({
                "idx": 1, "account_head": "Input VAT",
                "add_deduct_tax": "Add",
                "item_wise_tax_detail": '{"TEST": [15, 6900]}',
                "base_tax_amount_after_discount_amount": 6900,
            })],
        })
        rows = engine._source_rows(
            invoice, True, "2026-10-01", "2026-10-31", 100
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["taxable_value"], 46000)
        self.assertEqual(rows[0]["vat_amount"], 6900)
        self.assertEqual(rows[0]["recoverable_vat"], 6900)

    def test_filing_rejects_currency_other_than_company_base(self):
        doc = frappe._dict({"company": "Test Company", "currency": "USD"})
        with patch.object(frappe.db, "get_value", return_value="MUR"):
            with self.assertRaises(frappe.ValidationError):
                engine._set_filing_currency(doc)

    def test_filing_currency_is_populated_from_company(self):
        doc = frappe._dict({"company": "Test Company", "currency": None})
        with patch.object(frappe.db, "get_value", return_value="MUR"):
            engine._set_filing_currency(doc)
        self.assertEqual(doc.currency, "MUR")

    def test_actual_eur_invoice_item_detail_is_already_in_mur(self):
        """BDCEL SINV-BDCEL-2026-00128: item detail is base MUR, not EUR."""
        invoice = frappe._dict({
            "doctype": "Sales Invoice",
            "name": "SINV-BDCEL-2026-00128",
            "customer": "CUST-06380",
            "posting_date": "2026-07-13",
            "currency": "EUR",
            "conversion_rate": 54,
            "items": [
                frappe._dict({
                    "name": "dkl2g3e640", "idx": 1, "item_code": "STST10001",
                    "item_name": "Daily Rate", "vat_return_type": "1.4",
                    "base_net_amount": 8217.18,
                }),
                frappe._dict({
                    "name": "dkl28avtj2", "idx": 2, "item_code": "STST10013",
                    "item_name": "Gold Medal Trophy", "vat_return_type": "1.4",
                    "base_net_amount": 75130.20,
                }),
            ],
            "taxes": [frappe._dict({
                "idx": 1, "account_head": "501150 - Vat Output - BDCEL",
                "add_deduct_tax": "Add",
                "tax_amount_after_discount_amount": 231.52,
                "base_tax_amount_after_discount_amount": 12502.08,
                "item_wise_tax_detail":
                    '{"STST10001":[15.0,1232.577],"STST10013":[15.0,11269.529999999999]}',
            })],
        })
        rows = engine._source_rows(
            invoice, False, "2026-07-01", "2026-07-31", 100
        )
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(sum(r["taxable_value"] for r in rows), 83347.38)
        self.assertAlmostEqual(sum(r["vat_amount"] for r in rows), 12502.107)
        self.assertAlmostEqual(rows[0]["vat_amount"], 1232.577)

    def test_exempt_purchase_with_vat_is_not_silently_claimed(self):
        invoice = frappe._dict({
            "doctype": "Purchase Invoice", "name": "PINV-EXEMPT",
            "supplier": "Test Supplier", "posting_date": "2026-07-13",
            "bill_date": "2026-07-13", "conversion_rate": 1,
            "items": [frappe._dict({
                "name": "purchase-1", "idx": 2, "item_code": "TEST",
                "item_name": "Test Item", "vat_return_type": "8.2",
                "base_net_amount": 1000,
            })],
            "taxes": [frappe._dict({
                "idx": 1, "account_head": "Input VAT",
                "add_deduct_tax": "Add",
                "base_tax_amount_after_discount_amount": 150,
                "item_wise_tax_detail": '{"TEST":[15,150]}',
            })],
        })
        with self.assertRaisesRegex(frappe.ValidationError, "does not permit VAT recovery"):
            engine._source_rows(invoice, True, "2026-07-01", "2026-07-31", 100)
