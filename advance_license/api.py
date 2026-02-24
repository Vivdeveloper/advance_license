import frappe
from frappe import _
from frappe.utils import flt


def _parse_items(items):
	"""Parse and aggregate items from input."""
	if not items:
		return [], {}
	
	items = frappe.parse_json(items) if isinstance(items, str) else items
	item_codes = list(set([item.get("item_code") for item in items if item.get("item_code")]))
	item_qty_map = {}
	for item in items:
		if item.get("item_code"):
			item_code = item.get("item_code")
			item_qty_map[item_code] = item_qty_map.get(item_code, 0) + flt(item.get("qty", 0))
	
	return item_codes, item_qty_map


def _get_license_items(license_name, item_type="import"):
	"""
	Get license items from import or export table.
	item_type: "import" or "export"
	"""
	if item_type == "export":
		table = "Advance License Export"
		item_field = "item_of_export"
	else:
		table = "Advance License Import"
		item_field = "item_of_import"
	
	items = frappe.get_all(
		table,
		filters={"parent": license_name},
		fields=[item_field, "qty_allowed"]
	)
	return {item[item_field]: flt(item.qty_allowed) for item in items}


def _get_available_qty(license_name, item_code, qty_allowed, invoice_type="purchase", exclude_doc=None):
	"""
	Calculate available qty by subtracting used qty from submitted invoices.
	invoice_type: "purchase" or "sales"
	"""
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
	
	if exclude_doc:
		used_qty = frappe.db.sql("""
			SELECT SUM({item_alias}.qty) as used_qty
			FROM `{item_table}` {item_alias}
			INNER JOIN `{invoice_table}` {invoice_alias} ON {invoice_alias}.name = {item_alias}.parent
			WHERE {invoice_alias}.custom_advance_license = %s
			AND {item_alias}.item_code = %s
			AND {invoice_alias}.docstatus = 1
			AND {invoice_alias}.name != %s
		""".format(
			item_table=item_table,
			item_alias=item_alias,
			invoice_table=invoice_table,
			invoice_alias=invoice_alias
		), (license_name, item_code, exclude_doc), as_dict=True)
	else:
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
	
	used = flt(used_qty[0].used_qty) if used_qty and used_qty[0].used_qty else 0
	return flt(qty_allowed) - used


def _get_matching_items(license_name, item_codes, item_qty_map, item_type="import", invoice_type="purchase", exclude_doc=None):
	"""Get list of items that match with sufficient qty."""
	license_items = _get_license_items(license_name, item_type)
	matching_items = []
	
	for item_code in item_codes:
		if item_code not in license_items:
			continue
		
		required_qty = item_qty_map.get(item_code, 0)
		available_qty = _get_available_qty(license_name, item_code, license_items[item_code], invoice_type, exclude_doc)
		
		if available_qty > 0:
			matching_items.append(item_code)
	
	return matching_items


def _get_available_licenses(items, item_type="import", invoice_type="purchase", exclude_doc=None):
	"""Get available licenses based on items."""
	item_codes, item_qty_map = _parse_items(items)
	
	if not item_codes:
		return []
	
	licenses = frappe.get_all(
		"Advance License",
		filters={"status": ["in", ["Active", "Hold"]]},
		fields=["name"]
	)
	
	available_licenses = []
	for license_name in licenses:
		matching_items = _get_matching_items(
			license_name.name, item_codes, item_qty_map, item_type, invoice_type, exclude_doc
		)
		if matching_items:
			available_licenses.append(license_name.name)
	
	return available_licenses


def _validate_license_qty(license_name, items, item_type="import", invoice_type="purchase", exclude_doc=None):
	"""Validate that license has sufficient qty for all items."""
	if not license_name or not items:
		return {"valid": True}
	
	item_codes, item_qty_map = _parse_items(items)
	license_items = _get_license_items(license_name, item_type)
	errors = []
	
	for item_code, required_qty in item_qty_map.items():
		if item_code not in license_items:
			errors.append(_("Item {0} not found in Advance License {1}").format(item_code, license_name))
			continue
		
		available_qty = _get_available_qty(license_name, item_code, license_items[item_code], invoice_type, exclude_doc)
		if available_qty < required_qty:
			errors.append(
				_("Insufficient qty for item {0}. Required: {1}, Available: {2}").format(
					item_code, required_qty, available_qty
				)
			)
	
	if errors:
		return {"valid": False, "errors": errors}
	
	return {"valid": True}


@frappe.whitelist()
def get_available_licenses(items, exclude_pi=None):
	"""Get available Advance Licenses for Purchase Invoice (import items)."""
	return _get_available_licenses(items, item_type="import", invoice_type="purchase", exclude_doc=exclude_pi)


@frappe.whitelist()
def get_available_licenses_for_sales(items, exclude_si=None):
	"""Get available Advance Licenses for Sales Invoice (export items)."""
	return _get_available_licenses(items, item_type="export", invoice_type="sales", exclude_doc=exclude_si)


@frappe.whitelist()
def validate_license_qty(license_name, items, exclude_pi=None):
	"""Validate Advance License qty for Purchase Invoice."""
	return _validate_license_qty(license_name, items, item_type="import", invoice_type="purchase", exclude_doc=exclude_pi)


@frappe.whitelist()
def validate_sales_invoice_license_qty(license_name, items, exclude_si=None):
	"""Validate Advance License qty for Sales Invoice."""
	return _validate_license_qty(license_name, items, item_type="export", invoice_type="sales", exclude_doc=exclude_si)


def validate_purchase_invoice_license(doc, method=None):
	"""Validate Advance License qty before save/submit for Purchase Invoice."""
	if not doc.custom_advance_license or not doc.items:
		return
	
	license_status = frappe.db.get_value("Advance License", doc.custom_advance_license, "status")
	if license_status == "Hold":
		frappe.throw(_("Cannot use Advance License {0} with status 'Hold'.").format(doc.custom_advance_license))
	
	item_qty_map = {}
	for item in doc.items:
		if item.item_code:
			item_qty_map[item.item_code] = item_qty_map.get(item.item_code, 0) + flt(item.qty)
	
	if not item_qty_map:
		return
	
	license_items = _get_license_items(doc.custom_advance_license, "import")
	
	for item_code, required_qty in item_qty_map.items():
		if item_code not in license_items:
			frappe.throw(
				_("Item {0} not found in Advance License {1}").format(item_code, doc.custom_advance_license)
			)
		
		available_qty = _get_available_qty(
			doc.custom_advance_license, item_code, license_items[item_code], "purchase", doc.name
		)
		if available_qty < required_qty:
			frappe.throw(
				_("Insufficient qty for item {0}. Required: {1}, Available: {2}").format(
					item_code, required_qty, available_qty
				)
			)


def validate_sales_invoice_license(doc, method=None):
	"""Validate Advance License qty before save/submit for Sales Invoice."""
	if not doc.custom_advance_license or not doc.items:
		return
	
	license_status = frappe.db.get_value("Advance License", doc.custom_advance_license, "status")
	if license_status == "Hold":
		frappe.throw(_("Cannot use Advance License {0} with status 'Hold'.").format(doc.custom_advance_license))
	
	item_qty_map = {}
	for item in doc.items:
		if item.item_code:
			item_qty_map[item.item_code] = item_qty_map.get(item.item_code, 0) + flt(item.qty)
	
	if not item_qty_map:
		return
	
	license_items = _get_license_items(doc.custom_advance_license, "export")
	
	for item_code, required_qty in item_qty_map.items():
		if item_code not in license_items:
			frappe.throw(
				_("Item {0} not found in Advance License {1}").format(item_code, doc.custom_advance_license)
			)
		
		available_qty = _get_available_qty(
			doc.custom_advance_license, item_code, license_items[item_code], "sales", doc.name
		)
		if available_qty < required_qty:
			frappe.throw(
				_("Insufficient qty for item {0}. Required: {1}, Available: {2}").format(
					item_code, required_qty, available_qty
				)
			)
