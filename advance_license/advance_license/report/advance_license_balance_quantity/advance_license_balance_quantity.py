# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate
from advance_license.api import _get_license_items, _get_available_qty


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "license_number",
			"label": _("License Number"),
			"fieldtype": "Link",
			"options": "Advance License",
			"width": 150,
			"align": "left"
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "import_expiry_date",
			"label": _("Import Expiry Date"),
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "export_expiry_date",
			"label": _("Export Expiry Date"),
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "item_type",
			"label": _("Item Type"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "item_code",
			"label": _("Item Code"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 150
		},
		{
			"fieldname": "item_name",
			"label": _("Item Name"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "uom",
			"label": _("UOM"),
			"fieldtype": "Link",
			"options": "UOM",
			"width": 80
		},
		{
			"fieldname": "qty_allowed",
			"label": _("Qty Allowed"),
			"fieldtype": "Float",
			"width": 120,
			"precision": 2
		},
		{
			"fieldname": "used_qty",
			"label": _("Used Qty"),
			"fieldtype": "Float",
			"width": 120,
			"precision": 2
		},
		{
			"fieldname": "balance_qty",
			"label": _("Balance Qty"),
			"fieldtype": "Float",
			"width": 120,
			"precision": 2
		}
	]


def get_data(filters):
	data = []
	license_filters = {}
	
	if filters.get("advance_license"):
		license_filters["name"] = filters.get("advance_license")
	
	if filters.get("status"):
		license_filters["status"] = filters.get("status")
	else:
		license_filters["status"] = "Active"
	
	date_range = filters.get("date_range")
	from_date = None
	to_date = None
	
	if date_range:
		if isinstance(date_range, str):
			date_range = frappe.parse_json(date_range)
		if isinstance(date_range, list) and len(date_range) == 2:
			from_date = getdate(date_range[0])
			to_date = getdate(date_range[1])
	
	licenses = frappe.get_all(
		"Advance License",
		filters=license_filters,
		fields=["name", "license_number", "status", "current_license_date", "import_expiry_date", "export_expiry_date"]
	)
	
	item_type_filter = filters.get("item_type")
	items_filter = filters.get("items")
	
	if items_filter:
		if isinstance(items_filter, str):
			items_filter = frappe.parse_json(items_filter)
		items_filter = [item.strip() for item in items_filter] if isinstance(items_filter, list) else []
	
	for license_doc in licenses:
		license_name = license_doc.name
		import_expiry = license_doc.import_expiry_date
		export_expiry = license_doc.export_expiry_date
		
		if from_date and to_date:
			show_import = False
			show_export = False
			
			if not item_type_filter or item_type_filter == "Import":
				if import_expiry:
					import_expiry_date = getdate(import_expiry)
					if from_date <= import_expiry_date <= to_date:
						show_import = True
			
			if not item_type_filter or item_type_filter == "Export":
				if export_expiry:
					export_expiry_date = getdate(export_expiry)
					if from_date <= export_expiry_date <= to_date:
						show_export = True
			
			if not show_import and not show_export:
				continue
		else:
			show_import = True
			show_export = True
		
		if (not item_type_filter or item_type_filter == "Import") and show_import:
			import_items = frappe.get_all(
				"Advance License Import",
				filters={"parent": license_name},
				fields=["item_of_import", "qty_allowed", "uom"]
			)
			
			for item in import_items:
				item_code = item.item_of_import
				
				if items_filter and item_code not in items_filter:
					continue
				
				qty_allowed = flt(item.qty_allowed)
				used_qty = _get_used_qty(license_name, item_code, "purchase")
				balance_qty = qty_allowed - used_qty
				
				item_name = frappe.db.get_value("Item", item_code, "item_name") or ""
				
				data.append({
					"license_number": license_doc.license_number,
					"status": license_doc.status,
					"import_expiry_date": import_expiry,
					"export_expiry_date": "",
					"item_type": "Import",
					"item_code": item_code,
					"item_name": item_name,
					"uom": item.uom,
					"qty_allowed": qty_allowed,
					"used_qty": used_qty,
					"balance_qty": balance_qty
				})
		
		if (not item_type_filter or item_type_filter == "Export") and show_export:
			export_items = frappe.get_all(
				"Advance License Export",
				filters={"parent": license_name},
				fields=["item_of_export", "qty_allowed", "uom"]
			)
			
			for item in export_items:
				item_code = item.item_of_export
				
				if items_filter and item_code not in items_filter:
					continue
				
				qty_allowed = flt(item.qty_allowed)
				used_qty = _get_used_qty(license_name, item_code, "sales")
				balance_qty = qty_allowed - used_qty
				
				item_name = frappe.db.get_value("Item", item_code, "item_name") or ""
				
				data.append({
					"license_number": license_doc.license_number,
					"status": license_doc.status,
					"import_expiry_date": "",
					"export_expiry_date": export_expiry,
					"item_type": "Export",
					"item_code": item_code,
					"item_name": item_name,
					"uom": item.uom,
					"qty_allowed": qty_allowed,
					"used_qty": used_qty,
					"balance_qty": balance_qty
				})
	
	return data


def _get_used_qty(license_name, item_code, invoice_type="purchase"):
	"""Get used quantity from submitted invoices."""
	if invoice_type == "sales":
		invoice_table = "tabSales Invoice"
		item_table = "tabSales Invoice Item"
		item_alias = "si_item"
		invoice_alias = "si"
	else:
		invoice_table = "tabPurchase Invoice"
		item_table = "tabPurchase Invoice Item"
		item_alias = "pi_item"
		invoice_alias = "pi"
	
	used_qty = frappe.db.sql("""
		SELECT SUM({item_alias}.qty) as used_qty
		FROM `{item_table}` {item_alias}
		INNER JOIN `{invoice_table}` {invoice_alias} ON {invoice_alias}.name = {item_alias}.parent
		WHERE {invoice_alias}.custom_advance_license = %s
		AND {item_alias}.item_code = %s
		AND {invoice_alias}.docstatus = 1
	""".format(
		item_table=item_table,
		item_alias=item_alias,
		invoice_table=invoice_table,
		invoice_alias=invoice_alias
	), (license_name, item_code), as_dict=True)
	
	return flt(used_qty[0].used_qty) if used_qty and used_qty[0].used_qty else 0

