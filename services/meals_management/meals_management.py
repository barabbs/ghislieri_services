from modules.base_service import BaseService
from modules import utility as utl
from . import var
from .reservation import Reservation, get_date_str
from modules.service_pipe import Request
import datetime as dt
import os
import logging

log = logging.getLogger(__name__)


class MealsManagement(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(MealsManagement, self).__init__(*args, **kwargs)
        self.reservations = None
        self._load_reservations()
        self.last_update = (dt.datetime.now() - var.TIMELIMIT).replace(hour=0, minute=0, second=0, microsecond=0)

    def _load_reservations(self):
        self.reservations = set()
        for filename in filter(lambda f: not f[-5:] == ".temp", os.listdir(var.RESERVATIONS_DIR)):
            res = Reservation()
            if res.load_from_file(filename):
                self.reservations.add(res)

    def _get_reservation(self, date):
        return next(filter(lambda x: x.date == date, self.reservations))

    def create_res_recap(self, res):
        return res.create_recap(self)

    def send_res_recap(self, res):
        filepath = self.create_res_recap(res) + ".pdf"
        metadata = var.EMAIL_METADATA.copy()
        metadata["subject"] = metadata["subject"].format(date_str=get_date_str(res.date, False))
        self.send_request(Request('email_service', 'send_email', **metadata, text="", attachments=(filepath,)))

    def notify_reservation(self, res):
        notif_data = var.NOTIFICATION_DATA.copy()
        for k in ("start_time", "end_time"):
            notif_data[k] = utl.get_str_from_time(res.date + notif_data[k])
        notif_data["data"] = {"reservation_day_notif": get_date_str(res.date, False)}
        self.send_request(Request('ghislieri_bot', 'add_notification', **notif_data))

    # Requests

    def _request_get_active_reservations(self, user_id):
        return sum((m.get_user_reservations(user_id) for m in sorted(self.reservations)), start=tuple())

    def _request_toggle_meal_res(self, user_id, meal_dict):
        next(filter(lambda x: x.date == meal_dict["date"], self.reservations)).toggle(user_id, meal_dict["meal"])

    def _request_get_all_res_dates(self):
        dates = list()
        for f in sorted(os.listdir(var.RESERVATIONS_DIR)):
            d = dt.datetime.strptime(f, f"Reservations_{var.DATE_FORMAT}{var.RESERVATIONS_EXT}")
            dates.append({"filename": f, "date_str": get_date_str(d)})
        return dates

    def _request_create_recap(self, date_dict):
        res = Reservation()
        res.load_from_file(date_dict["filename"])
        self.create_res_recap(res)

    def _request_send_recap(self, date_dict):
        res = Reservation()
        res.load_from_file(date_dict["filename"])
        self.send_res_recap(res)

    # Runtime

    def _update(self):
        if self.last_update + dt.timedelta(days=1) + var.TIMELIMIT < dt.datetime.now():
            log.info("Updating...")
            self.last_update += dt.timedelta(days=1)
            try:
                self.send_res_recap(self._get_reservation(self.last_update))
                log.info(f"Reservation recap for {get_date_str(self.last_update, False)} sent")
            except StopIteration:
                pass
            try:
                self.notify_reservation(self._get_reservation(self.last_update + var.NOTIFICATION_DAYS_BEFORE))
                log.info(f"Notification for {get_date_str(self.last_update + var.NOTIFICATION_DAYS_BEFORE, False)} sent")
            except StopIteration:
                pass

            self._load_reservations()
