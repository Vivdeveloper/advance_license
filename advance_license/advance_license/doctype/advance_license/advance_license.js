function get_month_diff(end_date, start_date) {
	if (!end_date || !start_date) {
		return 0;
	}

	const start = moment(start_date);
	const end = moment(end_date);
	let months = end.diff(start, "months");

	if (end.date() < start.date()) {
		months -= 1;
	}

	return Math.max(months, 0);
}

function calculate_expiry_dates_from_months(frm) {
	if (!frm.doc.license_expiry_months) {
		return;
	}

	const months = cint(frm.doc.license_expiry_months);
	if (months <= 0) {
		return;
	}

	if (frm.doc.import_expiry_date) {
		const export_expiry = frappe.datetime.add_months(frm.doc.import_expiry_date, months);
		frm.set_value("export_expiry_date", export_expiry);
	}
}

function recalculate_months_from_expiry_dates(frm) {
	if (!frm.doc.import_expiry_date || !frm.doc.export_expiry_date) {
		return;
	}

	const months = get_month_diff(frm.doc.export_expiry_date, frm.doc.import_expiry_date);
	if (months > 0) {
		frm.set_value("license_expiry_months", months);
	}
}

function set_local_values(frm) {
	const export_rate = flt(frm.doc.export_exchange_rate);
	const import_rate = flt(frm.doc.import_exchange_rate);

	if (export_rate) {
		frm.set_value("value_export_inr", flt(frm.doc.value_export_fcy) * export_rate);
	}

	if (import_rate) {
		frm.set_value("value_import_inr", flt(frm.doc.value_import_fcy) * import_rate);
	}
}

function fetch_exchange_rates(frm) {
	if (!frm.doc.currency || !frm.doc.local_currency) {
		return;
	}

	const transaction_date = frm.doc.current_license_date || frappe.datetime.nowdate();

	frappe.call({
		method: "erpnext.setup.utils.get_exchange_rate",
		args: {
			from_currency: frm.doc.currency,
			to_currency: frm.doc.local_currency,
			transaction_date,
			args: "for_selling"
		},
		callback: (response) => {
			if (!response || !response.message) {
				return;
			}
			frm.set_value("export_exchange_rate", response.message);
		}
	});

	frappe.call({
		method: "erpnext.setup.utils.get_exchange_rate",
		args: {
			from_currency: frm.doc.currency,
			to_currency: frm.doc.local_currency,
			transaction_date,
			args: "for_buying"
		},
		callback: (response) => {
			if (!response || !response.message) {
				return;
			}
			frm.set_value("import_exchange_rate", response.message);
			set_local_values(frm);
		}
	});
}

function update_currency_labels(frm) {
	const fcy = frm.doc.currency || "";
	const local = frm.doc.local_currency || "";

	frm.set_df_property("value_export_fcy", "label", `Value of Export (${fcy || "FCY"})`);
	frm.set_df_property("value_import_fcy", "label", `Value of Import (${fcy || "FCY"})`);
	frm.set_df_property("value_export_inr", "label", `Value of Export (${local || "Local"})`);
	frm.set_df_property("value_import_inr", "label", `Value of Import (${local || "Local"})`);
}

frappe.ui.form.on("Advance License", {
	refresh(frm) {
		if (frm.doc.license_expiry_months) {
			calculate_expiry_dates_from_months(frm);
		}
		set_local_values(frm);
		update_currency_labels(frm);
	},
	current_license_date(frm) {
		if (frm.doc.license_expiry_months) {
			calculate_expiry_dates_from_months(frm);
		}
		fetch_exchange_rates(frm);
	},
	license_expiry_months(frm) {
		calculate_expiry_dates_from_months(frm);
	},
	import_expiry_date(frm) {
		if (frm.doc.import_expiry_date && frm.doc.export_expiry_date) {
			recalculate_months_from_expiry_dates(frm);
		} else if (frm.doc.import_expiry_date && frm.doc.license_expiry_months) {
			const months = cint(frm.doc.license_expiry_months);
			if (months > 0) {
				const export_expiry = frappe.datetime.add_months(frm.doc.import_expiry_date, months);
				frm.set_value("export_expiry_date", export_expiry);
			}
		}
	},
	export_expiry_date(frm) {
		if (frm.doc.import_expiry_date && frm.doc.export_expiry_date) {
			recalculate_months_from_expiry_dates(frm);
		} else if (frm.doc.export_expiry_date && frm.doc.license_expiry_months) {
			const months = cint(frm.doc.license_expiry_months);
			if (months > 0) {
				const import_expiry = frappe.datetime.subtract_months(frm.doc.export_expiry_date, months);
				frm.set_value("import_expiry_date", import_expiry);
			}
		}
	},
	currency(frm) {
		fetch_exchange_rates(frm);
		update_currency_labels(frm);
	},
	local_currency(frm) {
		fetch_exchange_rates(frm);
		update_currency_labels(frm);
	},
	export_exchange_rate(frm) {
		set_local_values(frm);
	},
	import_exchange_rate(frm) {
		set_local_values(frm);
	},
	value_export_fcy(frm) {
		set_local_values(frm);
	},
	value_import_fcy(frm) {
		set_local_values(frm);
	},
	before_save(frm) {
		if (frm.doc.import_items) {
			frm.doc.import_items.forEach(function(d) {
				if (d.qty_allowed == 0 || d.qty_allowed === null) {
					frappe.throw(__('Qty allowed cannot be 0 in row {0} of Import Items.', [d.idx]));
				}
			});
		}
		if (frm.doc.export_items) {
			frm.doc.export_items.forEach(function(d) {
				if (d.qty_allowed == 0 || d.qty_allowed === null) {
					frappe.throw(__('Qty allowed cannot be 0 in row {0} of Export Items.', [d.idx]));
				}
			});
		}
	}
});

frappe.ui.form.on("Advance License Import", {
	qty_allowed: function(frm, cdt, cdn) {
        var d = locals[cdt][cdn];
        if (d.qty_allowed == 0 || d.qty_allowed === null) {
            frappe.msgprint(__('Qty allowed cannot be 0.'));
        }
    },
    validate: function(frm) {
        frm.doc.import_items.forEach(function(d) {
            if (d.qty_allowed == 0 || d.qty_allowed === null) {
                frappe.throw(__('Qty allowed cannot be 0 in row {0}.', [d.idx]));
            }
        });
    }
});

frappe.ui.form.on("Advance License Export", {
	qty_allowed: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if (d.qty_allowed == 0 || d.qty_allowed === null) {
			frappe.msgprint(__('Qty allowed cannot be 0.'));
		}
	},
	validate: function(frm) {
		frm.doc.export_items.forEach(function(d) {
			if (d.qty_allowed == 0 || d.qty_allowed === null) {
				frappe.throw(__('Qty allowed cannot be 0 in row {0}.', [d.idx]));
			}
		});
	}
});