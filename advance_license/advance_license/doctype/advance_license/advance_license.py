# Copyright (c) 2024, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, cint, flt, getdate, nowdate

try:
	from erpnext.setup.utils import get_exchange_rate
except Exception:  # pragma: no cover - safe fallback if erpnext isn't installed
	get_exchange_rate = None


class AdvanceLicense(Document):
	def validate(self):
		self.validate_expiry_dates()
		self.validate_qty_allowed()
		self.set_expiry_dates()
		self.set_exchange_rates()
		self.set_local_values()

	def validate_expiry_dates(self):
		if flt(self.value_export_inr) > 0 and not self.export_expiry_date:
			frappe.throw(_("Export Expiry Date is mandatory."))
		
		if flt(self.value_import_inr) > 0 and not self.import_expiry_date:
			frappe.throw(_("Import Expiry Date is mandatory."))

	def validate_qty_allowed(self):
		if self.import_items:
			for item in self.import_items:
				if not item.qty_allowed or item.qty_allowed == 0:
					frappe.throw(
						_("Qty allowed cannot be 0 in row {0} of Import Items.").format(item.idx)
					)
		if self.export_items:
			for item in self.export_items:
				if not item.qty_allowed or item.qty_allowed == 0:
					frappe.throw(
						_("Qty allowed cannot be 0 in row {0} of Export Items.").format(item.idx)
					)

	def set_expiry_dates(self):
		if not self.current_license_date:
			return

		months = cint(self.license_expiry_months)
		target_date = self.export_expiry_date or self.import_expiry_date

		if months <= 0 and target_date:
			months = self._month_diff(target_date, self.current_license_date)
			self.license_expiry_months = months

		if months <= 0:
			return

		expiry_date = add_months(self.current_license_date, months)
		self.import_expiry_date = expiry_date
		self.export_expiry_date = expiry_date

	def _month_diff(self, end_date, start_date):
		if not (end_date and start_date):
			return 0

		ed = getdate(end_date)
		st = getdate(start_date)
		months = (ed.year - st.year) * 12 + (ed.month - st.month)
		if ed.day < st.day:
			months -= 1
		return max(months, 0)

	def set_exchange_rates(self):
		if not get_exchange_rate:
			return

		base_date = self.current_license_date or nowdate()
		from_currency = self.currency
		to_currency = self.local_currency

		if from_currency and to_currency:
			if not self.export_exchange_rate:
				self.export_exchange_rate = flt(
					get_exchange_rate(from_currency, to_currency, base_date, "for_selling")
				)
			if not self.import_exchange_rate:
				self.import_exchange_rate = flt(
					get_exchange_rate(from_currency, to_currency, base_date, "for_buying")
				)

	def set_local_values(self):
		if self.export_exchange_rate:
			self.value_export_inr = flt(self.value_export_fcy) * flt(self.export_exchange_rate)

		if self.import_exchange_rate:
			self.value_import_inr = flt(self.value_import_fcy) * flt(self.import_exchange_rate)
