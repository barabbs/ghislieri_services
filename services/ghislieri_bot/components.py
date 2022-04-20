from modules.service_pipe import Request
from . import var
from time import time
import telegram as tlg
import logging

log = logging.getLogger(__name__)


# Actions

def get_action_new(new_code, condition_data_key=None, else_new_node=None):
    def action(data, chat, bot, **kwargs):
        if condition_data_key is None or data[condition_data_key]:
            chat.session.append(bot.get_message(new_code.format(**data)))
        else:
            chat.session.append(bot.get_message(else_new_node.format(**data)))

    return action


def get_action_back(n=1):
    def action(chat, **kwargs):
        chat.session = chat.session[:-n]

    return action


def get_action_home():
    return lambda chat, **kwargs: chat.reset_session()


def get_action_save(data_key, value):
    def action(data, **kwargs):
        data[data_key.format(**data)] = value

    return action


def get_action_req(service_name, r_type, data_keys, other_data=None, recv_data_key=None):
    def action(data, service, **kwargs):
        req_data = {k: data[v].format(**data) if isinstance(data[v], str) else data[v] for k, v in ((r.format(**data), t.format(**data)) for r, t in data_keys.items())}
        if other_data is not None:
            req_data.update(other_data)
        recv = service.send_request(Request(service_name, r_type, **req_data))
        if recv_data_key is not None:
            data[recv_data_key] = recv

    return action


ACTION_DECORATORS = {'NEW': get_action_new, 'BACK': get_action_back, 'HOME': get_action_home, 'SAVE': get_action_save, 'REQ': get_action_req, }


# Components

class BaseComponent(object):
    def __init__(self, msg, raw):
        self.actions = tuple(ACTION_DECORATORS[a[0]](*a[1:]) for a in raw['actions'])

    def get_content(self, **kwargs):
        return dict()

    def act(self, **kwargs):
        for action in self.actions:
            action(**kwargs)


class Text(BaseComponent):
    def __init__(self, msg, raw):
        self.text = raw['text']
        super(Text, self).__init__(msg, raw)

    def get_content(self, data, **kwargs):
        self.act(data=data, **kwargs)
        return {'text': self.text.format(**data)}


class Keyboard(BaseComponent):
    def __init__(self, msg, raw):
        self.options = Options(msg, raw['options']) if 'options' in raw else None
        self.buttons = tuple(tuple(Button(msg, b) for b in row) for row in raw['buttons'])
        super(Keyboard, self).__init__(msg, raw)

    def get_content(self, message, chat, data, **kwargs):
        time_str = str(int(time()))
        buttons = self.options.get_buttons(data, time_str) if self.options is not None else []
        for row in self.buttons:
            r_butt = list()
            for b in row:
                if b.check_permission(chat.permissions):
                    r_butt.append(b.get_button(data, time_str))
            if not len(r_butt) == 0:
                buttons.append(r_butt)
        return {'reply_markup': tlg.InlineKeyboardMarkup(buttons)}

    def act(self, callback, **kwargs):
        if var.OPTIONBUTTON_CALLBACK_IDENTIFIER in callback:
            self.options.act(callback=callback, **kwargs)
        else:
            try:
                next(filter(lambda b: b.check_callback(callback), sum(self.buttons, start=()))).act(callback=callback, **kwargs)
            except StopIteration:
                log.warning(f"Callback {callback} for message {kwargs['message'].code} raised StopIteration")
        super(Keyboard, self).act(callback=callback, **kwargs)


class Button(BaseComponent):
    def __init__(self, msg, raw):
        self.text = raw['text']
        self.auth = set(raw['auth']) if 'auth' in raw else None
        self.url = raw['url'] if 'url' in raw else None
        self.callback = msg.code + var.CALLBACK_IDENTIFIER + raw['callback'] if 'callback' in raw else None
        super(Button, self).__init__(msg, raw)

    def check_permission(self, permissions):
        return self.auth is None or len(self.auth.intersection(permissions)) > 0

    def check_callback(self, callback):
        return self.callback == callback.split(var.TIME_IDENTIFIER)[-1]

    def get_button(self, data, time_str):
        callback = (time_str + var.TIME_IDENTIFIER + self.callback) if self.callback is not None else None
        return tlg.InlineKeyboardButton(str(self.text).format(**data), callback_data=callback, url=self.url)


class Answer(BaseComponent):
    def __init__(self, msg, raw):
        self.ans_data_key = raw['ans_data_key']
        super(Answer, self).__init__(msg, raw)

    def act(self, answer, data, **kwargs):
        data[self.ans_data_key.format(**data)] = answer
        super(Answer, self).act(answer=answer, data=data, **kwargs)


class Options(Answer):
    def __init__(self, msg, raw):
        self.text = raw['text']
        self.opt_data_key = raw['opt_data_key']
        self.base_callback = msg.code + var.OPTIONBUTTON_CALLBACK_IDENTIFIER
        super(Options, self).__init__(msg, raw)

    def get_buttons(self, data, time_str):
        return list([tlg.InlineKeyboardButton(self.text.format(**opt).format(**data), callback_data=time_str + var.TIME_IDENTIFIER + self.base_callback + str(n)), ] for n, opt in
                    enumerate(data[self.opt_data_key.format(**data)]))

    def act(self, callback, data, **kwargs):
        super(Options, self).act(answer=data[self.opt_data_key.format(**data)][int(callback.split(var.OPTIONBUTTON_CALLBACK_IDENTIFIER)[-1])], callback=callback, data=data, **kwargs)


COMPONENTS_CLASSES = {'TEXT': Text,
                      'KEYBOARD': Keyboard,
                      'ANSWER': Answer}
