from modules.utility import dotdict
from . import var
import time
import logging

log = logging.getLogger(__name__)


class MessageAuthorizationError(Exception):
    def __init__(self, msg_code):
        self.msg_code = msg_code
        super(MessageAuthorizationError, self).__init__(f"Authorisation error for message {msg_code}")


class Chat(object):
    def __init__(self, bot, user_id, last_message_id, student_infos, permissions):
        self.bot, self.user_id, self.last_message_id = bot, user_id, last_message_id
        self.data = dotdict({'user_id': self.user_id, 'infos': student_infos})
        self.session, self.last_interaction = list(), 0
        self.permissions = permissions

    def check_auth(self):
        msg = self._get_message()
        if not msg.check_permission(self.permissions):
            raise MessageAuthorizationError(msg.code)

    def get_info(self, info):
        return self.data['infos'][info]

    def set_last_message_id(self, new_message_id):
        self.last_message_id = new_message_id

    def _set_last_interaction(self):
        self.last_interaction = int(time.time())
        print(f"last interaction - {self.last_interaction}")

    def _get_message(self):
        return self.session[-1]

    def _get_component_args(self):
        return {'data': self.data, 'bot': self.bot, 'service': self.bot.service, 'chat': self}

    def reply(self, component, **kwargs):
        self._set_last_interaction()
        self._get_message().act(component, **self._get_component_args(), **kwargs)

    def get_message_content(self, **kwargs):
        content = {'chat_id': self.user_id, 'message_id': self.last_message_id}
        content.update(self._get_message().get_content(**self._get_component_args(), **kwargs))
        return content

    # Resetting session

    def reset_session(self, msg_code=None):
        self.data = dotdict({'user_id': self.data['user_id'], 'infos': self.data['infos']})
        self.last_interaction, notify = False, False
        if msg_code is None:
            notif = self.bot.notif_center.get_notification(self.user_id)
            if notif is not None:
                msg_code, notify = notif.msg_code, notif.notify
                self.data.update(notif.data)
                self.last_interaction = False
            else:
                msg_code, notify = var.HOME_MESSAGE_CODE, False
                self.last_interaction = True
        self.session = [self.bot.get_message(msg_code), ]
        print(f"last interaction - {self.last_interaction}")
        return notify

    # Syncing

    def sync(self, sync_time):
        if self._is_session_expired(sync_time):
            return self.reset_session()

    def _is_session_expired(self, sync_time):
        if type(self.last_interaction) == bool:
            return self.last_interaction
        return sync_time >= self.last_interaction + var.SESSION_TIMEOUT_SECONDS

    # Exiting

    def _add_pending_notification_message(self):
        if self.last_interaction == False:
            self.bot.notif_center.add_notification((self.user_id, ), "pending", self._get_message().code, False)

    def stop(self):
        self._add_pending_notification_message()

    def __str__(self):
        return f"Chat ({self.get_info('name')} {self.get_info('surname')}, user_id {self.user_id})"
