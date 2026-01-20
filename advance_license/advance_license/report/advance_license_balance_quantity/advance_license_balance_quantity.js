// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.query_reports["Advance License Balance Quantity"] = {
	"filters": [
		{
			"fieldname": "advance_license",
			"label": __("Advance License"),
			"fieldtype": "Link",
			"options": "Advance License",
			"get_query": function() {
				return {
					"filters": {
						"status": "Active"
					}
				};
			}
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nActive\nHold\nClosed\nCancelled",
			"default": "Active"
		},
		{
			"fieldname": "item_type",
			"label": __("Item Type"),
			"fieldtype": "Select",
			"options": "\nImport\nExport",
			"default": ""
		},
		{
			"fieldname": "items",
			"label": __("Items"),
			"fieldtype": "MultiSelectList",
			"get_data": function(txt) {
				return frappe.db.get_link_options("Item", txt);
			}
		},
		{
			"fieldname": "date_range",
			"label": __("Expiry Date Range"),
			"fieldtype": "DateRange",
		}
	]
};
