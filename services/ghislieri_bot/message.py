from .components import *
import logging

log = logging.getLogger(__name__)


class Message(object):
    def __init__(self, raw):
        self.code = raw['code']
        self.auth = tuple(set(raw[k]) if k in raw else None for k in ('whitelist', 'blacklist'))
        self.components = dict()
        self._load_components(raw['components'])

    def _load_components(self, comp):
        for k, d in comp.items():
            self.components[k] = COMPONENTS_CLASSES[k](d)

    def check_permission(self, permissions):
        w, b = self.auth
        return (w is None or len(w.intersection(permissions)) > 0) and (b is None or len(b.intersection(permissions)) == 0)

    def get_content(self, chat, **kwargs):
        content = {'parse_mode': tlg.ParseMode.HTML}
        for c in self.components.values():
            content.update(c.get_content(chat=chat, message=self, **kwargs))
        return content

    def act(self, component, **kwargs):
        self.components[component].act(message=self, **kwargs)
