import os, modules, datetime
from services.ghislieri_bot import formatting as fmt

# Directories
SERVICE_NAME = "ghislieri_bot"
# DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)

# Files
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
FILEPATH_BOT_TOKEN = os.path.join(DATA_DIR, 'ghislieri_bot_token.gbtk')

# Bot
REQUEST_CONNECTION_POOL_SIZE = 8
INITIAL_CONNECTION_RETRY_TIME = 30
STUDENT_UPDATE_SECONDS_INTERVAL = 10

# Database
DATABASE_STUDENTS_TABLE = "students"
DATABASE_PERMISSIONS_TABLE = "permissions"

# Student
STUDENT_INFOS = {'name': "nome", 'surname': "cognome", 'email': "email"}
SESSION_TIMEOUT_SECONDS = 600

# About
ABOUT_BOT = f"""{fmt.bold('Ghislieri Bot')} :robot:    -    version {modules.__version__}
{fmt.italic('Developed by Barabba')}

Source code at https://github.com/barabbs/Ghislieri_Bot
"""
