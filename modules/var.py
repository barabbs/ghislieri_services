import sys, os, datetime

DEBUG = "-d" in sys.argv

# Version
VERSION = "0.5.2"
CHANGELOG_VERSION = "0.5.0"

# Directories
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services")
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data')
TMP_DIR = os.path.join('/tmp', "ghislieri_services")
LOGS_DIR = os.path.join(DATA_DIR, 'logs')
ERRORS_DIR = os.path.join(DATA_DIR, 'errors')
CHANGELOGS_DIR = os.path.join(DATA_DIR, 'changelogs')
STATISTICS_DIR = os.path.join(DATA_DIR, 'statistics')

# Files
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'
FILEPATH_LOG = os.path.join(LOGS_DIR, f'ghislieri_services {datetime.datetime.now().strftime(DATETIME_FORMAT)}.log')
CHANGELOGS_FILENAME = f"changelog_{CHANGELOG_VERSION}.gscl"
STATISTICS_EXT = ".gsst"

# Requests
MAX_LOGS_PER_PAGE = 16

# Services
SERVICE_UPDATE_INTERVAL = 0.0625
