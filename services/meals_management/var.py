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
MENUS_DIR = os.path.join(DATA_DIR, 'menus')

# Files
RECAP_HTML_TEMPLATE = os.path.join(DATA_DIR, 'recap_html_template.mrtm')
DATE_FORMAT = '%Y-%m-%d'
RESERVATIONS_EXT = ".mr"
RECAP_EXT = ".html"

# Reservations
MEALS = ("Pranzo", "Cena")
GENDERS = ("M", "F")
POSSIBLE_RESERVATIONS = (True, False)
TIMELIMIT = dt.timedelta(hours=7, minutes=0)

# Messages
BUTTON_RESERVATION_INDICATOR = {True: "🟢", False: "🔴", None: "❔"}
RECAP_RESERVATION_INDICATOR = {True: "X", False: "", None: ""}

# Menu
MENU_MAILBOX = "Meals/menu"
MENU_PNG_DPI = 150
MENU_PDF_FILENAME_REGEX = r"\D+(\d+)-(\d+)\D+"
MENU_FILENAME = "Menu_{date}.png"

# ----- RESERVATIONS

# Emails
RESERV_EMAIL_METADATA = {"sender": "Servizio Prenotazione Pasti",
                         "groups": ("master",),
                         "receivers": ("portineria@ghislieri.it",),
                         "subject": "Prenotazione pasti {date_str}"}
RESERV_EMAIL_SENDING_TIME = "07:00:00"

# Notification
RESERV_NOTIFICATION_SENDING_TIME = "19:00:00"
RESERV_NOTIFICATION_DAYS_BEFORE = dt.timedelta(days=1)
RESERV_NOTIFICATION_DATA = {"groups": ('student',), "n_type": "meals", "msg_code": "meals_management.reservation.reminder", "notify": True, "enabled_time": {"hours": 12}}

# ----- REPORTS

REPORT_NOTIFICATION_DATA = {"groups": ('master', 'representative'), "n_type": "meal_report", "msg_code": "notifications.admin.new_meal_report", "notify": True}
REPORT_EMAIL_METADATA = {"sender": "Servizio Segnalazioni Mensa",
                         "groups": ("master", "representative"),
                         "subject": "Segnalazione Mensa di {user[name]} {user[surname]}",
                         "text": "Nuova segnalazione mensa di {user[name]} {user[surname]} in data {date}\n\n{report}\n\nn° {n_photos} foto allegate"}

if DEBUG:
    RESERV_EMAIL_METADATA = {"sender": "Servizio Prenotazione Pasti",
                             "groups": ("master",),
                             "receivers": ("gesu.barabba.official@gmail.com",),
                             "subject": "TEST Prenotazione pasti {date_str}"}
