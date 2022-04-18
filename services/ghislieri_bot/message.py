from .components import *
import logging

log = logging.getLogger(__name__)


class Message(object):
    def __init__(self, raw):
        self.code = raw['code']
        self.auth = set(raw['auth']) if 'auth' in raw else None
        self.components = dict()
        self._load_components(raw['components'])

    def _load_components(self, comp):
        for k, d in comp.items():
            self.components[k] = WIDGET_CLASSES[k](self, d)

    def check_permission(self, permissions):
        return self.auth is None or len(self.auth.intersection(permissions)) > 0

    def get_content(self, chat, **kwargs):
        content = {'parse_mode': tlg.ParseMode.HTML}
        for c in self.components.values():
            content.update(c.get_content(chat=chat, message=self, **kwargs))
        return content

    def act(self, component, **kwargs):
        try:
            actor = self.components[component]
        except KeyError:
            pass
        else:
            actor.act(message=self, **kwargs)
