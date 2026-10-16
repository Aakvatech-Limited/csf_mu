---
title: VAT Return Filing - Finance User Guide
---

# VAT Return Filing - Finance User Guide

**Application:** CSF MU · **Module:** MRA Integration · **Audience:** Finance and Accounts

This guide describes the VAT Return Filing workflow in ERPNext. It does **not** submit anything to MRA automatically. The MRA integration features for a future portal version are outside this filing workflow until separately released.

## 1. How VAT classification works

Each **Item Tax Template** can have a **VAT Return Type**, representing an MRA VAT return box (for example, **1.4** for standard-rated sales, **6.6** for local purchases with allowable input VAT, **7** for taxable purchases without input VAT credit, and **8.2** for exempt local purchases).

On a new **Sales Invoice Item** or **Purchase Invoice Item**, ERPNext fetches the template's `vat_return_type` into the line when that field is empty. The value **on the invoice item**, not the template's current value, controls the filing. This preserves any reviewed invoice-specific categorization when tax templates are edited later.

**Before submitting an invoice:** Check the Item Tax Template, the VAT Return Type on each line, and the tax amounts. On purchase lines, check the VAT Claim Date and VAT Recovery Treatment too.

### Example: standard-rated local purchase

| Field | Value |
|---|---|
| Item Tax Template | VAT 15% - Purchase - Goods |
| VAT Return Type | 6.6 |
| Net taxable purchase | Rs 100,000 |
| VAT | Rs 15,000 |
| Recovery treatment | Shared |
| Filing recovery percentage | 71% |
| Recoverable VAT | Rs 10,650 |

An exempt purchase with type **8.2** contributes its value to the applicable box but not to deductible VAT. A line with VAT Return Type **7** is recorded as non-credit input.

### Capital goods

Where configured, the system can convert a default local purchase category **6.6** into **6.4** for an item marked as a fixed asset. Confirm the treatment on the invoice line.

## 2. Correcting an incorrect VAT Return Type after invoice submission

**Item Tax Template cannot normally be changed after invoice submission.** That does not mean the invoice must be cancelled just to correct its VAT return box.

1. Open the submitted Sales Invoice or Purchase Invoice.
2. Expand the affected item row and find **VAT Return Type**.
3. Edit the **VAT Return Type** directly. The field is configured to allow changes after submission.
4. Save the invoice and verify the selected statutory box.
5. If the invoice is included only in a **Draft** VAT Return Filing, open that filing and choose **Pull Transactions** again to refresh its snapshot.

**Do not change the classification simply to force a return total.** Verify the invoice, tax template and statutory category. If the VAT amount itself is wrong, changing VAT Return Type does not recalculate ERPNext accounting tax entries.

**Submitted filing:** Do not silently reclassify lines already filed. Obtain a reviewed cancellation/amendment or documented adjustment under the company's filing controls.

## 3. The three important purchase dates

- **Supplier Invoice Date:** Date printed on the supplier's tax invoice.
- **Posting Date:** Date the Purchase Invoice enters ERPNext accounts.
- **VAT Claim Date:** Determines which VAT Return Filing picks up the purchase item.

An invoice dated **20 June** may arrive and be booked on **10 July**, but carry a VAT Claim Date of **1 August**. The accounting remains in July. The input VAT appears in August's filing, once, subject to VAT eligibility and the applicable MRA reporting rules.

### Deferring an input VAT claim

On the Purchase Invoice Item, set **VAT Claim Date** to a day in the intended filing month. It may be changed after submission **until** the line has been included in a submitted filing. Pulling July's transactions will leave the August-dated claim out; pulling August will include it.

The default VAT Claim Date is the purchase posting date when the invoice is entered. Existing blank claim dates can be populated through the authorized backfill procedure.

**Partial claims are not supported.** Each purchase item is claimed in one filing or not at all.

### Prior-period filing treatment

A delayed claim is not necessarily an **excess VAT brought forward**. Box **12** must represent an actual credit brought forward from a previous VAT return. Box **13** is for separately supported VAT adjustments. Finance must verify eligibility and presentation for historical invoices; dates alone do not determine a legally correct adjustment box.

## 4. VAT Recovery Treatment and the 71% percentage

Each purchase item has a **VAT Recovery Treatment**:

| Treatment | What is deductible? |
|---|---|
| **Full** | 100% of qualifying source VAT |
| **Shared** | VAT multiplied by the filing's recovery percentage |
| **None** | 0% |

Example for a purchase with Rs 15,000 VAT and a 71% filing recovery percentage:

- **Full:** Rs 15,000.
- **Shared:** Rs 10,650.
- **None:** Rs 0.

The recovery percentage belongs to each filing. It is not automatically calculated from that month's sales. To change it (for example, from **71%** to another approved percentage), open the filing while in **Draft**, update **Input VAT recovery (%)**, and select **Recalculate**. Confirm the percentage against the organization's approved taxable-turnover apportionment working paper.

A filing already submitted must not be silently recalculated using a new percentage.

## 5. Preparing a VAT Return Filing

1. Open **MRA Integration > VAT Return Filings**.
2. Create a new **VAT Return Filing** and select the **Company**.
3. Set **From Date** and **To Date** for the taxable month.
4. Enter the approved **Input VAT recovery (%)** (for example, **71**).
5. Save the draft.
6. If a current-period invoice has no VAT Return Type, correct or backfill the underlying invoice items first.
7. Click **Pull Transactions**. Sales items are selected from the posting period; purchase items are selected using their VAT Claim Date. Verify the populated **Sales Details** and **Purchase Details**.
8. Review each MRA box using **View Breakdown**. Check any unusual classification, prior-period claim, credit note and WHT-related invoice.
9. Add supported **Adjustments** only where necessary, with a reference and an explanatory reason.
10. Click **Recalculate** to refresh MRA box totals, gross input VAT, recoverable VAT, and VAT payable.
11. Review source totals and reconcile against ERPNext and supporting invoice registers.
12. **Submit** the filing only when the return is final and correctly supported.

**Pull Transactions replaces the draft sales and purchase detail snapshots** from source transactions; it keeps the entered adjustment rows. It must not be used on submitted returns.

### Prior-period excess credit

Box **12 - Excess VAT Brought Forward** is normally derived from the previous submitted VAT Return Filing's box **16**. Any manually entered opening credit requires an explanatory reference. Never use this field merely to compensate for a purchase invoice that was not claimed previously.

## 6. Downloading and filing

Choose **Export > Download Excel** to obtain:

- **VAT Return Summary:** MRA boxes and VAT amounts.
- **Notes - Breakdown:** Supporting invoice-item amounts, dates, tax classification, recovery treatment, source references, and adjustments.

Choose **Export > Print MRA VAT Return** for a printable form-style review copy.

**MNS Annex:** The existing phase-one export must be validated against the MRA upload schema before operational filing use. Until the announced 2027 portal changes are implemented and approved, the filing workflow is **manual**. Do not interpret an export as confirmation that the MRA has accepted a return.

After the return is actually filed with MRA, record the **Filing Date**, **MRA Acknowledgement / Reference** and **Filing Status** in ERPNext. These are distinct from the date the internal ERPNext document was submitted.

## 7. Common questions

**Why is an invoice from July appearing in the August purchase breakdown?**  
Its VAT Claim Date is in August; its Posting Date remains July.

**Why is an invoice missing?**  
Check that it is submitted, belongs to the filing company, has a valid VAT Return Type, and has a VAT Claim Date within the relevant period. If the invoice is already in a submitted filing it must not be claimed again.

**Why did changing the Item Tax Template master not change a submitted invoice?**  
The invoice item retains its own VAT Return Type. Update the invoice's VAT Return Type explicitly after verification, where permitted.

**Can I change an item template after invoice submission?**  
Normally no. Edit the permitted VAT Return Type on the submitted invoice item instead; do not recalculate posted tax by simply changing its reporting classification.

**Does withholding tax reduce deductible VAT?**  
No. Supplier withholding affects the payment settlement, not the original VAT taxable base.

**Can I claim 50% in July and the remaining 50% in August?**  
No. Partial allocation across filing periods is outside Phase 1.

**Who should approve the final MRA boxes?**  
The authorized finance reviewer. System categorization assists preparation; statutory classification and the final claim remain the taxpayer's responsibility.
