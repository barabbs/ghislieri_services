import os, datetime

# Directories
SERVICE_NAME = "email_service"
# DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)

# Files
CREDENTIALS_FILE = os.path.join(DATA_DIR, 'email_credentials_file.escr')

# Server
SMTP_SERVER = ("smtp.gmail.com", 587)
