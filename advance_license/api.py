import frappe
from frappe import _
from frappe.utils import escape_html, flt


def _bold_item(item_code):
	"""Item code wrapped in bold for HTML error messages (escaped)."""
	return f"<b>{escape_html(item_code)}</b>"


def _item_row_label_html(item):
	if item.item_code:
		return _bold_item(item.item_code)
	return escape_html(_("Row {0}").format(item.idx or "?"))


def _sync_invoice_item_advance_license_qty(doc):
	"""
	If Advance License is empty: set Advance License Qty to 0.
	If Advance License is set and item qty > 0 with Advance License Qty <= 0: default to item qty.
	"""
	for item in doc.items or []:
		lic = getattr(item, "custom_advance_license", None)
		if not lic:
			item.custom_advance_license_qty = 0
			continue
		line_qty = flt(item.qty)
		adv_qty = flt(item.custom_advance_license_qty or 0)
		if line_qty > 0 and adv_qty <= 0:
			item.custom_advance_license_qty = line_qty


def _validate_advance_license_qty_vs_line(doc):
	"""Advance License Qty must be >= 0 and not greater than item line qty."""
	errors = []
	for item in doc.items or []:
		if not getattr(item, "custom_advance_license", None):
			continue
		line_qty = flt(item.qty)
		adv_qty = flt(item.custom_advance_license_qty or 0)
		ref = _item_row_label_html(item)
		if adv_qty < 0:
			errors.append(_("Advance License Qty cannot be negative for item {0}.").format(ref))
		elif adv_qty > line_qty:
			errors.append(
				_("Advance License Qty ({0}) cannot be greater than item qty ({1}) for item {2}.").format(
					adv_qty, line_qty, ref
				)
			)
	return errors


def _parse_items(items):
	"""Parse and aggregate items from input; sums custom_advance_license_qty per item_code."""
	if not items:
		return [], {}
	
	items = frappe.parse_json(items) if isinstance(items, str) else items
	item_codes = list(set([item.get("item_code") for item in items if item.get("item_code")]))
	item_qty_map = {}
	for item in items:
		if item.get("item_code"):
			item_code = item.get("item_code")
			item_qty_map[item_code] = item_qty_map.get(item_code, 0) + flt(
				item.get("custom_advance_license_qty", 0)
			)
	
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
	Calculate available qty by subtracting used qty from submitted invoices (uses item
	custom_advance_license_qty, not stock qty).
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
			SELECT SUM(COALESCE({item_alias}.custom_advance_license_qty, 0)) as used_qty
			FROM `{item_table}` {item_alias}
			INNER JOIN `{invoice_table}` {invoice_alias} ON {invoice_alias}.name = {item_alias}.parent
			WHERE {item_alias}.custom_advance_license = %s
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
			SELECT SUM(COALESCE({item_alias}.custom_advance_license_qty, 0)) as used_qty
			FROM `{item_table}` {item_alias}
			INNER JOIN `{invoice_table}` {invoice_alias} ON {invoice_alias}.name = {item_alias}.parent
			WHERE {item_alias}.custom_advance_license = %s
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
		
		if available_qty >= required_qty:
			matching_items.append(item_code)
	
	return matching_items


def _invoice_row_key(row):
	if row.get("name"):
		return str(row.get("name"))
	return "idx:%s" % row.get("idx", 0)


def _invoice_line_demand_for_license_pick(row):
	"""
	Qty that counts against a license for this row when offering / reserving balance.
	Aligned with validate sync: if Advance License Qty is unset/zero but line has qty, line qty applies.
	"""
	line_qty = flt(row.get("qty", 0))
	adv_qty = flt(row.get("custom_advance_license_qty", 0))
	return adv_qty if adv_qty > 0 else line_qty


def _available_licenses_per_invoice_rows(rows, item_type="export", invoice_type="sales", exclude_doc=None):
	"""
	For each invoice line, return licenses that still cover that line's qty after:
	- submitted usage on other invoices, and
	- other lines on this same draft/submitted doc that already selected the license for the same item.

	Lines with no custom_advance_license do not reserve against a license in this calculation.
	For the current row's required qty, use Advance License Qty if set, else item qty (same as server validate).
	"""
	if not rows:
		return {}
	rows = frappe.parse_json(rows) if isinstance(rows, str) else rows

	licenses = frappe.get_all(
		"Advance License",
		filters={"status": ["in", ["Active", "Hold"]]},
		fields=["name"],
	)
	license_names = [l.name for l in licenses]

	result = {}
	for row in rows:
		rkey = _invoice_row_key(row)
		item_code = row.get("item_code")
		if not item_code:
			result[rkey] = []
			continue

		qty_needed = _invoice_line_demand_for_license_pick(row)
		row_choices = []
		for lic_name in license_names:
			license_items = _get_license_items(lic_name, item_type)
			if item_code not in license_items:
				continue

			other_lines_same_lic = 0
			for r in rows:
				if _invoice_row_key(r) == rkey:
					continue
				lic_val = r.get("custom_advance_license")
				if r.get("item_code") == item_code and str(lic_val or "") == str(lic_name):
					if lic_val:
						line_qty = flt(r.get("qty", 0))
						o_adv = flt(r.get("custom_advance_license_qty", 0))
						other_lines_same_lic += o_adv if o_adv > 0 else line_qty

			available_db = _get_available_qty(
				lic_name, item_code, license_items[item_code], invoice_type, exclude_doc
			)
			if available_db - other_lines_same_lic >= qty_needed:
				row_choices.append(lic_name)

		current = row.get("custom_advance_license")
		if current and str(current) not in [str(x) for x in row_choices]:
			row_choices.append(current)

		result[rkey] = row_choices

	return result


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
			errors.append(
				_("Item {0} not found in Advance License {1}.").format(
					_bold_item(item_code), escape_html(license_name)
				)
			)
			continue
		
		available_qty = _get_available_qty(license_name, item_code, license_items[item_code], invoice_type, exclude_doc)
		if available_qty < required_qty:
			errors.append(
				_("Insufficient qty for item {0}. Advance License Qty required: {1}, Available: {2}.").format(
					_bold_item(item_code), required_qty, available_qty
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
def get_available_licenses_batch(items, exclude_pi=None):
	"""Per Purchase Invoice line: licenses with enough balance for that line and rest of the draft."""
	return _available_licenses_per_invoice_rows(
		items, item_type="import", invoice_type="purchase", exclude_doc=exclude_pi
	)


@frappe.whitelist()
def get_available_licenses_for_sales(items, exclude_si=None):
	"""Get available Advance Licenses for Sales Invoice (export items)."""
	return _get_available_licenses(items, item_type="export", invoice_type="sales", exclude_doc=exclude_si)


@frappe.whitelist()
def get_available_licenses_for_sales_batch(items, exclude_si=None):
	"""Per Sales Invoice line: licenses with enough balance for that line and rest of the draft."""
	return _available_licenses_per_invoice_rows(
		items, item_type="export", invoice_type="sales", exclude_doc=exclude_si
	)


@frappe.whitelist()
def validate_license_qty(license_name, items, exclude_pi=None):
	"""Validate Advance License qty for Purchase Invoice."""
	return _validate_license_qty(license_name, items, item_type="import", invoice_type="purchase", exclude_doc=exclude_pi)


@frappe.whitelist()
def validate_sales_invoice_license_qty(license_name, items, exclude_si=None):
	"""Validate Advance License qty for Sales Invoice."""
	return _validate_license_qty(license_name, items, item_type="export", invoice_type="sales", exclude_doc=exclude_si)


def validate_purchase_invoice_license(doc, method=None):
	"""Validate Advance License qty before save/submit for Purchase Invoice (item-level license)."""
	if not doc.items:
		return

	_sync_invoice_item_advance_license_qty(doc)
	errors = _validate_advance_license_qty_vs_line(doc)

	# Group by item-level custom_advance_license
	license_item_map = {}
	for item in doc.items:
		if not item.item_code or not getattr(item, "custom_advance_license", None):
			continue
		license_name = item.custom_advance_license
		if license_name not in license_item_map:
			license_item_map[license_name] = {}
		license_item_map[license_name][item.item_code] = (
			license_item_map[license_name].get(item.item_code, 0)
			+ flt(item.custom_advance_license_qty or 0)
		)

	for license_name, item_qty_map in license_item_map.items():
		license_status = frappe.db.get_value("Advance License", license_name, "status")
		if license_status == "Hold":
			errors.append(_("Advance License {0} has status 'Hold'.").format(license_name))

		license_items = _get_license_items(license_name, "import")
		for item_code, required_qty in item_qty_map.items():
			if item_code not in license_items:
				errors.append(
					_("Item {0} not found in Advance License {1}.").format(
						_bold_item(item_code), escape_html(license_name)
					)
				)
				continue
			available_qty = _get_available_qty(
				license_name, item_code, license_items[item_code], "purchase", doc.name
			)
			if available_qty < required_qty:
				errors.append(
					_("Insufficient qty for item {0}. Advance License Qty required: {1}, Available: {2}.").format(
						_bold_item(item_code), required_qty, available_qty
					)
				)

	if errors:
		frappe.throw("<br>".join(errors), title=_("Advance License Over Usage"))


def validate_sales_invoice_license(doc, method=None):
	"""Validate Advance License qty before save/submit for Sales Invoice (item-level license)."""
	if not doc.items:
		return

	_sync_invoice_item_advance_license_qty(doc)
	errors = _validate_advance_license_qty_vs_line(doc)

	# Group by item-level custom_advance_license
	license_item_map = {}
	for item in doc.items:
		if not item.item_code or not getattr(item, "custom_advance_license", None):
			continue
		license_name = item.custom_advance_license
		if license_name not in license_item_map:
			license_item_map[license_name] = {}
		license_item_map[license_name][item.item_code] = (
			license_item_map[license_name].get(item.item_code, 0)
			+ flt(item.custom_advance_license_qty or 0)
		)

	for license_name, item_qty_map in license_item_map.items():
		license_status = frappe.db.get_value("Advance License", license_name, "status")
		if license_status == "Hold":
			errors.append(_("Advance License {0} has status 'Hold'.").format(license_name))

		license_items = _get_license_items(license_name, "export")
		for item_code, required_qty in item_qty_map.items():
			if item_code not in license_items:
				errors.append(
					_("Item {0} not found in Advance License {1}.").format(
						_bold_item(item_code), escape_html(license_name)
					)
				)
				continue
			available_qty = _get_available_qty(
				license_name, item_code, license_items[item_code], "sales", doc.name
			)
			if available_qty < required_qty:
				errors.append(
					_("Insufficient qty for item {0}. Advance License Qty required: {1}, Available: {2}.").format(
						_bold_item(item_code), required_qty, available_qty
					)
				)

	if errors:
		frappe.throw("<br>".join(errors), title=_("Advance License Over Usage"))
