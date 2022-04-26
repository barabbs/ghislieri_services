import sys, os

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = 'student_databaser'
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)

# Files
FILEPATH_DATABASE = os.path.join(DATA_DIR, 'database.gsdb')
FILEPATH_GROUPS_LIST = os.path.join(DATA_DIR, 'groups.gsgr')

# Database
DATABASE_STUDENTS_TABLE = "students"
STUDENT_INFOS = ('name', 'surname', 'email')
