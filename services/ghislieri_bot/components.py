from modules.service_pipe import Request
import telegram as tlg
from emoji import emojize
import logging

log = logging.getLogger(__name__)


# Actions

def get_action_new(new_code):
    return lambda data, chat, bot, **kwargs: chat.session.append(bot.get_message(new_code.format(**data)))


def get_action_back(n=1):
    def action(chat, **kwargs):
        chat.session = chat.session[:-n]

    return action


def get_action_home():
    return lambda chat, **kwargs: chat.reset_session()


def get_action_save(data_key, value):
    def action(data, **kwargs):
        data[data_key.format(**data)] = value
        # if isinstance(value, str):
        #     data[data_key.format(**data)] = value.format(**data)
        # else:
        #     data[data_key.format(**data)] = value

    return action


# TODO:  VVVV  CONSIDER REMOVING  VVVV
# def get_action_copy(data_keys):
#     def action(data, **kwargs):
#         for k in data_keys:
#             try:
#                 data[k[0].format(**data)] = data[k[1].format(**data)].copy()
#             except AttributeError:
#                 data[k[0].format(**data)] = data[k[1].format(**data)]
#
#     return action


def get_action_req(service_name, r_type, data_keys, other_data=None, recv_data_key=None):
    def action(data, service, **kwargs):
        req_data = {k: data[v].format(**data) if isinstance(data[v], str) else data[v] for k,v in ((r.format(**data), t.format(**data)) for r,t in data_keys.items())}
        if other_data is not None:
            req_data.update(other_data)
        recv = service.send_request(Request(service_name, r_type, **req_data))
        if recv_data_key is not None:
            data[recv_data_key] = recv

    return action


# ACTION_DECORATORS = {'NEW': get_action_new, 'BACK': get_action_back, 'HOME': get_action_home, 'SAVE': get_action_save, 'COPY': get_action_copy, 'REQ': get_action_req, }
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
        return {'text': emojize(self.text.format(**data))}


class ButtonsGroup(BaseComponent):
    def __init__(self, msg, raw):
        self.buttons = tuple(tuple(Button(msg, b) for b in row) for row in raw['buttons'])
        super(ButtonsGroup, self).__init__(msg, raw)

    def get_content(self, **kwargs):
        return {'reply_markup': tlg.InlineKeyboardMarkup(list(list(b.get_button(**kwargs) for b in row) for row in self.buttons))}

    def act(self, callback, **kwargs):
        try:
            next(filter(lambda b: b.callback == callback, sum(self.buttons, start=()))).act(callback=callback, **kwargs)
        except StopIteration:
            log.warning(f"Callback {callback} for message {kwargs['message'].code} raised StopIteration")
        super(ButtonsGroup, self).act(callback=callback, **kwargs)


class Button(BaseComponent):
    def __init__(self, msg, raw):
        self.text = raw['text']
        self.callback = msg.code + ':' + raw['callback']
        super(Button, self).__init__(msg, raw)

    def get_button(self, data, **kwargs):
        return tlg.InlineKeyboardButton(emojize(self.text.format(**data)), callback_data=self.callback)


class Answer(BaseComponent):
    def __init__(self, msg, raw):
        self.ans_data_key = raw['ans_data_key']
        super(Answer, self).__init__(msg, raw)

    def act(self, answer, data, **kwargs):
        answer.replace("{", "{{")
        answer.replace("}", "}}")
        data[self.ans_data_key.format(**data)] = answer
        super(Answer, self).act(answer=answer, data=data, **kwargs)


WIDGET_CLASSES = {'TEXT': Text,
                  'BUTTONS': ButtonsGroup,
                  'ANSWER': Answer}
