import sys, os

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "email_service"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
ATTACHMENT_DIR = os.path.join(DATA_DIR, "attachments")

# Files
CREDENTIALS_FILE = os.path.join(DATA_DIR, 'email_credentials_file.escr')

# Server
SMTP_HOST, IMAP_HOST = "smtp.gmail.com", "imap.gmail.com"
