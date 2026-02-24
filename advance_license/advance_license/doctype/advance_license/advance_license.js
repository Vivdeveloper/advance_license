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

function set_license_expiry_months(frm) {
	const import_expiry = frm.doc.import_expiry_date;
	const export_expiry = frm.doc.export_expiry_date;
	if (import_expiry && export_expiry) {
		const months = moment(export_expiry).diff(moment(import_expiry), "months", true);
		frm.set_value("license_expiry_months", Math.round(Math.abs(months)));
	}
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
		set_local_values(frm);
		update_currency_labels(frm);
	},
	current_license_date(frm) {
		fetch_exchange_rates(frm);
	},
	import_expiry_date(frm) {
		set_license_expiry_months(frm);
	},
	export_expiry_date(frm) {
		set_license_expiry_months(frm);
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