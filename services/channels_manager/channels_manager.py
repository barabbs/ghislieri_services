from modules.base_service import BaseService, task
from modules.service_pipe import Request
from .facebook_scraping import get_facebook_group_posts
from . import var
from modules import utility as utl

import logging, os

log = logging.getLogger(__name__)


def _get_posts_history():
    with open(var.FACEBOOK_POSTS_FILE, 'r') as posts_file:
        return set(int(p.split(",")[0]) for p in posts_file.readlines())


def _get_channel_id():
    with open(var.CHANNEL_ID_FILE, 'r') as channel_file:
        return int(channel_file.read())


CHANNEL_ID = _get_channel_id()


class ChannelsManager(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(ChannelsManager, self).__init__(*args, **kwargs)
        self.post_history = _get_posts_history()

    def _load_tasks(self):
        self.scheduler.every(2).minutes.at(":00").do(self._task_check_facebook_posts)
        super(ChannelsManager, self)._load_tasks()

    def _send_post(self, post):
        log.info(f"New facebook post with id {post['post_id']} found")
        msgs = list()
        text = var.FACEBOOK_POST_MSG.format(**post)
        msgs.append(self.send_request(Request("ghislieri_bot", "send_message",
                                              chat_id=CHANNEL_ID, disable_web_page_preview=True, text=text)))
        if "img" in post.keys():
            msgs.append(self.send_request(Request("ghislieri_bot", "send_photo",
                                                  chat_id=CHANNEL_ID, photo=post["img"], reply_to_message_id=msgs[0])))
        self.post_history.add(post['post_id'])
        with open(var.FACEBOOK_POSTS_FILE, 'a') as posts_file:
            posts_file.write(f"{post['post_id']}," + ",".join(str(s) for s in msgs) + "\n")

    def _check_facebook_posts(self):
        for post in get_facebook_group_posts():
            if post['post_id'] not in self.post_history:
                self._send_post(post)

    # Tasks

    @task
    def _task_check_facebook_posts(self):
        self._check_facebook_posts()


SERVICE_CLASS = ChannelsManager
