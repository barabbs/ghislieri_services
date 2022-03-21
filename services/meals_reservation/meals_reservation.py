from modules.base_service import BaseService
from . import var
from .meal import Meal
from datetime import datetime, timedelta
import os
import logging

log = logging.getLogger(__name__)


class MealsReservation(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(MealsReservation, self).__init__(*args, **kwargs)
        self.meals = set()
        self._load_meals()

    def _load_meals(self):
        for filename in filter(lambda f: not f[-5:] == ".temp", os.listdir(var.RESERVATIONS_DIR)):
            meal = Meal()
            if meal.load_from_file(filename):
                self.meals.add(meal)

    def _request_get_active_meals(self, user_id):
        return sum((m.get_reservation(user_id) for m in sorted(self.meals)), start=tuple())

    def _request_toggle_meal(self, user_id, meal_dict):
        next(filter(lambda x: x.date == meal_dict["date"], self.meals)).toggle(user_id, meal_dict["meal"])

    def _request_create_recap(self, meal_dict):
        next(filter(lambda x: x.date == meal_dict["date"], self.meals)).create_recap(self)
