from modules.base_service import BaseService
from modules.service_pipe import Request
from modules import utility as utl
from .bot import Bot, RemoveChatUpdate
from . import var
from datetime import datetime
import os, logging

log = logging.getLogger(__name__)


class GhislieriBot(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(GhislieriBot, self).__init__(*args, **kwargs)
        self.bot = None

    def _load_tasks(self):
        self.scheduler.every(var.BOT_SYNC_SECONDS_INTERVAL).seconds.do(self._task_sync_bot)
        super(GhislieriBot, self)._load_tasks()

    # Requests

    def _request_add_notification(self, users=None, groups=None, **kwargs):
        if groups is not None:
            users = sum(
                (list(c['user_id'] for c in self.send_request(Request("student_databaser", "get_chats", group=g))) for g
                 in groups), start=list() if users is None else list(users))
        self.bot.notif_center.add_notification(users=users, **kwargs)

    def _request_expire_notification(self, user_id):
        self.bot.get_chat_from_id(user_id).expire_notification()

    def _request_edit_groups(self, user_id, group, edit):
        groups = self.send_request(Request("student_databaser", "edit_groups", user_id=user_id, group=group, edit=edit))
        self.bot.get_chat_from_id(user_id).set_groups(groups)

    def _request_remove_chat(self, user_id):
        self.bot.update_queue.put(RemoveChatUpdate(user_id))

    def _request_save_feedback(self, user_id, student_infos, text):
        time = utl.get_str_from_time()
        header = f"name={student_infos['name']}\nsurname={student_infos['surname']}\nuser_id={user_id}\ntime={time}"
        with open(os.path.join(var.FEEDBACK_DIR, f"{user_id} - {time}.gbfb"), 'w', encoding='utf-8') as f:
            f.write(f"{header}\n\n{text}")

    def _request_send_message(self, **kwargs):
        return self.bot.request_send_message(**kwargs)

    def _request_send_photo(self, **kwargs):
        return self.bot.request_send_photo(**kwargs)

    # Tasks

    def _task_sync_bot(self):
        self.bot.sync()

    # Statistics

    def _get_statistics(self):
        stats = super(GhislieriBot, self)._get_statistics()
        chats = self.bot.get_chats_stats()
        stats["chats"] = f"up {chats['active']:3} | notif {chats['notif']:3} | {chats['home']:3}/{chats['block']:3}"
        return stats

    # Runtime

    def run(self):
        self.bot = Bot(self)
        super(GhislieriBot, self).run()

    def _stop(self):
        self.bot.stop()
        super(GhislieriBot, self)._stop()

    def _exit(self):
        self.bot.exit()
        super(GhislieriBot, self)._exit()


SERVICE_CLASS = GhislieriBot
