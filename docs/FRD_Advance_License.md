# Functional Requirements Document (FRD)
# Advance License – Working Flow

**App:** advance_license  
**Version:** 0.0.1  
**Framework:** Frappe / ERPNext 16.x

---

## 1. Overview

### 1.1 Purpose

The Advance License module manages Advance Licenses for import/export under DGFT (Directorate General of Foreign Trade) rules. It tracks license items, quantities, expiry dates, and validates usage against Purchase Invoices (import) and Sales Invoices (export).

### 1.2 Scope

- Advance License creation and maintenance
- Link licenses to Purchase Invoice (import items) and Sales Invoice (export items)
- Quantity validation against allowed vs used
- Balance quantity reporting

---

## 2. User Roles & Prerequisites

| Role | Access |
|------|--------|
| System Manager | Full access to Advance License, reports, and configuration |
| Purchase User | Create/edit Purchase Invoice with Advance License |
| Sales User | Create/edit Sales Invoice with Advance License |

**Prerequisites:**
- ERPNext installed with Currency, Item, UOM
- Supplier/Customer marked as "Advance License Applicable" where needed

---

## 3. Master Data Setup

### 3.1 Supplier / Customer

- **Supplier:** Set `Advance License Applicable` = Yes to show Advance License field on Purchase Invoice
- **Customer:** Set `Advance License Applicable` = Yes to show Advance License field on Sales Invoice

### 3.2 Items

- **Import items:** Must have `is_purchase_item` = 1 (used in Advance License Import)
- **Export items:** Must have `is_sales_item` = 1 (used in Advance License Export)

---

## 4. Advance License – Creation Flow

### 4.1 Create Advance License

**Path:** Advance License → New

### 4.2 Fields & Sections

| Section | Field | Type | Required | Description |
|---------|-------|------|----------|-------------|
| Detail | License Number | Data | Auto | Unique, auto from field |
| | Posting Date | Date | Yes | Current License Date |
| | Currency | Link (Currency) | | Default: USD |
| | Local Currency | Link (Currency) | | Default: INR |
| | Application Type | Select | | SION, Non SION-Fresh, Non SION-Repeat |
| | License Type | Select | | Advance Licence |
| | Status | Select | | Active, Hold, Closed, Cancelled |
| | Approval Date | Date | | |
| | Remark | Small Text | | |
| Export/Import Values | Export Exchange Rate | Float | | Auto-fetched from ERPNext |
| | Value of Export (FCY) | Currency | | |
| | Value of Export (Local) | Currency | | Auto: FCY × rate |
| | Import Exchange Rate | Float | | Auto-fetched |
| | Value of Import (FCY) | Currency | | |
| | Value of Import (Local) | Currency | | Auto: FCY × rate |
| | Licence Expiry (Months) | Int | | Auto from Import/Export expiry dates |
| | Import Expiry Date | Date | Conditional | If value_import_inr > 0 |
| | Export Expiry Date | Date | Conditional | If value_export_inr > 0 |
| Item of Import | import_items | Table | Yes | Child: Advance License Import |
| Item of Export | export_items | Table | Yes | Child: Advance License Export |

### 4.3 Child Table – Advance License Import

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Item of Import | Link (Item) | Yes | Filter: is_purchase_item=1 |
| Qty Allowed | Float | Yes | Must be > 0 |
| UOM | Link (UOM) | | Fetched from Item |
| Wastage % | Percent | | Optional |
| Description | Data | | Optional |

### 4.4 Child Table – Advance License Export

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Item of Export | Link (Item) | Yes | Filter: is_sales_item=1 |
| Qty Allowed | Float | Yes | Must be > 0 |
| UOM | Link (UOM) | | Fetched from Item |
| Description | Long Text | | Optional |

### 4.5 Auto-Behaviour (Client-Side)

1. **Exchange rates:** Fetched on change of Currency, Local Currency, or Posting Date
2. **Local values:** Value of Export/Import (Local) = FCY × Exchange Rate
3. **Licence Expiry Months:** When both Import Expiry Date and Export Expiry Date are set:
   - Months = difference (Export Expiry Date − Import Expiry Date)
   - Validation: both dates ≥ Posting Date; Import Expiry Date ≤ Export Expiry Date

### 4.6 Validations (Server-Side)

- Qty Allowed > 0 for all Import and Export items

---

## 5. Purchase Invoice – Using Advance License (Import)

### 5.1 Flow

1. Create Purchase Invoice
2. Select **Supplier** with `Advance License Applicable` = Yes
3. Field **Advance License** becomes visible
4. Add items to the invoice
5. **Advance License** dropdown shows only licenses that:
   - Have status Active or Hold
   - Contain the invoice items in Import table
   - Have sufficient balance (Qty Allowed − Used Qty ≥ invoice qty)
6. Select Advance License
7. Save / Submit

### 5.2 Validations (On Save / Submit)

- Advance License status cannot be **Hold**
- All invoice items must exist in the license Import table
- For each item: Available Qty (Qty Allowed − Used in submitted PIs) ≥ invoice qty
- Current invoice is excluded when calculating used qty (for edit scenario)

### 5.3 Used Qty Calculation

- **Used Qty** = SUM(qty) from submitted Purchase Invoice Items where:
  - `custom_advance_license` = selected license
  - `item_code` = item
  - `docstatus` = 1

---

## 6. Sales Invoice – Using Advance License (Export)

### 6.1 Flow

1. Create Sales Invoice
2. Select **Customer** with `Advance License Applicable` = Yes
3. Field **Advance License** becomes visible
4. Add items to the invoice
5. **Advance License** dropdown shows only licenses that:
   - Have status Active or Hold
   - Contain the invoice items in Export table
   - Have sufficient balance (Qty Allowed − Used Qty ≥ invoice qty)
6. Select Advance License
7. Save / Submit

### 6.2 Validations (On Save / Submit)

- Advance License status cannot be **Hold**
- All invoice items must exist in the license Export table
- For each item: Available Qty (Qty Allowed − Used in submitted SIs) ≥ invoice qty
- Current invoice is excluded when calculating used qty (for edit scenario)

### 6.3 Used Qty Calculation

- **Used Qty** = SUM(qty) from submitted Sales Invoice Items where:
  - `custom_advance_license` = selected license
  - `item_code` = item
  - `docstatus` = 1

---

## 7. Advance License Balance Quantity Report

### 7.1 Path

Reports → Advance License Balance Quantity

### 7.2 Filters

| Filter | Type | Default | Description |
|--------|------|---------|-------------|
| Advance License | Link | | Specific license or all |
| Status | Select | Active | License status |
| Date Range | Date Range | | Filter by Import/Export expiry |
| Item Type | Select | | Import / Export |
| Items | Multi-select | | Filter by item codes |

### 7.3 Columns

| Column | Description |
|--------|-------------|
| License Number | Link to Advance License |
| Status | Active / Hold / Closed / Cancelled |
| Import Expiry Date | For Import rows |
| Export Expiry Date | For Export rows |
| Item Type | Import / Export |
| Item Code | Link to Item |
| Item Name | From Item |
| UOM | Unit of Measure |
| Qty Allowed | From license |
| Used Qty | From submitted invoices |
| Balance Qty | Qty Allowed − Used Qty |

### 7.4 Logic

- One row per license item (Import or Export)
- Used Qty from submitted Purchase Invoice (Import) or Sales Invoice (Export)
- Balance Qty = Qty Allowed − Used Qty
- Date Range filters rows by Import/Export expiry falling in range

---

## 8. API Methods (Whitelisted)

| Method | Purpose |
|--------|---------|
| `advance_license.api.get_available_licenses(items, exclude_pi)` | Licenses for Purchase Invoice (import) |
| `advance_license.api.get_available_licenses_for_sales(items, exclude_si)` | Licenses for Sales Invoice (export) |
| `advance_license.api.validate_license_qty(license_name, items, exclude_pi)` | Validate qty for Purchase Invoice |
| `advance_license.api.validate_sales_invoice_license_qty(license_name, items, exclude_si)` | Validate qty for Sales Invoice |

---

## 9. End-to-End Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ADVANCE LICENSE WORKING FLOW                          │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │ 1. Master Setup   │
  │  - Supplier/Cust  │
  │    Advance Lic    │
  │    Applicable=Yes │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐     ┌──────────────────┐
  │ 2. Advance        │     │ 3. Items         │
  │    License        │────▶│    (Import/      │
  │    Creation       │     │     Export)      │
  └────────┬─────────┘     └──────────────────┘
           │
           │  • Import items (qty_allowed)
           │  • Export items (qty_allowed)
           │  • Expiry dates
           │  • Status: Active/Hold/Closed
           │
           ▼
  ┌──────────────────┐     ┌──────────────────┐
  │ 4. Purchase       │     │ 5. Sales         │
  │    Invoice        │     │    Invoice       │
  │    (Import)       │     │    (Export)     │
  └────────┬─────────┘     └────────┬────────┘
           │                         │
           │  Select License         │  Select License
           │  Add items              │  Add items
           │  Validate qty           │  Validate qty
           │  Submit                 │  Submit
           │                         │
           ▼                         ▼
  ┌──────────────────────────────────────────┐
  │ 6. Used Qty tracked in submitted         │
  │    Purchase Invoice / Sales Invoice      │
  └──────────────────────────────────────────┘
           │
           ▼
  ┌──────────────────────────────────────────┐
  │ 7. Advance License Balance Quantity      │
  │    Report: Qty Allowed - Used = Balance  │
  └──────────────────────────────────────────┘
```

---

## 10. Error Messages

| Condition | Message |
|-----------|---------|
| License status = Hold | Cannot use Advance License {0} with status 'Hold'. |
| Item not in license | Item {0} not found in Advance License {1}. |
| Insufficient qty | Insufficient qty for item {0}. Required: {1}, Available: {2}. |
| Qty allowed = 0 | Qty allowed cannot be 0 in row {0} of Import/Export Items. |
| Expiry date overlap | Import Expiry Date cannot be after Export Expiry Date. |
| Expiry before license date | Import Expiry Date and Export Expiry Date must be on or after Current License Date. |

---

## 11. Dependencies

- **Frappe** 16.x
- **ERPNext** 16.x (for exchange rates, Item, Currency, UOM)
- Custom fields on: Purchase Invoice, Sales Invoice, Supplier, Customer

---

## 12. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-02-25 | - | Initial FRD |
