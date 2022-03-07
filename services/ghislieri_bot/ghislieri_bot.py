from modules.base_service import BaseService
from .bot import Bot
from . import var
import logging

log = logging.getLogger(__name__)


class GhislieriBot(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(GhislieriBot, self).__init__(*args, **kwargs)
        self.bot = None

    def run(self):
        self.bot = Bot(self)
        self.bot.run()

    def _exit(self):
        self.bot.exit()
