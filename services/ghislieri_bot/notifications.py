from modules import utility as utl
from . import var
import datetime as dt
import json, os
import logging

log = logging.getLogger(__name__)


class NotificationCenter(object):
    # TODO: Implement notification preferences (push/no push/no notification, and eventually push but muted ['disable_notification' tag in send_message])
    def __init__(self):
        self.notifications = None
        self._load_notifications_backup()

    def _check_notifications(self):
        self.notifications = list(filter(None, self.notifications))

    def get_notification(self, user_id):
        self._check_notifications()
        for n in self.notifications:
            if n.check_user(user_id):
                return n

    def add_notification(self, **kwargs):
        self.notifications.append(Notification(**kwargs))
        log.info(f"Added notification with kwargs {kwargs}")

    def _save_notifications_backup(self):
        with open(var.NOTIFICATIONS_BCKP_FILE, 'w', encoding='UTF-8') as file:
            json.dump(list(n.to_save() for n in self.notifications), file)

    def _load_notifications_backup(self):
        try:
            with open(var.NOTIFICATIONS_BCKP_FILE, encoding='UTF-8') as file:
                self.notifications = list(Notification(**kwargs) for kwargs in json.load(file))
            os.remove(var.NOTIFICATIONS_BCKP_FILE)
        except FileNotFoundError:
            self.notifications = list()

    # Exiting

    def exit(self):
        self._save_notifications_backup()


class Notification(object):
    def __init__(self, users, n_type, msg_code, notify, data=None, start_time=None, end_time=False, **kwargs):
        # TODO: Consider removing "notify" and use only default notify status for n_type on notification preferences implementation
        self.users, self.n_type, self.msg_code, self.notify, self.data = set(users), n_type, msg_code, notify, dict() if data is None else data
        self.start_time = dt.datetime.now() if start_time is None else utl.get_time_from_str(start_time)
        self.end_time = end_time if isinstance(end_time, bool) else utl.get_time_from_str(end_time)

    def check_user(self, user_id):
        if dt.datetime.now() > self.start_time and user_id in self.users:
            self.users.remove(user_id)
            return True
        return False

    def add_user(self, user_id):
        self.users.add(user_id)

    def expired(self):
        if isinstance(self.end_time, bool):
            return self.end_time
        return dt.datetime.now() > self.end_time

    def expire(self):
        self.end_time = True

    def to_save(self):
        return {"users": list(self.users), "n_type": self.n_type, "msg_code": self.msg_code, "notify": self.notify, "data": self.data,
                "start_time": utl.get_str_from_time(self.start_time), "end_time": self.end_time if isinstance(self.end_time, bool) else utl.get_str_from_time(self.end_time)}

    def __bool__(self):
        return len(self.users) != 0 and not self.expired()

    def __str__(self):
        return f"Notification {self.to_save()}"
