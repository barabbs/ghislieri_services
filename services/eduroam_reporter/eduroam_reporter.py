from modules.base_service import BaseService
from . import var
from datetime import datetime
import os
import logging

log = logging.getLogger(__name__)


class EduroamReporter(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(EduroamReporter, self).__init__(*args, **kwargs)
        with open(var.DEFAULT_REPORTS_FILE) as file:
            self.default_reports = file.read().split("\n")

    def _request_get_default_reports(self):
        return self.default_reports

    def _request_new_report(self, user_id, student_infos, report, place, note):
        time = datetime.now().strftime(var.DATETIME_FORMAT)
        header = f"name={student_infos['name']}\nsurname={student_infos['surname']}\nuser_id={user_id}\ntime={time}"
        with open(os.path.join(var.REPORTS_DIR, f"{user_id} - {time}.errp"), 'w', encoding='utf-8') as f:
            f.write(f"{header}\n\nPLACE:\t {place}\nREPORT:\t {report}\nNOTE:\t {note}")
