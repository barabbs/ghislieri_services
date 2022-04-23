import sys, os, datetime

DEBUG = "-d" in sys.argv

# Version
VERSION = "0.2.1"

# Directories
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services")
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')
ERRORS_DIR = os.path.join(DATA_DIR, 'errors')
CHANGELOGS_DIR = os.path.join(DATA_DIR, 'changelogs')

# Files
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
FILEPATH_LOG = os.path.join(LOGS_DIR, f'ghislieri_services {datetime.datetime.now().strftime(DATETIME_FORMAT)}.log')
CHANGELOGS_FILENAME = f"changelog_{'.'.join(VERSION.split('.')[0:2])}.gscl"

# Services
SERVICE_UPDATE_INTERVAL = 0.0625
