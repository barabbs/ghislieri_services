from . import var
from modules.service_pipe import Request
from modules import utility as utl
import datetime as dt
import os, jinja2, pdfkit


def get_date_str(date, abbr=True):
    return f"{utl.get_weekday_name(date, abbr).upper()} {date.strftime('%d')} {utl.get_month_name(date, abbr)} {date.strftime('%Y')}"


class Reservation(object):
    def __init__(self, date=None, from_date=None):
        self.date, self.from_date = date, from_date
        self.meals_res = {m: dict() for m in var.MEALS}

    def load_from_file(self, filename):
        with open(os.path.join(var.RESERVATIONS_DIR, filename)) as file:
            raw = tuple(line.replace("\n", "") for line in file.readlines())
            self.date, self.from_date = dt.date.fromisoformat(raw[0]), dt.date.fromisoformat(raw[1])
            j = 0
            while True:
                try:
                    meal = raw[2 + 3 * j]
                except IndexError:
                    break
                self.meals_res[meal] = dict()
                for i, r in enumerate(var.POSSIBLE_RESERVATIONS):
                    try:
                        self.meals_res[meal].update({int(k): r for k in raw[3 + 3 * j + i].split(",")})
                    except ValueError:
                        pass
                j += 1
        return self.from_date <= (dt.datetime.now() - var.TIMELIMIT).date() < self.date

    def _get_user_meal_res(self, user_id, meal):
        if user_id in self.meals_res[meal]:
            return self.meals_res[meal][user_id]
        return None

    def get_user_reservations(self, user_id):
        return tuple({"meal": m, "date": self.date, "date_str": get_date_str(self.date),
                      "reservation_str": var.BUTTON_RESERVATION_INDICATOR[self._get_user_meal_res(user_id, m)]} for m in self.meals_res.keys())

    def toggle(self, user_id, meal):
        try:
            self.meals_res[meal][user_id] = not self.meals_res[meal][user_id]
        except KeyError:
            self.meals_res[meal][user_id] = var.POSSIBLE_RESERVATIONS[0]
        self.save()

    def save(self):
        filepath = os.path.join(var.RESERVATIONS_DIR, f"Reservations_{self.date.strftime(var.DATE_FORMAT)}{var.RESERVATIONS_EXT}")
        with open(filepath + ".temp", "w") as file:
            file.write("\n".join((self.date.strftime(var.DATE_FORMAT), self.from_date.strftime(var.DATE_FORMAT),)) + "\n")
            for m in var.MEALS:
                file.write(f"{m}\n")
                file.write("\n".join((",".join((str(u) for u, v in filter(lambda x: x[1] == r, self.meals_res[m].items()))) for r in var.POSSIBLE_RESERVATIONS)) + "\n")
            os.rename(filepath + ".temp", filepath)

    def create_recap(self, service):
        with open(var.RECAP_HTML_TEMPLATE) as templ_file:
            templ = jinja2.Template(templ_file.read())
        filepath = os.path.join(var.RECAPS_DIR, f"Recap_{self.date.strftime(var.DATE_FORMAT)}")
        with open(filepath + ".html", "w") as file:
            students = list(service.send_request(Request('student_databaser', 'get_chats', group="student", sort=True)))
            for s in students:
                s['meals'] = tuple(self._get_user_meal_res(s['user_id'], m) for m in var.MEALS)
                s['indic'] = tuple(var.RECAP_RESERVATION_INDICATOR[i] for i in s['meals'])
            res = list()
            totals = {m: list() for m in var.MEALS}
            for g in var.GENDERS:
                by_gender = tuple(filter(lambda s: s['student_infos']['gender'] == g, students))
                for i, m in enumerate(var.MEALS):
                    totals[m].append(sum(1 for t in filter(lambda x: x['meals'][i], by_gender)))
                n, w = len(by_gender), (len(by_gender) + 1) // 2
                res.append(tuple(by_gender[i:i + w] for i in range(0, n, w)))
            for m in var.MEALS:
                totals[m].append(sum(totals[m]))
            file.write(templ.render(date_str=get_date_str(self.date, False), reservations=res, totals=totals))
        pdfkit.from_file(filepath + '.html', filepath + '.pdf')
        return filepath

    def __lt__(self, other):
        return self.date < other.date
