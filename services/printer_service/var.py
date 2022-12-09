import sys, os

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "printer_service"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
FILES_DIR = os.path.join(DATA_DIR, "files")

# Files
FILEPATH_PRINTER_ADDRESS = os.path.join(DATA_DIR, "printer_address.txt")

PRINT_PROCESS_TIMEOUT = 60
