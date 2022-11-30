from modules.base_service import BaseService
from modules import utility as utl
from . import var
from .reservation import Reservation, get_date_str
from modules.service_pipe import Request
import datetime as dt
import os, re, pdf2image
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
        self.scheduler.every().day.at(var.RESERV_EMAIL_SENDING_TIME).do(self._task_send_res_recap)
        for t in var.RESERV_NOTIFICATION_SENDING_TIMES:
            self.scheduler.every().day.at(t).do(self._task_send_notification)
        self.scheduler.every().hour.at("00:00").do(self._task_download_menu)
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
        metadata = var.RESERV_EMAIL_METADATA.copy()
        metadata["subject"] = metadata["subject"].format(date_str=get_date_str(res.date, False))
        self.send_request(Request('email_service', 'send_email', **metadata, text="", attachments=(filepath,)))

    def _notify_reservation(self, res):
        notif_data = var.RESERV_NOTIFICATION_DATA.copy()
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

    def _request_download_menu(self):
        self._task_download_menu()

    def _request_get_todays_menu(self):
        today = dt.date.today()
        filename = os.path.join(var.MENUS_DIR, var.MENU_FILENAME.format(date=utl.get_str_from_time(today, date=True)))
        return {"exists": os.path.exists(filename), "date_str": get_date_str(today, False), "filepath": filename}

    def _request_new_report(self, user_id, student_infos, report, photos):
        date, n_photos = utl.get_str_from_time(date=True), len(photos)
        metadata = var.REPORT_EMAIL_METADATA.copy()
        metadata["subject"] = metadata["subject"].format(user=student_infos)
        metadata["text"] = metadata["text"].format(user=student_infos, date=date, report=report, n_photos=n_photos)
        self.send_request(Request('email_service', 'send_email', **metadata, attachments=photos))
        notif_data = var.REPORT_NOTIFICATION_DATA.copy()
        notif_data["data"] = {"report": {"date": date, "user": student_infos, "report": report, "n_photos": n_photos}}
        self.send_request(Request('ghislieri_bot', 'add_notification', **notif_data))

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
            self._notify_reservation(self._get_reservation(var.RESERV_NOTIFICATION_DAYS_BEFORE))
            log.info(f"Notification for today+{var.RESERV_NOTIFICATION_DAYS_BEFORE} sent")
        except StopIteration:
            pass

    def _task_download_menu(self):
        docx_files = self.send_request(Request('email_service', 'download_attachments', mailbox=var.MENU_MAILBOX))
        pdf_files = list(utl.convert_docx_to_pdf(f, timeout=15) for f in docx_files)
        img_files = ((os.path.basename(f), pdf2image.convert_from_path(f, dpi=var.MENU_PNG_DPI)[0]) for f in pdf_files)
        for name, img in img_files:
            try:
                regex = re.search(r"\D+(\d+)(.*)", name)
                day, month = int(regex.group(1)), regex.group(2)
                for n, m in enumerate(utl.MONTHS_ABBR):
                    if m in month:
                        month = month.replace(month, f" {n + 1} ")
                        break
                month = int(re.search(r"\D+(\d+).*", month).group(1))
                date = utl.get_str_from_time(dt.date(year=dt.date.today().year, month=month, day=day), date=True)
                img.save(os.path.join(var.MENUS_DIR, var.MENU_FILENAME.format(date=date)), "PNG")
                log.info(f"got new menu for {date}")
            except AttributeError:
                log.error(f"error in menu date recognition for file {name}")
        for fn in docx_files + pdf_files:
            os.remove(fn)


SERVICE_CLASS = MealsManagement
