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


def get_action_req(service_name, r_type, data_keys, other_data=None, recv_data_key=None):
    def action(data, service, **kwargs):
        req_data = {k: data[v].format(**data) if isinstance(data[v], str) else data[v] for k, v in ((r.format(**data), t.format(**data)) for r, t in data_keys.items())}
        if other_data is not None:
            req_data.update(other_data)
        recv = service.send_request(Request(service_name, r_type, **req_data))
        if recv_data_key is not None:
            data[recv_data_key] = recv

    return action


def get_action_save(data_key, value):
    def action(data, **kwargs):
        data[data_key.format(**data)] = value

    return action


def get_action_add(data_key, increment):
    def action(data, **kwargs):
        data[data_key.format(**data)] += increment

    return action


ACTION_DECORATORS = {'NEW': get_action_new, 'BACK': get_action_back, 'HOME': get_action_home, 'REQ': get_action_req, 'SAVE': get_action_save, 'ADD': get_action_add}


# Components

class BaseComponent(object):
    def __init__(self, raw):
        self.actions = tuple(ACTION_DECORATORS[a[0]](*a[1:]) for a in raw['actions']) if 'actions' in raw else tuple()

    def get_content(self, **kwargs):
        return dict()

    def act(self, **kwargs):
        for action in self.actions:
            action(**kwargs)


class Text(BaseComponent):
    def __init__(self, raw):
        self.text = raw['text']
        super(Text, self).__init__(raw)

    def get_content(self, data, **kwargs):
        self.act(data=data, **kwargs)
        return {'text': self.text.format(**data)}


class Answer(BaseComponent):
    def __init__(self, raw):
        self.ans_data_key = raw['ans_data_key']
        super(Answer, self).__init__(raw)

    def act(self, answer, data, **kwargs):
        data[self.ans_data_key.format(**data)] = answer
        super(Answer, self).act(answer=answer, data=data, **kwargs)


# Keyboard

class Keyboard(BaseComponent):
    def __init__(self, raw):
        self.parts = list(KEYBOARD_PARTE_CLASSES[part](p_raw) for part, p_raw in raw.items())
        # super(Keyboard, self).__init__(raw)  # Removed 'actions' from KEYBOARD component as it seems not to be used

    def get_content(self, **kwargs):
        time_str = str(int(time()))
        buttons = sum((part.get_keys(time_str=time_str, **kwargs) for part in self.parts), start=list())
        return {'reply_markup': tlg.InlineKeyboardMarkup(buttons)}

    def act(self, callback, **kwargs):
        time_str, msg_code, part_flag, key_id = callback.split(var.CALLBACK_SEP)
        if kwargs['message'].code != msg_code:
            log.warning(f"wrong msg_code - callback {callback} for message {kwargs['message'].code}")
            return
        for p in self.parts:
            if p.check_flag(part_flag):
                p.act(key_id=key_id, **kwargs)
                break
        else:
            log.warning(f"wrong part_flag - callback {callback} for message {kwargs['message'].code}")
            return


# super(Keyboard, self).act(callback=callback, **kwargs)


class Key(BaseComponent):
    def __init__(self, raw):
        self.text, self.id = raw['text'], raw['id']
        self.auth = tuple(set(raw[k]) if k in raw else None for k in ('whitelist', 'blacklist'))
        self.url = raw['url'] if 'url' in raw else None
        super(Key, self).__init__(raw)

    def _check_permission(self, groups):
        w, b = self.auth
        return (w is None or len(w.intersection(groups)) > 0) and (b is None or len(b.intersection(groups)) == 0)

    def check_id(self, key_id):
        return self.id == key_id

    def _get_callback(self, time_str, message, part, **kwargs):
        return var.CALLBACK_SEP.join((time_str, message.code, part.get_flag(), self.id))

    def get_key(self, data, permissions=None, **kwargs):
        if permissions is None or self._check_permission(permissions):
            return tlg.InlineKeyboardButton(str(self.text).format(**data), callback_data=self._get_callback(**kwargs) if self.url is None else None, url=self.url)


class Buttons(BaseComponent):
    PART_FLAG = 'b'

    def __init__(self, raw):
        self.buttons = tuple(tuple(Key(b) for b in row) for row in raw)

    def get_flag(self):
        return self.PART_FLAG

    def check_flag(self, flag):
        return self.PART_FLAG == flag

    def get_keys(self, chat, **kwargs):
        return list(filter(lambda r: len(r) != 0,
                           (list(filter(lambda x: x is not None, (b.get_key(part=self, permissions=chat.groups, **kwargs) for b in row))) for row in self.buttons)))

    def act(self, key_id, **kwargs):
        for b in sum(self.buttons, tuple()):
            if b.check_id(key_id):
                b.act(**kwargs)
                break
        else:
            log.warning(f"wrong key_id - callback {kwargs['callback']} for message {kwargs['message'].code}")


class Options(Buttons, Answer):
    PART_FLAG = 'o'

    def __init__(self, raw):
        self.text, self.opt_data_key = raw['text'], raw['opt_data_key']
        self.page_data_key = raw['page_data_key'] if 'page_data_key' in raw else None
        self.page_shape = raw['page_shape'] if 'page_shape' in raw else var.DEFAULT_PAGE_SHAPE
        super(Buttons, self).__init__(raw)

    def get_keys(self, data, **kwargs):
        w, h = self.page_shape
        try:
            page = data[self.page_data_key] if self.page_data_key is not None else 0   # TODO: Add control for page range (not too big, not negative ?)
        except KeyError:
            data[self.page_data_key], page = 0, 0
        options, opt_data, keys = list(enumerate(data[self.opt_data_key.format(**data)][page * h * w:(page + 1) * h * w])), data.copy(), list()
        shaped_options = [options[i:i + w] for i in range(0, min(len(options), w * h), w)]
        for row in shaped_options:
            keys.append(list())
            for n, opt in row:
                opt_data.update(opt)
                keys[-1].append(Key({'text': self.text, 'id': str(n)}).get_key(part=self, data=opt_data, **kwargs))
        return keys

    def act(self, key_id, data, **kwargs):
        super(Buttons, self).act(answer=data[self.opt_data_key.format(**data)][int(key_id)], data=data, **kwargs)


get_raw_back_nav = lambda text='↩️ Back': ({'text': text, 'id': 'back', 'actions': [['BACK']]},)
get_raw_home_nav = lambda text='🏠 Home': ({'text': text, 'id': 'home', 'actions': [['HOME']]},)
get_raw_arrows_nav = lambda page_data_key: ({'text': '◀️', 'id': 'arrow_l', 'actions': [['ADD', page_data_key, -1]]}, {'text': '▶️', 'id': 'arrow_r', 'actions': [['ADD', page_data_key, 1]]})

NAVIGATION_RAW_GENERATORS = {'back': get_raw_back_nav, 'home': get_raw_home_nav, 'arrows': get_raw_arrows_nav}


class Navigation(Buttons):
    PART_FLAG = 'n'

    def __init__(self, raw):
        super(Navigation, self).__init__(sum((NAVIGATION_RAW_GENERATORS[n[0]](*n[1:]) for n in row), start=tuple()) for row in raw)


KEYBOARD_PARTE_CLASSES = {'options': Options, 'buttons': Buttons, 'navigation': Navigation}

COMPONENTS_CLASSES = {'TEXT': Text, 'KEYBOARD': Keyboard, 'ANSWER': Answer}
