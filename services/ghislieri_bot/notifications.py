from modules import utility as utl
from . import var
import datetime as dt
import json, os


class NotificationCenter(object):
    # TODO: Implement notification preferences (push/no push/no notification, and eventually push but muted ['disable_notification' tag in send_message])
    # TODO: Implement notification expiry date (e.g. so that someone doesn't have to watch meals notification after too much time)
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
    def __init__(self, users, n_type, msg_code, notify, data=None, start_time=None, end_time=None):
        self.users, self.n_type, self.msg_code, self.notify = set(users), n_type, msg_code, notify
        self.start_time = utl.get_time_from_str(start_time)
        self.end_time = None if end_time is None else utl.get_time_from_str(end_time)
        self.data = dict() if data is None else data

    def check_user(self, user_id):
        if dt.datetime.now() > self.start_time and user_id in self.users:
            self.users.remove(user_id)
            return True
        return False

    def add_user(self, user_id):
        self.users.add(user_id)

    def expired(self):
        return self.end_time is not None and dt.datetime.now() > self.end_time

    def to_save(self):
        return {"users": list(self.users), "n_type": self.n_type, "msg_code": self.msg_code, "notify": self.notify, "data": self.data,
                "start_time": utl.get_str_from_time(self.start_time), "end_time": None if self.end_time is None else utl.get_str_from_time(self.end_time)}

    def __bool__(self):
        return len(self.users) != 0 and not self.expired()
