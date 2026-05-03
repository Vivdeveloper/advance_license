# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "voucher_type",
			"label": _("Voucher Type"),
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"fieldname": "voucher_no",
			"label": _("Voucher No"),
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"fieldname": "posting_date",
			"label": _("Posting Date"),
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"fieldname": "advance_license",
			"label": _("Advance License"),
			"fieldtype": "Link",
			"options": "Advance License",
			"width": 150,
		},
		{
			"fieldname": "license_number",
			"label": _("License Number"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "license_status",
			"label": _("License Status"),
			"fieldtype": "Data",
			"width": 100,
		},

		{
			"fieldname": "item_code",
			"label": _("Item Code"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 130,
		},
		{
			"fieldname": "item_name",
			"label": _("Item Name"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "uom",
			"label": _("UOM"),
			"fieldtype": "Link",
			"options": "UOM",
			"width": 80,
		},
		{
			"fieldname": "qty_allowed",
			"label": _("Allowed on License"),
			"fieldtype": "Float",
			"width": 130,
			"precision": 2,
		},
		{
			"fieldname": "qty",
			"label": _("Qty on Voucher"),
			"fieldtype": "Float",
			"width": 120,
			"precision": 2,
		},
		{
			"fieldname": "note",
			"label": _("Note"),
			"fieldtype": "Data",
			"width": 220,
		},
	]


def get_data(filters):
	data = []
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	advance_license = filters.get("advance_license")
	license_status = filters.get("license_status")
	voucher_type = filters.get("voucher_type")
	item_code = filters.get("item_code")

	if not voucher_type or voucher_type == "Purchase Invoice":
		data.extend(
			_get_purchase_invoice_rows(from_date, to_date, advance_license, item_code, license_status)
		)
	if not voucher_type or voucher_type == "Sales Invoice":
		data.extend(
			_get_sales_invoice_rows(from_date, to_date, advance_license, item_code, license_status)
		)

	data.sort(
		key=lambda r: (
			r.get("advance_license") or "",
			r.get("posting_date") or "",
			r.get("voucher_type") or "",
			r.get("voucher_no") or "",
			r.get("item_code") or "",
		)
	)

	for row in data:
		_set_line_note(row)

	# Build output with subtotal per license and grand total
	out = []
	detail_rows_for_grand_total = []
	current_license = None
	license_rows = []

	for row in data:
		lic = row.get("advance_license") or ""
		if current_license is not None and lic != current_license:
			# Flush previous group with subtotal
			for r in license_rows:
				out.append(r)
				detail_rows_for_grand_total.append(r)
			out.append(_make_subtotal_row(current_license, license_rows))
			license_rows = []
		current_license = lic
		license_rows.append(row)

	if license_rows:
		for r in license_rows:
			out.append(r)
			detail_rows_for_grand_total.append(r)
		out.append(_make_subtotal_row(current_license, license_rows))

	if detail_rows_for_grand_total:
		out.append(_make_total_row(detail_rows_for_grand_total))

	return out


def _get_purchase_invoice_rows(from_date, to_date, advance_license, item_code, license_status=None):
	conditions = ["pi_item.custom_advance_license IS NOT NULL", "pi_item.custom_advance_license != ''", "pi.docstatus = 1"]
	values = []
	license_join = ""
	if license_status:
		license_join = "INNER JOIN `tabAdvance License` al_pi ON al_pi.name = pi_item.custom_advance_license"
		conditions.append("al_pi.status = %s")
		values.append(license_status)
	if from_date:
		conditions.append("pi.posting_date >= %s")
		values.append(from_date)
	if to_date:
		conditions.append("pi.posting_date <= %s")
		values.append(to_date)
	if advance_license:
		conditions.append("pi_item.custom_advance_license = %s")
		values.append(advance_license)
	if item_code:
		conditions.append("pi_item.item_code = %s")
		values.append(item_code)

	rows = frappe.db.sql("""
		SELECT
			pi.name as voucher_no,
			pi.posting_date,
			pi_item.custom_advance_license as advance_license,
			pi_item.item_code,
			pi_item.item_name,
			pi_item.qty,
			pi_item.stock_uom as uom,
			ali.qty_allowed
		FROM `tabPurchase Invoice Item` pi_item
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pi_item.parent
		{license_join}
		LEFT JOIN `tabAdvance License Import` ali ON ali.parent = pi_item.custom_advance_license AND ali.item_of_import = pi_item.item_code
		WHERE {conditions}
		ORDER BY pi.posting_date, pi.name
	""".format(license_join=license_join, conditions=" AND ".join(conditions)), values, as_dict=True)

	license_numbers, license_statuses = _get_license_meta(
		[r.advance_license for r in rows if r.advance_license]
	)

	out = []
	for r in rows:
		out.append(
			{
				"voucher_type": "Purchase Invoice",
				"voucher_no": r.voucher_no,
				"posting_date": r.posting_date,
				"advance_license": r.advance_license,
				"license_number": license_numbers.get(r.advance_license, ""),
				"license_status": license_statuses.get(r.advance_license, ""),
				"qty_allowed": flt(r.qty_allowed),
				"item_code": r.item_code,
				"item_name": r.item_name or "",
				"qty": flt(r.qty),
				"uom": r.uom or "",
			}
		)
	return out


def _get_sales_invoice_rows(from_date, to_date, advance_license, item_code, license_status=None):
	conditions = ["si_item.custom_advance_license IS NOT NULL", "si_item.custom_advance_license != ''", "si.docstatus = 1"]
	values = []
	license_join = ""
	if license_status:
		license_join = "INNER JOIN `tabAdvance License` al_si ON al_si.name = si_item.custom_advance_license"
		conditions.append("al_si.status = %s")
		values.append(license_status)
	if from_date:
		conditions.append("si.posting_date >= %s")
		values.append(from_date)
	if to_date:
		conditions.append("si.posting_date <= %s")
		values.append(to_date)
	if advance_license:
		conditions.append("si_item.custom_advance_license = %s")
		values.append(advance_license)
	if item_code:
		conditions.append("si_item.item_code = %s")
		values.append(item_code)

	rows = frappe.db.sql("""
		SELECT
			si.name as voucher_no,
			si.posting_date,
			si_item.custom_advance_license as advance_license,
			si_item.item_code,
			si_item.item_name,
			si_item.qty,
			si_item.stock_uom as uom,
			ale.qty_allowed
		FROM `tabSales Invoice Item` si_item
		INNER JOIN `tabSales Invoice` si ON si.name = si_item.parent
		{license_join}
		LEFT JOIN `tabAdvance License Export` ale ON ale.parent = si_item.custom_advance_license AND ale.item_of_export = si_item.item_code
		WHERE {conditions}
		ORDER BY si.posting_date, si.name
	""".format(license_join=license_join, conditions=" AND ".join(conditions)), values, as_dict=True)

	license_numbers, license_statuses = _get_license_meta(
		[r.advance_license for r in rows if r.advance_license]
	)

	out = []
	for r in rows:
		out.append(
			{
				"voucher_type": "Sales Invoice",
				"voucher_no": r.voucher_no,
				"posting_date": r.posting_date,
				"advance_license": r.advance_license,
				"license_number": license_numbers.get(r.advance_license, ""),
				"license_status": license_statuses.get(r.advance_license, ""),
				"qty_allowed": flt(r.qty_allowed),
				"item_code": r.item_code,
				"item_name": r.item_name or "",
				"qty": flt(r.qty),
				"uom": r.uom or "",
			}
		)
	return out


def _get_license_meta(license_names):
	"""Advance License doc `license_number` (display id) and `status` per name."""
	if not license_names:
		return {}, {}
	unique = list({name for name in license_names if name})
	licenses = frappe.get_all(
		"Advance License",
		filters={"name": ["in", unique]},
		fields=["name", "license_number", "status"],
	)
	numbers = {d.name: d.license_number or d.name for d in licenses}
	statuses = {d.name: d.status or "" for d in licenses}
	return numbers, statuses


def _set_line_note(row):
	"""One short note per line: only when something is wrong (keeps the grid easy to read)."""
	allowed = flt(row.get("qty_allowed"))
	line_qty = flt(row.get("qty"))
	if allowed <= 0 and line_qty > 0:
		row["note"] = _("No allowance for this item on the license")
	elif line_qty > allowed:
		over = flt(line_qty - allowed)
		row["note"] = _("This voucher is {0} over the allowed qty").format(over)
	else:
		row["note"] = ""


def _make_subtotal_row(advance_license_name, rows):
	"""Subtotal row for one Advance License group."""
	license_number = rows[0].get("license_number", "") if rows else ""
	al_status = rows[0].get("license_status", "") if rows else ""
	return {
		"voucher_type": "",
		"voucher_no": _("Total ({0})").format(license_number or advance_license_name),
		"posting_date": "",
		"advance_license": advance_license_name,
		"license_number": license_number,
		"license_status": al_status,
		"qty_allowed": "",
		"item_code": "",
		"item_name": "",
		"qty": flt(sum(r.get("qty") for r in rows)),
		"note": _("See Notes on lines above") if any((r.get("note") or "").strip() for r in rows) else "",
		"uom": "",
	}


def _make_total_row(rows):
	"""Grand total row."""
	return {
		"voucher_type": "",
		"voucher_no": _("Grand Total"),
		"posting_date": "",
		"advance_license": "",
		"license_number": "",
		"license_status": "",
		"qty_allowed": "",
		"item_code": "",
		"item_name": "",
		"qty": flt(sum(r.get("qty") for r in rows)),
		"note": _("See Notes on lines above") if any((r.get("note") or "").strip() for r in rows) else "",
		"uom": "",
	}
