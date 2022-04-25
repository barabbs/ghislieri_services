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

    def _load_tasks(self):
        self.scheduler.every().day.at(var.EMAIL_SENDING_TIME).do(self._task_send_res_recap)
        self.scheduler.every().day.at(var.NOTIFICATION_SENDING_TIME).do(self._task_send_notification)
        super(MealsManagement, self)._load_tasks()

    def _load_reservations(self):
        self.reservations = set()
        for filename in filter(lambda f: not f[-5:] == ".temp", os.listdir(var.RESERVATIONS_DIR)):
            res = Reservation()
            if res.load_from_file(filename):
                self.reservations.add(res)

    def _get_reservation(self, delta=dt.timedelta()):
        date = dt.date.today() + delta
        return next(filter(lambda x: x.date == date, self.reservations))

    def _create_res_recap(self, res):
        return res.create_recap(self)

    def _send_res_recap(self, res):
        filepath = self._create_res_recap(res) + ".pdf"
        metadata = var.EMAIL_METADATA.copy()
        metadata["subject"] = metadata["subject"].format(date_str=get_date_str(res.date, False))
        self.send_request(Request('email_service', 'send_email', **metadata, text="", attachments=(filepath,)))

    def _notify_reservation(self, res):
        notif_data = var.NOTIFICATION_DATA.copy()
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
        self._create_res_recap(res)

    def _request_send_recap(self, date_dict):
        res = Reservation()
        res.load_from_file(date_dict["filename"])
        self._send_res_recap(res)

    # Tasks

    def _task_send_res_recap(self):
        log.info("Sending Res Recap...")
        try:
            self._send_res_recap(self._get_reservation())
            log.info(f"Reservation recap for today sent")
        except StopIteration:
            pass
        self._load_reservations()

    def _task_send_notification(self):
        try:
            self._notify_reservation(self._get_reservation(var.NOTIFICATION_DAYS_BEFORE))
            log.info(f"Notification for today+{var.NOTIFICATION_DAYS_BEFORE} sent")
        except StopIteration:
            pass


SERVICE_CLASS = MealsManagement
