from modules.base_service import BaseService
from .bot import Bot
from . import var
from datetime import datetime
import os, logging

log = logging.getLogger(__name__)


class GhislieriBot(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(GhislieriBot, self).__init__(*args, **kwargs)
        self.bot = None

    # Requests
    def _request_save_feedback(self, user_id, student_infos, text):
        time = datetime.now().strftime(var.DATETIME_FORMAT)
        header = f"name={student_infos['name']}\nsurname={student_infos['surname']}\nuser_id={user_id}\ntime={time}"
        with open(os.path.join(var.FEEDBACK_DIR, f"{user_id} - {time}.gbfb"), 'w', encoding='utf-8') as f:
            f.write(f"{header}\n\n{text}")


    def run(self):
        self.bot = Bot(self)
        super(GhislieriBot, self).run()

    def _update(self):
        self.bot.update()

    def _exit(self):
        self.bot.exit()
