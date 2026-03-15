# ERPNext Country Specific Functionality for Mauritius (CSF MU)

## Overview

CSF MU adds Mauritius Revenue Authority (MRA) e‑invoicing support to ERPNext. It introduces the required settings, custom fields, validations, tax code mapping, invoice transmission, and logging.


---

## Install

```bash
bench --site <your.site> install-app csf_mu
bench --site <your.site> migrate
bench --site <your.site> clear-cache
```

---

## Core Setup

### 1. CSF MU Settings

Go to **CSF MU Settings** and fill:

- Main screen fields:
  - `Auth URL`
  - `Transmit URL`
- Add one row per company in **Settings Details** and fill:
  - `Company`
  - `Username`, `Password`
  - `EBS MRA ID`, `Area Code`
  - `Public Key Certificate`
  - `Max Invoices Per Request` (default 500)
  - Optional: `Enable PRF/TRN Invoices`
  - Optional: `Auto Send to MRA on Submit`

Notes:
- Token + encryption key are cached per company settings row.
- `Max Invoices Per Request` is enforced per company.

### 2. Company Fields (MRA Tab)

Required:
- `TAN`
- `BRN`
- `Business Address`

Optional:
- `Trade Name`
- `Business Phone`
- `Person Type` (VATR/NVTR)

### 3. Customer Fields (MRA Section)

Required only for B2B/B2G:
- `Buyer Type`
- `TAN`
- `BRN` (B2B only)

Other fields:
- `Transaction Type` (B2B/B2G/B2C/EXP/B2E)
- `Business Address`
- `NIC / NCID`

### 4. Tax Code Mapping

Create **MRA Tax Code Map** records that link:
- `Item Tax Template`
- `Tax Code`
- `Nature` (GOODS or SERVICES)

### 5. Item Tax Template (ERPNext Setup)

**Step 1 — Create Sales Taxes & Charges Template**
- Go to **Accounts → Sales Taxes and Charges Template**
- Create or select a VAT template (e.g. VAT 15%)
- This template defines the tax account (use your company VAT account) and rate

**Step 2 — Create Item Tax Template**
- Go to **Accounts → Item Tax Template**
- Name it clearly (e.g. `MRA TC01 GOODS - B`)
- Add a tax row pointing to your company VAT account and rate
- Save the template

Auto‑create option:
- On **Company**, click **Create MRA Item Tax Templates**.
- This generates standard MRA templates and maps them to tax codes.  
  Update the tax accounts/rates to match your company setup if needed.

**Step 3 — Map it to MRA Tax Code**
- Create an **MRA Tax Code Map**
- Link the Item Tax Template
- Choose the correct **Tax Code** and **Nature**

**Step 4 — Assign to Items**
- On each **Item**, set **Item Tax Template**
- This is how the system decides which MRA Tax Code to send

Tip:
- You can also set a **Default Item Tax Template** on the Sales Invoice,
  but item‑level templates are required if you sell mixed goods/services.

Tax Code meanings (MRA Data Structure):
- `TC01` = Taxable supplies at 15%
- `TC02` = Taxable supplies at zero rate
- `TC03` = Exempt supplies
- `TC04` = Non‑fiscal items not affecting turnover
- `TC05` = Standard rated supplies to exempt bodies/persons
- `TC06` = Supplies outside VAT scope

---

## How It Works

### Sales Invoice

On submit, CSF MU:
- Validates item tax templates and MRA mapping
- Validates buyer details for B2B/B2G
- Validates CRN/DRN requirements
- Builds payload and transmits to MRA (if `Auto Send to MRA on Submit` is enabled)
- Writes **MRA Einvoice Log** and updates `mra_status`

### Credit Note (CRN)

Use **Return / Credit Note** from a submitted invoice.
- `return_against` is required
- `Reason Stated` is required
- `mra_invoice_type_desc` is set to CRN

### Debit Note (DRN)

Use **Is Rate Adjustment Entry (Debit Note)**.
- `return_against` is required
- `Reason Stated` is required
- `mra_invoice_type_desc` is set to DRN

### PRF / TRN

Enable **Enable PRF/TRN Invoices** in the company row under **Settings Details**.
The **Invoice Type (MRA)** field appears and allows PRF/TRN.

---

## Batch Transmit (Single Request)

Use **Sales Invoice List → Send to MRA (Batch Request)** to send many invoices in one request.

Limits:
- Max invoices per request: 500
- Max total items per request: 5000
- Single company per batch request

Progress bar shows processing status.

---

## Logging

### MRA Einvoice Log

Stores:
- Request JSON
- Response JSON
- Status
- IRN
- QR Code
- Error details (child table: **MRA Invoice Log Detail**)

---

## Compliance Notes

- `previousNoteHash` is computed automatically using SHA‑256 and chained per invoice type.
- CRN/DRN must reference a **SUCCESS** fiscalised invoice.
- Buyer fields are enforced for B2B/B2G.

---

## Troubleshooting

Common causes of rejection:
- Missing Company TAN/BRN/Address
- Missing Customer buyer fields for B2B/B2G
- Missing MRA Tax Code Map
- Invalid `return_against` for CRN/DRN

---

## Test Case Coverage (MRA Portal)

- STD, CRN, DRN, PRF, TRN supported
- Batch transmit supports the 10‑invoice test case
- Failed scenario (wrong TAN) behaves as expected

---

## Support

For project setup or customizations, contact the implementation team.
