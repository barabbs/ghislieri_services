from modules.base_service import BaseService
from modules.service_pipe import Request
from modules import utility as utl
from . import var
from datetime import datetime
import os
import logging

log = logging.getLogger(__name__)


class ContentSubmitter(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(ContentSubmitter, self).__init__(*args, **kwargs)
        with open(var.DEFAULT_EDUROAM_REPORTS_FILE) as file:
            self.default_reports = file.read().split("\n")

    def _request_get_default_eduroam_reports(self):
        return tuple({'report': r} for r in self.default_reports)

    def _request_new_eduroam_report(self, user_id, student_infos, report, place, note):
        time = utl.get_str_from_time()
        header = f"name={student_infos['name']}\nsurname={student_infos['surname']}\nuser_id={user_id}\ntime={time}"
        with open(os.path.join(var.EDUROAM_REPORTS_DIR, f"{user_id} - {time}.errp"), 'w', encoding='utf-8') as f:
            f.write(f"{header}\n\nPLACE:\t {place}\nREPORT:\t {report}\nNOTE:\t {note}")
        notif_data = var.EDUROAM_REPORT_NOTIFICATION_DATA.copy()
        notif_data["data"] = {"report": {"time": time, "user": student_infos, "report": report, "place": place, "note": note}}
        self.send_request(Request('ghislieri_bot', 'add_notification', **notif_data))

    def _request_get_default_eduroam_reports(self):
        return tuple({'report': r} for r in self.default_reports)

    def _request_new_eduroam_report(self, user_id, student_infos, report, place, note):
        time = utl.get_str_from_time()
        header = f"name={student_infos['name']}\nsurname={student_infos['surname']}\nuser_id={user_id}\ntime={time}"
        with open(os.path.join(var.EDUROAM_REPORTS_DIR, f"{user_id} - {time}.errp"), 'w', encoding='utf-8') as f:
            f.write(f"{header}\n\nPLACE:\t {place}\nREPORT:\t {report}\nNOTE:\t {note}")
        notif_data = var.EDUROAM_REPORT_NOTIFICATION_DATA.copy()
        notif_data["data"] = {"report": {"time": time, "user": student_infos, "report": report, "place": place, "note": note}}
        self.send_request(Request('ghislieri_bot', 'add_notification', **notif_data))

    def _request_new_socials_submission(self, user_id, student_infos, description, photos):
        date, n_photos = utl.get_str_from_time(date=True), len(photos)
        metadata = var.SOCIAL_SUBMISSION_EMAIL_METADATA.copy()
        metadata["subject"] = metadata["subject"].format(user=student_infos)
        metadata["text"] = metadata["text"].format(user=student_infos, date=date, description=description, n_photos=n_photos)
        self.send_request(Request('email_service', 'send_email', **metadata, attachments=photos))
        notif_data = var.SOCIAL_SUBMISSION_NOTIFICATION_DATA.copy()
        notif_data["data"] = {"submission": {"date": date, "user": student_infos, "description": description, "n_photos": n_photos}}
        self.send_request(Request('ghislieri_bot', 'add_notification', **notif_data))


SERVICE_CLASS = ContentSubmitter
