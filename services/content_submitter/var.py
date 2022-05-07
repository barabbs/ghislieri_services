import sys, os

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "content_submitter"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
EDUROAM_REPORTS_DIR = os.path.join(DATA_DIR, 'eduroam_reports')

# Files
DEFAULT_EDUROAM_REPORTS_FILE = os.path.join(DATA_DIR, 'default_eduroam_reports.erdr')

# Notifications
EDUROAM_REPORT_NOTIFICATION_DATA = {"groups": ('master',), "n_type": "content_submitter", "msg_code": "notifications.admin.new_social_submission", "notify": True, "end_time": False}


SOCIAL_SUBMISSION_NOTIFICATION_DATA = {"groups": ('master', 'socials_rep'), "n_type": "social_submission", "msg_code": "notifications.admin.new_social_submission", "notify": True}
SOCIAL_SUBMISSION_EMAIL_METADATA = {"sender": "Servizio Social Submissions",
                                    "groups": ("master", "socials_rep"),
                                    "subject": "Foto per Socials di {user[name]} {user[surname]}",
                                    "text": "Nuove foto per Socials inviate da {user[name]} {user[surname]} in data {date}\n\n---- Descrizione:\n{description}\n\nn° {n_photos} foto allegate"}
