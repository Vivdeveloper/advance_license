# Advance License – FRD (Simple)

**App:** advance_license · **Framework:** Frappe / ERPNext 16.x

---

## 1. Overview

Advance License tracks import/export licenses (DGFT). You create a license with **Import** and **Export** items and **Qty Allowed** per item. Purchase Invoices (import) and Sales Invoices (export) can use a license per item row; used qty is summed from submitted invoices. **Balance = Qty Allowed − Used Qty.**

---

## 2. Setup

- **Supplier:** Set *Advance License Applicable* = Yes → Advance License field shows on Purchase Invoice items.
- **Customer:** Set *Advance License Applicable* = Yes → Advance License field shows on Sales Invoice items.
- **Items:** Use purchase items for Import, sales items for Export (as in license child tables).

---

## 3. Advance License

- **Path:** Advance License → New
- **Main:** License Number (auto), Posting Date, Status (Active / Hold / Closed / Cancelled), Import/Export expiry dates, currency and values.
- **Import items (table):** Item, Qty Allowed, UOM. Qty Allowed > 0.
- **Export items (table):** Item, Qty Allowed, UOM. Qty Allowed > 0.

---

## 4. Purchase Invoice (Import)

- Supplier must have *Advance License Applicable* = Yes.
- On each **item row** you can set **Advance License**. Only licenses with status Active or Hold appear; only those that include the item and have **Balance Qty ≥ invoice qty** are offered.
- **On save/submit:** System checks item is in license Import table and balance qty is enough (current invoice excluded when calculating used qty).
- **Used qty** = sum of qty on submitted Purchase Invoice items where `custom_advance_license` = that license and `item_code` = that item.

---

## 5. Sales Invoice (Export)

- Customer must have *Advance License Applicable* = Yes.
- On each **item row** you can set **Advance License**. Only licenses with status Active or Hold appear; only those that include the item and have **Balance Qty ≥ invoice qty** are offered.
- **On save/submit:** System checks item is in license Export table and balance qty is enough (current invoice excluded).
- **Used qty** = sum of qty on submitted Sales Invoice items where `custom_advance_license` = that license and `item_code` = that item.

---

## 6. Reports

### Advance License Balance Quantity

- **Path:** Reports → Advance License Balance Quantity
- **Filters:** Advance License, Status (default Active), Item Type (Import/Export), Items, Expiry Date Range
- **Content:** One row per license item (Import or Export): License, Status, Expiry dates, Item, Qty Allowed, Used Qty, Balance Qty. Grouped by license with subtotal and grand total.

### Advance License Voucher Wise

- **Path:** Reports → Advance License Voucher Wise
- **Filters:** From/To Date, Advance License, Voucher Type (PI/SI), Item
- **Content:** One row per voucher line (PI or SI item with advance license): Voucher Type, Voucher No, Posting Date, Advance License, License Number, Qty Allowed, Item, Qty. Grouped by Advance License with subtotal and grand total.

---

## 7. API (for developers)

| Method | Use |
|--------|-----|
| `get_available_licenses(items, exclude_pi)` | Licenses for Purchase Invoice |
| `get_available_licenses_for_sales(items, exclude_si)` | Licenses for Sales Invoice |
| `validate_license_qty(license_name, items, exclude_pi)` | Validate qty for PI |
| `validate_sales_invoice_license_qty(license_name, items, exclude_si)` | Validate qty for SI |

---

## 8. Flow (summary)

1. Set Supplier/Customer → Advance License Applicable = Yes.
2. Create Advance License with Import/Export items and Qty Allowed.
3. On PI (import): select license per item; system checks balance.
4. On SI (export): select license per item; system checks balance.
5. Used qty comes from submitted PI/SI; Balance = Qty Allowed − Used.
6. Use Balance Quantity report or Voucher Wise report to see usage.

---

## 9. Common errors

- **Hold:** Advance License has status Hold (warning).
- **Item not in license:** Item not in license Import/Export table.
- **Insufficient qty:** Required qty > Balance Qty for that item.
- **Expiry:** Import Expiry ≤ Export Expiry; both ≥ Posting Date.

---

## 10. Dependencies

- Frappe 16.x, ERPNext 16.x
- Custom fields: Purchase Invoice Item, Sales Invoice Item, Supplier, Customer (advance license related)
