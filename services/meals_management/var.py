import sys, os
import datetime as dt

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "meals_management"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
RESERVATIONS_DIR = os.path.join(DATA_DIR, 'reservations')
RECAPS_DIR = os.path.join(DATA_DIR, 'recaps')

# Files
RECAP_HTML_TEMPLATE = os.path.join(DATA_DIR, 'recap_html_template.mrtm')
DATE_FORMAT = '%Y-%m-%d'
RESERVATIONS_EXT = ".mr"
RECAP_EXT = ".html"

# Reservations
MEALS = ("Pranzo", "Cena")
POSSIBLE_RESERVATIONS = (True, False)
TIMELIMIT = dt.timedelta(hours=7, minutes=0)

# Messages
BUTTON_RESERVATION_INDICATOR = {True: "🟢", False: "🔴", None: "❔"}
RECAP_RESERVATION_INDICATOR = {True: "X", False: "", None: ""}

# Emails
EMAIL_METADATA = {"sender": "Servizio Prenotazione Pasti",
                  "receivers": ("portineria@ghislieri.it", "alesosso@gmail.com"),
                  "subject": "Prenotazione pasti {date_str}"}
EMAIL_SENDING_TIME = "07:00:00"

# Notification
NOTIFICATION_SENDING_TIME = "19:00:00"
NOTIFICATION_DAYS_BEFORE = dt.timedelta(days=1)
NOTIFICATION_DATA = {"groups": ('student',), "n_type": "meals", "msg_code": "meals_management.reservation.reminder", "notify": True, "enabled_time": {"hours": 12}}

if DEBUG:
    EMAIL_METADATA = {"sender": "Servizio Prenotazione Pasti",
                      "receivers": ("gesu.barabba.official@gmail.com", "alesosso@gmail.com"),
                      "subject": "Prenotazione pasti {date_str}"}
