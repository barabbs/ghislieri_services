import os, datetime

# Directories
SERVICE_NAME = "meals_reservation"
# DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
RESERVATIONS_DIR = os.path.join(DATA_DIR, 'reservations')
RECAPS_DIR = os.path.join(DATA_DIR, 'recaps')

# Files
RECAP_HTML_TEMPLATE = os.path.join(DATA_DIR, 'recap_html_template.mrtm')
DATETIME_FORMAT = '%Y-%m-%d'
RESERVATIONS_EXT = ".mr"
RECAP_EXT = ".html"

# Reservations
MEALS = ("Pranzo", "Cena")
POSSIBLE_RESERVATIONS = (True, False)
TIMELIMIT = datetime.timedelta(hours=18, minutes=48)

# Messages
BUTTON_DATETIME_FORMAT = '%A %d %b %Y'
BUTTON_RESERVATION_INDICATOR = {True: "🟢", False: "🔴", None: "❔"}
RECAP_RESERVATION_INDICATOR = {True: "X", False: "", None: ""}

# Emails
EMAIL_METADATA = {"sender": "Servizio Prenotazione Pasti",
                  "receivers": ("gesu.barabba.official@gmail.com", "alesosso@gmail.com"),
                  "subject": "Prenotazione pasti {date_str}"}