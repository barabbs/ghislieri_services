from . import var
from modules import utility as utl
from datetime import datetime
import os

def get_date_str(date):
    return f"{utl.get_weekday_name(date, True).upper()}  {date.strftime('%d')} {utl.get_month_name(date, True)} {date.strftime('%Y')}"

class Meal(object):
    def __init__(self, meal=None, date=None, from_date=None):
        self.meal, self.date, self.from_date = meal, date, from_date
        self.users = dict()

    def load_from_file(self, filename):
        with open(os.path.join(var.RESERVATIONS_DIR, filename)) as file:
            raw = tuple(line.replace("\n", "") for line in file.readlines())
            self.meal = raw[0]
            self.date = datetime.strptime(raw[1], var.DATETIME_FORMAT)
            self.from_date = datetime.strptime(raw[2], var.DATETIME_FORMAT)
            self.users = dict()
            for i, r in enumerate(var.POSSIBLE_RESERVATIONS):
                try:
                    self.users.update({int(k): r for k in raw[3 + i].split(",")})
                except ValueError:
                    pass
        return self.from_date < datetime.now()

    def get_user_reservation(self, user_id):
        if user_id in self.users.keys():
            data = {"reservation": self.users[user_id]}
        else:
            data = {"reservation": None}
        data.update({"meal": self.meal, "date": self.date, "date_str": get_date_str(self.date), "reservation_str": var.BUTTON_RESERVATION_INDICATOR[data["reservation"]]})
        return data

    def toggle(self, user_id):
        try:
            self.users[user_id] = not self.users[user_id]
        except KeyError:
            self.users[user_id] = var.POSSIBLE_RESERVATIONS[0]
        self.save()

    def save(self):
        filepath = os.path.join(var.RESERVATIONS_DIR, f"{self.date.strftime(var.DATETIME_FORMAT)}_{self.meal}{var.RESERVATIONS_EXT}")
        with open(filepath + ".temp", "w") as file:
            file.write("\n".join((self.meal,
                                  self.date.strftime(var.DATETIME_FORMAT),
                                  self.from_date.strftime(var.DATETIME_FORMAT),) +
                                 tuple(",".join((str(u) for u, v in filter(lambda x: x[1] == r, self.users.items()))) for r in var.POSSIBLE_RESERVATIONS)) + "\n")
        os.rename(filepath + ".temp", filepath)

    def __lt__(self, other):
        return self.date < other.date or (self.date == other.date and self.meal == var.MEALS[0])
