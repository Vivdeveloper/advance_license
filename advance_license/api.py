import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_available_licenses(items, exclude_pi=None):
	"""
	Get available Advance Licenses based on items in Purchase Invoice.
	Shows licenses that have at least one matching item with sufficient qty available.
	"""
	if not items:
		return []

	items = frappe.parse_json(items) if isinstance(items, str) else items
	item_codes = list(set([item.get("item_code") for item in items if item.get("item_code")]))
	item_qty_map = {}
	for item in items:
		if item.get("item_code"):
			item_code = item.get("item_code")
			item_qty_map[item_code] = item_qty_map.get(item_code, 0) + flt(item.get("qty", 0))

	if not item_codes:
		return []

	license_filters = {
		"status": "Active"
	}

	licenses = frappe.get_all(
		"Advance License",
		filters=license_filters,
		fields=["name", "license_number", "status"]
	)

	available_licenses = []
	for license_name in licenses:
		matching_items = _get_matching_items(license_name.name, item_codes, item_qty_map, exclude_pi)
		if matching_items:
			available_licenses.append(license_name.name)

	return available_licenses


def _get_matching_items(license_name, item_codes, item_qty_map, exclude_pi=None):
	"""
	Get list of items that are available in this license with sufficient qty.
	Returns list of item codes that match, empty list if none match.
	"""
	import_items = frappe.get_all(
		"Advance License Import",
		filters={"parent": license_name},
		fields=["item_of_import", "qty_allowed"]
	)
	license_items = {item.item_of_import: flt(item.qty_allowed) for item in import_items}
	
	matching_items = []
	for item_code in item_codes:
		if item_code not in license_items:
			continue

		required_qty = item_qty_map.get(item_code, 0)
		available_qty = _get_available_qty(license_name, item_code, license_items[item_code], exclude_pi)

		if available_qty >= required_qty:
			matching_items.append(item_code)

	return matching_items


def _get_available_qty(license_name, item_code, qty_allowed, exclude_pi=None):
	"""Calculate available qty by subtracting used qty from submitted PIs."""
	if exclude_pi:
		used_qty = frappe.db.sql("""
			SELECT SUM(pi_item.qty) as used_qty
			FROM `tabPurchase Invoice Item` pi_item
			INNER JOIN `tabPurchase Invoice` pi ON pi.name = pi_item.parent
			WHERE pi.custom_advance_license = %s
			AND pi_item.item_code = %s
			AND pi.docstatus = 1
			AND pi.name != %s
		""", (license_name, item_code, exclude_pi), as_dict=True)
	else:
		used_qty = frappe.db.sql("""
			SELECT SUM(pi_item.qty) as used_qty
			FROM `tabPurchase Invoice Item` pi_item
			INNER JOIN `tabPurchase Invoice` pi ON pi.name = pi_item.parent
			WHERE pi.custom_advance_license = %s
			AND pi_item.item_code = %s
			AND pi.docstatus = 1
		""", (license_name, item_code), as_dict=True)

	used = flt(used_qty[0].used_qty) if used_qty and used_qty[0].used_qty else 0
	return flt(qty_allowed) - used


@frappe.whitelist()
def validate_license_qty(license_name, items, exclude_pi=None):
	"""
	Validate that license has sufficient qty for all items.
	Used before save/submit.
	"""
	if not license_name or not items:
		return {"valid": True}

	items = frappe.parse_json(items) if isinstance(items, str) else items
	item_qty_map = {}
	for item in items:
		if item.get("item_code"):
			item_code = item.get("item_code")
			item_qty_map[item_code] = item_qty_map.get(item_code, 0) + flt(item.get("qty", 0))

	import_items = frappe.get_all(
		"Advance License Import",
		filters={"parent": license_name},
		fields=["item_of_import", "qty_allowed"]
	)

	license_items = {item.item_of_import: flt(item.qty_allowed) for item in import_items}
	errors = []

	for item_code, required_qty in item_qty_map.items():
		if item_code not in license_items:
			errors.append(_("Item {0} not found in Advance License {1}").format(item_code, license_name))
			continue

		available_qty = _get_available_qty(license_name, item_code, license_items[item_code], exclude_pi)
		if available_qty < required_qty:
			errors.append(
				_("Insufficient qty for item {0}. Required: {1}, Available: {2}").format(
					item_code, required_qty, available_qty
				)
			)

	if errors:
		return {"valid": False, "errors": errors}

	return {"valid": True}


def validate_purchase_invoice_license(doc, method=None):
	"""Validate Advance License qty before save/submit."""
	if not doc.custom_advance_license or not doc.items:
		return

	item_qty_map = {}
	for item in doc.items:
		if item.item_code:
			item_qty_map[item.item_code] = item_qty_map.get(item.item_code, 0) + flt(item.qty)

	if not item_qty_map:
		return

	import_items = frappe.get_all(
		"Advance License Import",
		filters={"parent": doc.custom_advance_license},
		fields=["item_of_import", "qty_allowed"]
	)

	license_items = {item.item_of_import: flt(item.qty_allowed) for item in import_items}

	for item_code, required_qty in item_qty_map.items():
		if item_code not in license_items:
			frappe.throw(
				_("Item {0} not found in Advance License {1}").format(item_code, doc.custom_advance_license)
			)

		available_qty = _get_available_qty(doc.custom_advance_license, item_code, license_items[item_code], doc.name)
		if available_qty < required_qty:
			frappe.throw(
				_("Insufficient qty for item {0}. Required: {1}, Available: {2}").format(
					item_code, required_qty, available_qty
				)
			)
