import os, datetime

# Directories
SERVICE_NAME = "eduroam_reporter"
# DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')

# Files
DEFAULT_REPORTS_FILE = os.path.join(DATA_DIR, 'default_reports.erdr')

# Reporter
UPDATE_SECONDS_INTERVAL = 10

# Reports
REPORTS_LIST = ("Il wi-fi non si connette",
                "Nessuna connessione ad Internet, ma al wi-fi sì")
