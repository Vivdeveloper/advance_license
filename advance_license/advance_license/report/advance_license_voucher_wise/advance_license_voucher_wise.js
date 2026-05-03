// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.query_reports["Advance License Voucher Wise"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "advance_license",
			"label": __("Advance License"),
			"fieldtype": "Link",
			"options": "Advance License",
			"get_query": function() {
				const status = frappe.query_report.get_filter_value("license_status");
				if (status) {
					return {
						filters: { status: status },
					};
				}
				return {};
			},
		},
		{
			"fieldname": "license_status",
			"label": __("License Status"),
			"fieldtype": "Select",
			"options": "\nActive\nHold\nClosed\nCancelled",
			"default": ""
		},
		{
			"fieldname": "voucher_type",
			"label": __("Voucher Type"),
			"fieldtype": "Select",
			"options": "\nPurchase Invoice\nSales Invoice",
			"default": "",
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
		},
	]
};
