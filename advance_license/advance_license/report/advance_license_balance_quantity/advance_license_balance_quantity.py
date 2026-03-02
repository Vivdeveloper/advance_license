# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate
from advance_license.api import _get_available_qty


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "license_number",
			"label": _("Advance License"),
			"fieldtype": "Data",
			"width": 150,
			"align": "left",
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "import_expiry_date",
			"label": _("Import Expiry Date"),
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "export_expiry_date",
			"label": _("Export Expiry Date"),
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "item_type",
			"label": _("Item Type"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "item_code",
			"label": _("Item Code"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
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
			"label": _("Qty Allowed"),
			"fieldtype": "Float",
			"width": 120,
			"precision": 2,
		},
		{
			"fieldname": "used_qty",
			"label": _("Used Qty"),
			"fieldtype": "Float",
			"width": 120,
			"precision": 2,
		},
		{
			"fieldname": "balance_qty",
			"label": _("Balance Qty"),
			"fieldtype": "Float",
			"width": 120,
			"precision": 2,
		},
	]


def get_data(filters):
	license_filters = _build_license_filters(filters)
	from_date, to_date = _parse_date_range(filters.get("date_range"))
	items_filter = _parse_items_filter(filters.get("items"))
	item_type_filter = filters.get("item_type")

	licenses = frappe.get_all(
		"Advance License",
		filters=license_filters,
		fields=["name", "license_number", "status", "import_expiry_date", "export_expiry_date"],
	)

	data = []
	all_item_codes = []
	detail_rows_for_grand_total = []

	for license_doc in licenses:
		show_import, show_export = _should_show_license_by_date(
			license_doc, from_date, to_date, item_type_filter
		)
		if not show_import and not show_export:
			continue

		license_rows = []

		if (not item_type_filter or item_type_filter == "Import") and show_import:
			import_rows = frappe.get_all(
				"Advance License Import",
				filters={"parent": license_doc.name},
				fields=["item_of_import", "qty_allowed", "uom"],
			)
			for item in import_rows:
				item_code = item.item_of_import
				if items_filter and item_code not in items_filter:
					continue
				all_item_codes.append(item_code)
				qty_allowed = flt(item.qty_allowed)
				available = _get_available_qty(license_doc.name, item_code, qty_allowed, "purchase")
				used_qty = qty_allowed - available
				row = _make_row(
					license_doc,
					item_code,
					qty_allowed,
					used_qty,
					available,
					"Import",
					uom=item.uom,
					import_expiry=license_doc.import_expiry_date,
					export_expiry=None,
				)
				license_rows.append(row)

		if (not item_type_filter or item_type_filter == "Export") and show_export:
			export_rows = frappe.get_all(
				"Advance License Export",
				filters={"parent": license_doc.name},
				fields=["item_of_export", "qty_allowed", "uom"],
			)
			for item in export_rows:
				item_code = item.item_of_export
				if items_filter and item_code not in items_filter:
					continue
				all_item_codes.append(item_code)
				qty_allowed = flt(item.qty_allowed)
				available = _get_available_qty(license_doc.name, item_code, qty_allowed, "sales")
				used_qty = qty_allowed - available
				row = _make_row(
					license_doc,
					item_code,
					qty_allowed,
					used_qty,
					available,
					"Export",
					uom=item.uom,
					import_expiry=None,
					export_expiry=license_doc.export_expiry_date,
				)
				license_rows.append(row)

		for row in license_rows:
			data.append(row)
			detail_rows_for_grand_total.append(row)
		if license_rows:
			data.append(_make_subtotal_row(license_doc, license_rows))

	item_names = _get_item_names(list(set(all_item_codes)))
	for row in data:
		if row.get("item_code"):
			row["item_name"] = item_names.get(row["item_code"], "")

	if detail_rows_for_grand_total:
		data.append(_make_total_row(detail_rows_for_grand_total))

	return data


def _build_license_filters(filters):
	license_filters = {}
	if filters.get("advance_license"):
		license_filters["name"] = filters.get("advance_license")
	license_filters["status"] = filters.get("status") or "Active"
	return license_filters


def _parse_date_range(date_range):
	if not date_range:
		return None, None
	if isinstance(date_range, str):
		date_range = frappe.parse_json(date_range)
	if isinstance(date_range, list) and len(date_range) == 2:
		return getdate(date_range[0]), getdate(date_range[1])
	return None, None


def _parse_items_filter(items_filter):
	if not items_filter:
		return []
	if isinstance(items_filter, str):
		items_filter = frappe.parse_json(items_filter)
	return [item.strip() for item in items_filter] if isinstance(items_filter, list) else []


def _should_show_license_by_date(license_doc, from_date, to_date, item_type_filter):
	if not from_date or not to_date:
		return True, True
	show_import = False
	show_export = False
	if (not item_type_filter or item_type_filter == "Import") and license_doc.import_expiry_date:
		import_expiry_date = getdate(license_doc.import_expiry_date)
		if from_date <= import_expiry_date <= to_date:
			show_import = True
	if (not item_type_filter or item_type_filter == "Export") and license_doc.export_expiry_date:
		export_expiry_date = getdate(license_doc.export_expiry_date)
		if from_date <= export_expiry_date <= to_date:
			show_export = True
	return show_import, show_export


def _get_item_names(item_codes):
	if not item_codes:
		return {}
	items = frappe.get_all(
		"Item",
		filters={"name": ["in", item_codes]},
		fields=["name", "item_name"],
	)
	return {d.name: d.item_name or "" for d in items}


def _make_row(
	license_doc,
	item_code,
	qty_allowed,
	used_qty,
	balance_qty,
	item_type,
	uom=None,
	import_expiry=None,
	export_expiry=None,
):
	return {
		"license_number": license_doc.license_number or license_doc.name,
		"status": license_doc.status,
		"import_expiry_date": import_expiry or "",
		"export_expiry_date": export_expiry or "",
		"item_type": item_type,
		"item_code": item_code,
		"item_name": "",  # filled later in batch
		"uom": uom or "",
		"qty_allowed": qty_allowed,
		"used_qty": used_qty,
		"balance_qty": balance_qty,
	}


def _make_subtotal_row(license_doc, rows):
	"""Subtotal row for one license group."""
	return {
		"license_number": _("Total ({0})").format(license_doc.license_number or license_doc.name),
		"status": "",
		"import_expiry_date": "",
		"export_expiry_date": "",
		"item_type": "",
		"item_code": "",
		"item_name": "",
		"uom": "",
		"qty_allowed": flt(sum(r.get("qty_allowed") for r in rows)),
		"used_qty": flt(sum(r.get("used_qty") for r in rows)),
		"balance_qty": flt(sum(r.get("balance_qty") for r in rows)),
	}


def _make_total_row(rows):
	"""Grand total row."""
	return {
		"license_number": _("Grand Total"),
		"status": "",
		"import_expiry_date": "",
		"export_expiry_date": "",
		"item_type": "",
		"item_code": "",
		"item_name": "",
		"uom": "",
		"qty_allowed": flt(sum(r.get("qty_allowed") for r in rows)),
		"used_qty": flt(sum(r.get("used_qty") for r in rows)),
		"balance_qty": flt(sum(r.get("balance_qty") for r in rows)),
	}

