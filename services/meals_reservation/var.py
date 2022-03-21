import os, datetime

# Directories
SERVICE_NAME = "meals_reservation"
# DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
RESERVATIONS_DIR = os.path.join(DATA_DIR, 'reservations')

# Files
DATETIME_FORMAT = '%Y-%m-%d'
RESERVATIONS_EXT = ".mr"

# Reservations
MEALS = ("Pranzo", "Cena")
POSSIBLE_RESERVATIONS = (True, False)

# Messages
BUTTON_DATETIME_FORMAT = '%A %d %b %Y'
BUTTON_RESERVATION_INDICATOR = {True: "🟢", False: "🔴", None: "❔"}
