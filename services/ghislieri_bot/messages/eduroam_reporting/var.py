import os, datetime

# Directories
SERVICE_NAME = "eduroam_reporter"
# DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
DATA_DIR = os.path.join(os.getcwd(), 'data')
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')
TEMP_REPORTS_DIR = os.path.join('/var', 'tmp', SERVICE_NAME)
LOGS_DIR = os.path.join(DATA_DIR, 'logs')
ERRORS_DIR = os.path.join(DATA_DIR, 'errors')

# Files
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
FILEPATH_LOG = os.path.join(LOGS_DIR, f'eduroam_reporter {datetime.datetime.now().strftime(DATETIME_FORMAT)}.log')
REPORTS_EXT = "edr"
TEMP_REPORTS_EXT = "temp"

# Reporter
UPDATE_SECONDS_INTERVAL = 10

# Reports
REPORTS_LIST = ("Il wi-fi non si connette",
                "Nessuna connessione ad Internet, ma al wi-fi sì")
