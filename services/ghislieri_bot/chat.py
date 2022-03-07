from modules.service_pipe import Request
from . import var
from .messages.home import HomeMessage
import time
import queue
import logging

log = logging.getLogger(__name__)


class Chat(object):
    def __init__(self, user_id, last_message_id, student_infos=None):
        # TODO: Remove chat_id if equal to user_id
        self.user_id, self.last_message_id = user_id, last_message_id
        self.student_infos = student_infos if student_infos is not None else dict((k, None) for k in var.STUDENT_INFOS)
        self.message_list = list()
        self.reset_message_queue = queue.Queue()  # TODO: write with deque
        self.last_interaction = 0
        # TODO: Add user permissions

    def set_last_message_id(self, new_message_id):
        self.last_message_id = new_message_id
        return Request('student_databaser', 'set_student_last_message_id', self.user_id, self.last_message_id)

    def get_info(self, info):
        return self.student_infos[info]

    def reset_session(self):
        self.last_interaction = None
        try:
            self.message_list = [self.reset_message_queue.get(block=False), ]
            return False
        except queue.Empty:
            self.message_list = [HomeMessage(), ]
            return True

    def add_reset_message(self, message):
        self.reset_message_queue.put(message, block=True)

    def _get_message(self):
        return self.message_list[-1]

    def respond(self, response_type, value, **kwargs):
        self._refresh_last_interaction()
        answer = self._get_answer(response_type, value, **kwargs)
        if answer is not None:
            self._response_update(*answer)

    def _refresh_last_interaction(self):
        self.last_interaction = int(time.time())

    def _get_answer(self, response_type, value, **kwargs):
        last_message = self._get_message()
        return getattr(last_message, f'get_answer_{response_type}')(value, student=self, **kwargs)

    def _response_update(self, *args):
        if args[0] == 'back':
            self.message_list = self.message_list[:-args[1]]
        elif args[0] == 'home':
            self.reset_session()
        elif args[0] == 'new':
            self.message_list.append(args[1](**args[2]))

    def get_message_content(self):
        message = self._get_message()
        content = message.get_content(student=self)
        content.update({'chat_id': self.user_id, 'message_id': self.last_message_id})
        return content

    def sync(self, sync_time):
        if self._is_session_expired(sync_time):
            return self.reset_session()

    def _is_session_expired(self, sync_time):
        return self.last_interaction is not None and sync_time > self.last_interaction + var.SESSION_TIMEOUT_SECONDS

    def __str__(self):
        return f"Chat ({self.student_infos['name']} {self.student_infos['surname']}, user_id {self.user_id})"
