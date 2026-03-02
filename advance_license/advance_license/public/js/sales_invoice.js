frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		_toggle_advance_license_column(frm);
		_setup_advance_license_query(frm);
		_refresh_row_licenses(frm);
	},
	customer(frm) {
		_toggle_advance_license_column(frm);
		_refresh_row_licenses(frm);
	},
	items_add(frm) {
		_filter_advance_license_debounced(frm);
	},
	items_remove(frm) {
		_filter_advance_license_debounced(frm);
	},
	before_save(frm) {
		return _validate_license_qty(frm, true);
	},
	before_submit(frm) {
		return _validate_license_qty(frm, true);
	}
});

frappe.ui.form.on("Sales Invoice Item", {
	item_code(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		row.custom_advance_license = "";
		frm.refresh_field("items");
		_filter_advance_license_debounced(frm);
	},
	qty(frm, cdt, cdn) {
		_filter_advance_license_debounced(frm);
	},
	custom_advance_license(frm, cdt, cdn) {
		_validate_license_qty(frm, false);
	}
});

function _toggle_advance_license_column(frm) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;

	frappe.db.get_value("Customer", frm.doc.customer, "custom_advance_license_applicable", function(r) {
		if (frm.doc.customer && r && r.custom_advance_license_applicable === "Yes") {
			grid.update_docfield_property("custom_advance_license", "hidden", 0);
		} else {
			grid.update_docfield_property("custom_advance_license", "hidden", 1);
			if (frm.doc.items) {
				frm.doc.items.forEach(function(row) {
					if (row.custom_advance_license) row.custom_advance_license = "";
				});
				frm.refresh_field("items");
			}
		}
	});
}

function _setup_advance_license_query(frm) {
	frm.set_query("custom_advance_license", "items", function(doc, cdt, cdn) {
		const licenses = frm._row_licenses && frm._row_licenses[cdn];
		if (!licenses || licenses.length === 0) {
			return { filters: { name: "" } };
		}
		return { filters: { name: ["in", licenses] } };
	});
}

let _filter_timeout = null;

function _filter_advance_license_debounced(frm) {
	if (_filter_timeout) clearTimeout(_filter_timeout);
	_filter_timeout = setTimeout(function() {
		_refresh_row_licenses(frm);
	}, 300);
}

function _refresh_row_licenses(frm) {
	if (!frm.doc.customer || !frm.doc.items || frm.doc.items.length === 0) {
		frm._row_licenses = {};
		return;
	}
	if (!frm._row_licenses) frm._row_licenses = {};

	const pending = [];
	frm.doc.items.forEach(function(row) {
		if (!row.item_code) return;
		const cdn = row.name || "Sales Invoice Item-" + row.idx;
		const items_arg = [{ item_code: row.item_code, qty: parseFloat(row.qty) || 0 }];
		pending.push({
			cdn: cdn,
			items: items_arg
		});
	});

	if (pending.length === 0) return;

	pending.forEach(function(p) {
		frappe.call({
			method: "advance_license.api.get_available_licenses_for_sales",
			args: {
				items: p.items,
				exclude_si: frm.doc.name || null
			},
			callback: function(r) {
				const list = (r.message && r.message.length) ? r.message : [];
				frm._row_licenses[p.cdn] = list;
				frm.refresh_field("items");
			}
		});
	});
}

function _validate_license_qty(frm, throw_error) {
	if (!frm.doc.items || frm.doc.items.length === 0 || !frm.doc.customer) {
		return true;
	}

	const by_license = {};
	frm.doc.items.forEach(function(row) {
		if (!row.item_code || !row.custom_advance_license) return;
		const lic = row.custom_advance_license;
		if (!by_license[lic]) by_license[lic] = [];
		by_license[lic].push({ item_code: row.item_code, qty: row.qty || 0 });
	});

	const licenses = Object.keys(by_license);
	if (licenses.length === 0) return true;

	let validation_passed = true;
	let error_message = "";

	licenses.forEach(function(license_name) {
		const items = by_license[license_name];
		frappe.call({
			method: "advance_license.api.validate_sales_invoice_license_qty",
			args: {
				license_name: license_name,
				items: items,
				exclude_si: frm.doc.name || null
			},
			async: false,
			callback: function(r) {
				if (r.message && !r.message.valid) {
					validation_passed = false;
					if (r.message.errors && r.message.errors.length) {
						error_message += r.message.errors.join("<br>") + "<br>";
					}
				}
			}
		});
	});

	if (!validation_passed) {
		if (throw_error) {
			frappe.show_alert({
				message: error_message.replace(/<br\s*\/?>/gi, " "),
				indicator: "orange"
			}, 5);
		}
	}
	return validation_passed;
}
