import sys, os

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "email_service"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
ATTACHMENT_DIR = os.path.join(DATA_DIR, "attachments")

# Credentials
GOOGLE_SCOPES = ["https://mail.google.com/"]
GOOGLE_CREDENTIALS_FILE = os.path.join(DATA_DIR, 'google_credentials.json')
GOOGLE_TOKEN_FILE = os.path.join(DATA_DIR, 'google_token.json')
GOOGLE_CREDENTIALS_NOTIFICATION_DATA = {"groups": ('master',), "n_type": "google_credentials", "msg_code": "notifications.admin.google_credentials_login", "notify": True, "enabled_time": {"hours": 12}}

# Server
SMTP_HOST, IMAP_HOST = "smtp.gmail.com", "imap.gmail.com"
