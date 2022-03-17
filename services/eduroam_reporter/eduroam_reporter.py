from modules.base_service import BaseService
from . import var
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