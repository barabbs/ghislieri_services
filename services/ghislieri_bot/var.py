import sys, os

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "ghislieri_bot"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
FEEDBACK_DIR = os.path.join(DATA_DIR, 'feedback')
NOTIFICATIONS_DIR = os.path.join(DATA_DIR, 'notifications')
NOTIFICATIONS_BCKP_FILE = os.path.join(NOTIFICATIONS_DIR, 'notifications_bckp.gbnb')
MESSAGES_DIR = os.path.join(os.getcwd(), 'messages')

# Files
FILEPATH_BOT_TOKEN = os.path.join(DATA_DIR, 'ghislieri_bot_token.gbtk')
if DEBUG:
    FILEPATH_BOT_TOKEN = os.path.join(DATA_DIR, 'ghislieri_bot_token_test.gbtk')

# Bot
REQUEST_CONNECTION_POOL_SIZE = 8
CONNECTION_RETRY_TIME = 10
BOT_SYNC_SECONDS_INTERVAL = 5

# Components
DATA_FORMATTING_HEAD = "$"
CALLBACK_SEP = ":"
DEFAULT_PAGE_SHAPE = (1, 100)


# Messages
HOME_MESSAGE_CODE = "home"
WELCOME_MESSAGE_CODE = "welcome.welcome"
ERROR_MESSAGE_CODE = "utility.error"
AUTH_ERROR_MESSAGE_CODE = "utility.auth"
SHUTDOWN_MESSAGE_CODE = "utility.bot_shutdown"

# Chats
SESSION_TIMEOUT_SECONDS = 5
