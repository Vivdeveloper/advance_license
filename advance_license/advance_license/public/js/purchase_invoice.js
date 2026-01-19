frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		_toggle_advance_license_field(frm);
		_setup_advance_license_filter(frm);
	},
	supplier(frm) {
		_toggle_advance_license_field(frm);
		if (!frm.doc.supplier) {
			frm.set_value("custom_advance_license", "");
		}
	},
	items_add(frm) {
		_filter_advance_license_debounced(frm);
	},
	items_remove(frm) {
		_filter_advance_license_debounced(frm);
	},
	custom_advance_license(frm) {
		if (frm.doc.custom_advance_license) {
			_validate_license_qty(frm, false);
		}
	},
	before_save(frm) {
		return _validate_license_qty(frm, true);
	},
	before_submit(frm) {
		return _validate_license_qty(frm, true);
	}
});

frappe.ui.form.on("Purchase Invoice Item", {
	item_code(frm, cdt, cdn) {
		frm.refresh_field("items");
		_filter_advance_license_debounced(frm);
	},
	qty(frm, cdt, cdn) {
		frm.refresh_field("items");
		_filter_advance_license_debounced(frm);
	},
	items_remove(frm, cdt, cdn) {
		_filter_advance_license_debounced(frm);
	},
	items_add(frm, cdt, cdn) {
		_filter_advance_license_debounced(frm);
	}
});

function _toggle_advance_license_field(frm) {
	if (!frm.doc.supplier) {
		frm.set_df_property("custom_advance_license", "hidden", 1);
		return;
	}

	frappe.db.get_value("Supplier", frm.doc.supplier, "custom_advance_license_applicable", function(r) {
		if (r && r.custom_advance_license_applicable === "Yes") {
			frm.set_df_property("custom_advance_license", "hidden", 0);
		} else {
			frm.set_df_property("custom_advance_license", "hidden", 1);
			if (frm.doc.custom_advance_license) {
				frm.set_value("custom_advance_license", "");
			}
		}
	});
}

function _setup_advance_license_filter(frm) {
	if (!frm._available_licenses) {
		frm._available_licenses = [];
	}
	_setup_get_query(frm);
	if (frm.doc.items && frm.doc.items.length > 0) {
		_filter_advance_license(frm);
	}
}

function _setup_get_query(frm) {
	frm.set_query("custom_advance_license", function() {
		if (!frm._available_licenses || frm._available_licenses.length === 0) {
			return {
				filters: {
					name: ""
				}
			};
		}
		return {
			filters: {
				name: ["in", frm._available_licenses]
			}
		};
	});
}

let _filter_timeout = null;

function _filter_advance_license_debounced(frm) {
	if (_filter_timeout) {
		clearTimeout(_filter_timeout);
	}
	_filter_timeout = setTimeout(function() {
		_filter_advance_license(frm);
	}, 300);
}

function _filter_advance_license(frm) {
	if (!frm._available_licenses) {
		frm._available_licenses = [];
	}

	if (!frm.doc.supplier) {
		return;
	}

	if (!frm.doc.items || frm.doc.items.length === 0) {
		frm._available_licenses = [];
		_setup_get_query(frm);
		frm.refresh_field("custom_advance_license");
		return;
	}

	const items = [];
	frm.doc.items.forEach(function(item) {
		if (item.item_code) {
			items.push({
				item_code: item.item_code,
				qty: parseFloat(item.qty) || 0
			});
		}
	});

	if (items.length === 0) {
		frm._available_licenses = [];
		_setup_get_query(frm);
		frm.refresh_field("custom_advance_license");
		return;
	}

	frappe.call({
		method: "advance_license.api.get_available_licenses",
		args: {
			items: items,
			exclude_pi: frm.doc.name || null
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				frm._available_licenses = r.message;
			} else {
				frm._available_licenses = [];
				if (frm.doc.custom_advance_license) {
					frappe.msgprint({
						message: __("No Advance License available for selected items with sufficient qty."),
						indicator: "orange",
						title: __("No License Available")
					});
					frm.set_value("custom_advance_license", "");
				}
			}
			_setup_get_query(frm);
			frm.refresh_field("custom_advance_license");
		}
	});
}

function _validate_license_qty(frm, throw_error=true) {
	if (!frm.doc.custom_advance_license || !frm.doc.items || frm.doc.items.length === 0 || !frm.doc.supplier) {
		return true;
	}

	const items = frm.doc.items.map(function(item) {
		return {
			item_code: item.item_code,
			qty: item.qty || 0
		};
	}).filter(function(item) {
		return item.item_code;
	});

	if (items.length === 0) {
		return true;
	}

	let validation_passed = true;
	let error_message = "";

	frappe.call({
		method: "advance_license.api.validate_license_qty",
		args: {
			license_name: frm.doc.custom_advance_license,
			items: items,
			exclude_pi: frm.doc.name || null
		},
		async: false,
		callback: function(r) {
			if (!r.message.valid) {
				validation_passed = false;
				error_message = r.message.errors.join("<br>");
			}
		}
	});

	if (!validation_passed && throw_error) {
		frappe.throw(error_message);
	}

	return validation_passed;
}
