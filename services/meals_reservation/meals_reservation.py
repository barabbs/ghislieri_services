from modules.base_service import BaseService
from . import var
from .meal import Meal, get_date_str
from modules.service_pipe import Request
from datetime import date, time, datetime, timedelta
import os
import logging

log = logging.getLogger(__name__)


class MealsReservation(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(MealsReservation, self).__init__(*args, **kwargs)
        self.meals = None
        self._load_meals()
        self.last_update = self._get_last_update() - timedelta(days=1)

    def _load_meals(self):
        self.meals = set()
        for filename in filter(lambda f: not f[-5:] == ".temp", os.listdir(var.RESERVATIONS_DIR)):
            meal = Meal()
            if meal.load_from_file(filename):
                self.meals.add(meal)

    def _get_last_update(self):
        t = date.today()
        return datetime(t.year, t.month, t.day)

    def _get_meal(self, date):
        return next(filter(lambda x: x.date == date, self.meals))

    def create_recap(self, meal):
        return meal.create_recap(self)

    def send_recap(self, meal):
        filepath = self.create_recap(meal) + ".pdf"
        metadata = var.EMAIL_METADATA.copy()
        metadata["subject"] = metadata["subject"].format(date_str=get_date_str(meal.date, False))
        self.send_request(Request('email_service', 'send_email', **metadata, text="", attachments=(filepath,)))

    # Requests

    def _request_get_active_meals(self, user_id):
        return sum((m.get_reservation(user_id) for m in sorted(self.meals)), start=tuple())

    def _request_toggle_meal(self, user_id, meal_dict):
        next(filter(lambda x: x.date == meal_dict["date"], self.meals)).toggle(user_id, meal_dict["meal"])

    def _request_create_recap(self, meal_dict):
        self.create_recap(self._get_meal(meal_dict["date"]))

    def _request_send_recap(self, meal_dict):
        self.send_recap(self._get_meal(meal_dict["date"]))

    # Runtime

    def _update(self):
        if self.last_update + timedelta(days=1) + var.TIMELIMIT < datetime.now():
            log.info("Updating...")
            self.last_update = self._get_last_update()
            try:
                self.send_recap(self._get_meal(self.last_update))
            except StopIteration:
                pass
            else:
                log.info(f"Reservarion recap for {get_date_str(self.last_update, False)} sent")
            self._load_meals()