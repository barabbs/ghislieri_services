import sys, os

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "eduroam_reporter"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')

# Files
DEFAULT_REPORTS_FILE = os.path.join(DATA_DIR, 'default_reports.erdr')

# Notifications
NEW_REPORT_NOTIFICATION_DATA = {"groups": ('master',), "n_type": "eduroam_reporter", "msg_code": "notifications.admin.new_eduroam_report", "notify": True, "end_time": False}
