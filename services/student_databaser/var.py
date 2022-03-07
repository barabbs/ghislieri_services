import os

# Directories
SERVICE_NAME = 'student_databaser'
# DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)

# Files
FILEPATH_DATABASE = os.path.join(DATA_DIR, 'database.gsdb')

# Database
DATABASE_STUDENTS_TABLE = "students"
STUDENT_INFOS = ('name', 'surname', 'email')
DATABASE_PERMISSIONS_TABLE = "permissions"
