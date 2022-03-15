from .components import *
import logging

log = logging.getLogger(__name__)


class Message(object):
    def __init__(self, raw):
        self.code = raw['code']
        self.components = dict()
        self._load_components(raw['components'])

    def _load_components(self, comp):
        for k, d in comp.items():
            self.components[k] = WIDGET_CLASSES[k](self, d)

    def get_content(self, **kwargs):
        content = {'parse_mode': tlg.ParseMode.HTML}
        for c in self.components.values():
            content.update(c.get_content(**kwargs))
        return content

    def act(self, component, **kwargs):
        try:
            actor = self.components[component]
        except KeyError:
            pass
        else:
            actor.act(message=self, **kwargs)

    def save(self):
        # TODO: Finish this saving method (problem with saving actions as their origin isn't remembered)
        return {'code': self.code,
                'components': dict((k, d.save()) for k, d in self.components.items())}
