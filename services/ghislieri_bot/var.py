import os, modules, datetime

# Directories
SERVICE_NAME = "ghislieri_bot"
# DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
FEEDBACK_DIR = os.path.join(DATA_DIR, 'feedback')
MESSAGES_DIR = os.path.join(os.getcwd(), 'messages')

# Files

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
FILEPATH_BOT_TOKEN = os.path.join(DATA_DIR, 'ghislieri_bot_token.gbtk')
MESSAGE_FILE_EXT = '.gsm'

# Bot
REQUEST_CONNECTION_POOL_SIZE = 8
CONNECTION_RETRY_TIME = 30
STUDENT_UPDATE_SECONDS_INTERVAL = 5

# Student
SESSION_TIMEOUT_SECONDS = 60  # TODO: !!! CHANGE ON DEPLOYMENT !!!

