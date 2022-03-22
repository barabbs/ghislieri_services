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

# Bot
REQUEST_CONNECTION_POOL_SIZE = 8
CONNECTION_RETRY_TIME = 10
STUDENT_UPDATE_SECONDS_INTERVAL = 5
TIME_IDENTIFIER = "#"
CALLBACK_IDENTIFIER = ":"
OPTIONBUTTON_CALLBACK_IDENTIFIER = "$"

# Messages
HOME_MESSAGE_CODE = "home"
WELCOME_MESSAGE_CODE = "welcome.welcome"
ERROR_MESSAGE_CODE = "errors.error"
AUTH_ERROR_MESSAGE_CODE = "errors.auth"
SHUTDOWN_MESSAGE_CODE = "errors.bot_shutdown"

# Student
SESSION_TIMEOUT_SECONDS = 60  # TODO: !!! CHANGE ON DEPLOYMENT !!!

