from . import var
import json, os


class NotificationCenter(object):
    # TODO: Implement notification preferences (sound/muted/no notification)
    # TODO: Implement notification expiry date (e.g. so that someone doesn't have to watch meals notification after too much time)
    def __init__(self):
        self.notifications = None
        self._load_notifications_backup()

    def get_notification(self, user_id):
        for n in self.notifications:
            if n.has_user(user_id):
                if n.remove_user(user_id):
                    self.notifications.remove(n)
                return n

    def add_notification(self, *args, **kwargs):
        self.notifications.append(Notification(*args, **kwargs))

    def _save_notifications_backup(self):
        with open(var.NOTIFICATIONS_BCKP_FILE, 'w', encoding='UTF-8') as file:
            json.dump(list(n.to_save() for n in self.notifications), file)

    def _load_notifications_backup(self):
        try:
            with open(var.NOTIFICATIONS_BCKP_FILE, encoding='UTF-8') as file:
                self.notifications = list(Notification(*args) for args in json.load(file))
            os.remove(var.NOTIFICATIONS_BCKP_FILE)
        except FileNotFoundError:
            self.notifications = list()

    # Exiting

    def exit(self):
        self._save_notifications_backup()


class Notification(object):
    def __init__(self, users, n_type, msg_code, notify, data):
        self.users, self.n_type, self.msg_code, self.notify = users, n_type, msg_code, notify
        self.data = dict() if data is None else data

    def has_user(self, user_id):
        return user_id in self.users

    def remove_user(self, user_id):
        self.users.remove(user_id)
        return len(self.users) == 0

    def to_save(self):
        return self.users, self.n_type, self.msg_code, self.notify, self.data
