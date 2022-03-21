from . import var
from modules.service_pipe import Request
from modules import utility as utl
from datetime import datetime
import os, jinja2, pdfkit


def get_date_str(date, abbr=True):
    return f"{utl.get_weekday_name(date, abbr).upper()}  {date.strftime('%d')} {utl.get_month_name(date, abbr)} {date.strftime('%Y')}"


class Meal(object):
    def __init__(self, date=None, from_date=None):
        self.date, self.from_date = date, from_date
        self.reservations = {m: dict() for m in var.MEALS}

    def load_from_file(self, filename):
        with open(os.path.join(var.RESERVATIONS_DIR, filename)) as file:
            raw = tuple(line.replace("\n", "") for line in file.readlines())
            self.date = datetime.strptime(raw[0], var.DATETIME_FORMAT)
            self.from_date = datetime.strptime(raw[1], var.DATETIME_FORMAT)
            j = 0
            while True:
                try:
                    meal = raw[2 + 3 * j]
                except IndexError:
                    break
                self.reservations[meal] = dict()
                for i, r in enumerate(var.POSSIBLE_RESERVATIONS):
                    try:
                        self.reservations[meal].update({int(k): r for k in raw[3 + 3 * j + i].split(",")})
                    except ValueError:
                        pass
                j += 1
        return self.from_date < datetime.now()

    def _get_user_reservation(self, user_id, meal):
        if user_id in self.reservations[meal]:
            return self.reservations[meal][user_id]
        return None

    def get_reservation(self, user_id):
        return tuple({"meal": m, "date": self.date, "date_str": get_date_str(self.date),
                      "reservation_str": var.BUTTON_RESERVATION_INDICATOR[self._get_user_reservation(user_id, m)]} for m in self.reservations.keys())

    def toggle(self, user_id, meal):
        try:
            self.reservations[meal][user_id] = not self.reservations[meal][user_id]
        except KeyError:
            self.reservations[meal][user_id] = var.POSSIBLE_RESERVATIONS[0]
        self.save()

    def save(self):
        filepath = os.path.join(var.RESERVATIONS_DIR, f"Reservations_{self.date.strftime(var.DATETIME_FORMAT)}{var.RESERVATIONS_EXT}")
        with open(filepath + ".temp", "w") as file:
            file.write("\n".join((self.date.strftime(var.DATETIME_FORMAT), self.from_date.strftime(var.DATETIME_FORMAT),)) + "\n")
            for m in var.MEALS:
                file.write(f"{m}\n")
                file.write("\n".join((",".join((str(u) for u, v in filter(lambda x: x[1] == r, self.reservations[m].items()))) for r in var.POSSIBLE_RESERVATIONS)) + "\n")
            os.rename(filepath + ".temp", filepath)

    def create_recap(self, service):
        with open(var.RECAP_HTML_TEMPLATE) as templ_file:
            templ = jinja2.Template(templ_file.read())
        filepath = os.path.join(var.RECAPS_DIR, f"Recap_{self.date.strftime(var.DATETIME_FORMAT)}")
        with open(filepath + ".html", "w") as file:
            res = list(service.send_request(Request('student_databaser', 'get_chats')))
            for u in res:
                u['meals'] = tuple(var.RECAP_RESERVATION_INDICATOR[self._get_user_reservation(u['user_id'], m)] for m in var.MEALS)
            res = tuple(sorted(res, key=lambda x: x['student_infos']['surname']))
            n, w = len(res), (len(res) + 2) // 3
            res = tuple(res[i:i + w] for i in range(0, n, w))
            file.write(templ.render(date_str=get_date_str(self.date, False), reservations=res,
                                    total={m: sum(1 for i in filter(lambda x: x, self.reservations[m].values())) for m in self.reservations.keys()}))
        pdfkit.from_file(filepath + '.html', filepath + '.pdf')
        return filepath

    def __lt__(self, other):
        return self.date < other.date
