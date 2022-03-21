import os, datetime

# Directories
DATA_DIR = os.path.join(os.getcwd(), 'data')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')
ERRORS_DIR = os.path.join(DATA_DIR, 'errors')

# Files
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
FILEPATH_LOG = os.path.join(LOGS_DIR, f'ghislieri_services {datetime.datetime.now().strftime(DATETIME_FORMAT)}.log')

#
SERVICE_UPDATE_INTERVAL =0.03125