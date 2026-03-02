# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


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
			"fieldname": "qty_allowed",
			"label": _("Qty Allowed"),
			"fieldtype": "Float",
			"width": 100,
			"precision": 2,
		},
		{
			"fieldname": "qty",
			"label": _("Qty"),
			"fieldtype": "Float",
			"width": 100,
			"precision": 2,
		},
		{
			"fieldname": "uom",
			"label": _("UOM"),
			"fieldtype": "Link",
			"options": "UOM",
			"width": 80,
		},
	]


def get_data(filters):
	data = []
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	advance_license = filters.get("advance_license")
	voucher_type = filters.get("voucher_type")
	item_code = filters.get("item_code")

	if not voucher_type or voucher_type == "Purchase Invoice":
		data.extend(
			_get_purchase_invoice_rows(from_date, to_date, advance_license, item_code)
		)
	if not voucher_type or voucher_type == "Sales Invoice":
		data.extend(
			_get_sales_invoice_rows(from_date, to_date, advance_license, item_code)
		)

	# Group by Advance License (name), then by posting_date, voucher
	data.sort(key=lambda r: (
		r.get("advance_license") or "",
		r.get("posting_date") or "",
		r.get("voucher_type") or "",
		r.get("voucher_no") or "",
	))

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


def _get_purchase_invoice_rows(from_date, to_date, advance_license, item_code):
	conditions = ["pi_item.custom_advance_license IS NOT NULL", "pi_item.custom_advance_license != ''", "pi.docstatus = 1"]
	values = []
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
		LEFT JOIN `tabAdvance License Import` ali ON ali.parent = pi_item.custom_advance_license AND ali.item_of_import = pi_item.item_code
		WHERE {conditions}
		ORDER BY pi.posting_date, pi.name
	""".format(conditions=" AND ".join(conditions)), values, as_dict=True)

	license_numbers = _get_license_numbers([r.advance_license for r in rows if r.advance_license])

	out = []
	for r in rows:
		out.append({
			"voucher_type": "Purchase Invoice",
			"voucher_no": r.voucher_no,
			"posting_date": r.posting_date,
			"advance_license": r.advance_license,
			"license_number": license_numbers.get(r.advance_license, ""),
			"qty_allowed": flt(r.qty_allowed),
			"item_code": r.item_code,
			"item_name": r.item_name or "",
			"qty": flt(r.qty),
			"uom": r.uom or "",
		})
	return out


def _get_sales_invoice_rows(from_date, to_date, advance_license, item_code):
	conditions = ["si_item.custom_advance_license IS NOT NULL", "si_item.custom_advance_license != ''", "si.docstatus = 1"]
	values = []
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
		LEFT JOIN `tabAdvance License Export` ale ON ale.parent = si_item.custom_advance_license AND ale.item_of_export = si_item.item_code
		WHERE {conditions}
		ORDER BY si.posting_date, si.name
	""".format(conditions=" AND ".join(conditions)), values, as_dict=True)

	license_numbers = _get_license_numbers([r.advance_license for r in rows if r.advance_license])

	out = []
	for r in rows:
		out.append({
			"voucher_type": "Sales Invoice",
			"voucher_no": r.voucher_no,
			"posting_date": r.posting_date,
			"advance_license": r.advance_license,
			"license_number": license_numbers.get(r.advance_license, ""),
			"qty_allowed": flt(r.qty_allowed),
			"item_code": r.item_code,
			"item_name": r.item_name or "",
			"qty": flt(r.qty),
			"uom": r.uom or "",
		})
	return out


def _get_license_numbers(license_names):
	if not license_names:
		return {}
	licenses = frappe.get_all(
		"Advance License",
		filters={"name": ["in", list(set(license_names))]},
		fields=["name", "license_number"],
	)
	return {d.name: d.license_number or d.name for d in licenses}


def _make_subtotal_row(advance_license_name, rows):
	"""Subtotal row for one Advance License group."""
	license_number = rows[0].get("license_number", "") if rows else ""
	return {
		"voucher_type": "",
		"voucher_no": _("Total ({0})").format(license_number or advance_license_name),
		"posting_date": "",
		"advance_license": advance_license_name,
		"license_number": license_number,
		"qty_allowed": "",
		"item_code": "",
		"item_name": "",
		"qty": flt(sum(r.get("qty") for r in rows)),
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
		"qty_allowed": "",
		"item_code": "",
		"item_name": "",
		"qty": flt(sum(r.get("qty") for r in rows)),
		"uom": "",
	}
