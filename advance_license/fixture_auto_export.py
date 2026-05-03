# Custom Field `before_save`: export this app's fixtures after the DB transaction commits.
# Only when site `developer_mode` is 1 (see site_config.json).

import frappe
from frappe.utils import cint
from frappe.utils.fixtures import export_fixtures

APP_NAME = "advance_license"
FIXTURE_MODULE = "ADVANCE LICENSE"
_LOCAL_EXPORT_QUEUED = "_advance_license_fixture_export_queued"


def _developer_mode_on() -> bool:
	return cint(frappe.conf.get("developer_mode", 0)) == 1


def _blocked() -> bool:
	if not _developer_mode_on():
		return True
	if frappe.in_test:
		return True
	if (
		frappe.flags.in_fixtures
		or frappe.flags.in_migrate
		or frappe.flags.in_install
		or frappe.flags.in_setup_wizard
	):
		return True
	return False


def schedule_custom_field_fixture_export(doc, method=None):
	if _blocked() or doc.get("module") != FIXTURE_MODULE:
		return

	if getattr(frappe.local, _LOCAL_EXPORT_QUEUED, False):
		return

	setattr(frappe.local, _LOCAL_EXPORT_QUEUED, True)

	def clear_scheduled_flag() -> None:
		setattr(frappe.local, _LOCAL_EXPORT_QUEUED, False)

	def export_after_commit() -> None:
		clear_scheduled_flag()
		export_fixtures(app=APP_NAME)

	frappe.db.after_commit.add(export_after_commit)
	frappe.db.after_rollback.add(clear_scheduled_flag)
