from modules.service_pipe import Request
from modules import utility as utl
from . import var
from modules.var import DATA_DIR
from time import time
import telegram as tlg
import os, logging
from math import ceil

log = logging.getLogger(__name__)


def format_data(raw, data):
    if isinstance(raw, str):  # TODO: Use a JSONDecoder to create a different class for "data_keys"?????
        try:
            if raw[0] == var.DATA_FORMATTING_HEAD:
                return format_data(data[raw[1:].format(**data)], data)
        except IndexError:
            pass
        return raw.format(**data)
    if isinstance(raw, dict):
        return dict({format_data(k, data): format_data(v, data) for k, v in raw.items()})
    if isinstance(raw, list) or isinstance(raw, tuple):
        return tuple(format_data(i, data) for i in raw)
    return raw


# Actions

def get_action_new(new_code, condition_data_key=None, else_new_code=None):
    def action(data, chat, bot, **kwargs):
        if condition_data_key is None or data[condition_data_key]:
            chat.session.append(bot.get_message(format_data(new_code, data)))
        else:
            chat.session.append(bot.get_message(format_data(else_new_code, data)))

    return action


def get_action_back(n=1):
    def action(chat, **kwargs):
        chat.session = chat.session[:-n]

    return action


def get_action_home():
    return lambda chat, **kwargs: chat.reset_session()


def get_action_req(service_name, r_type, send_data=None, recv_data_key=None):
    if send_data is None:
        send_data = dict()

    def action(data, service, **kwargs):
        recv = service.send_request(Request(format_data(service_name, data), format_data(r_type, data), **format_data(send_data, data)))
        if recv_data_key is not None:
            data[format_data(recv_data_key, data)] = recv

    return action


def get_action_save(data_key, value):
    def action(data, **kwargs):
        data[format_data(data_key, data)] = format_data(value, data)

    return action


def get_action_page(data_keys, increment):
    def action(data, **kwargs):
        data[format_data(data_keys[0], data)] = ((data[format_data(data_keys[0], data)] + format_data(increment, data) - 1) % data[format_data(data_keys[1], data)]) + 1

    return action


ACTION_DECORATORS = {'NEW': get_action_new, 'BACK': get_action_back, 'HOME': get_action_home, 'REQ': get_action_req, 'SAVE': get_action_save, 'PAGE': get_action_page}


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
        return {'text': format_data(self.text, data)}


class Photo(BaseComponent):
    def __init__(self, raw):
        self.filepath, self.caption = raw['filepath'], raw['caption'] if 'caption' in raw else None
        super(Photo, self).__init__(raw)

    def get_content(self, data, **kwargs):
        self.act(data=data, **kwargs)
        return {'photo': {'caption': format_data(self.caption, data), 'filepath': format_data(self.filepath, data)}}


class Answer(BaseComponent):
    def __init__(self, raw):
        self.ans_data_key = raw['ans_data_key']
        super(Answer, self).__init__(raw)

    def act(self, answer, data, **kwargs):
        data[format_data(self.ans_data_key, data)] = answer
        super(Answer, self).act(answer=answer, data=data, **kwargs)


class PhotoAns(BaseComponent):
    def __init__(self, raw):
        self.photo_filepath = raw['photo_filepath']
        self.photos_paths_data_key = raw['photos_paths_data_key'] if 'photos_paths_data_key' in raw else None
        super(PhotoAns, self).__init__(raw)

    def act(self, photo, data, **kwargs):
        data.update({"date": utl.get_str_from_time(date=True)})
        path = photo.get_file().download(utl.get_unused_filepath(os.path.join(DATA_DIR, *format_data(self.photo_filepath, data))))
        if self.photos_paths_data_key is not None:
            data[format_data(self.photos_paths_data_key, data)] += (path,)
        super(PhotoAns, self).act(photo=photo, data=data, **kwargs)


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
            return tlg.InlineKeyboardButton(format_data(str(self.text), data), callback_data=self._get_callback(**kwargs) if self.url is None else None, url=format_data(self.url, data))


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
        self.page_data_keys = raw['page_data_keys'] if 'page_data_keys' in raw else None
        self.page_shape = raw['page_shape'] if 'page_shape' in raw else var.DEFAULT_PAGE_SHAPE
        super(Buttons, self).__init__(raw)

    def _get_page(self, data):
        w, h = self.page_shape
        try:
            if self.page_data_keys is not None:
                page = data[self.page_data_keys[0]]
                return w, h, page - 1
            return w, h, 0
        except KeyError:
            data[self.page_data_keys[0]] = 1
            return w, h, 0

    def get_keys(self, data, **kwargs):
        all_options = data[format_data(self.opt_data_key, data)]
        w, h, page = self._get_page(data)
        if self.page_data_keys is not None:
            data[self.page_data_keys[1]] = ceil(len(all_options) / (w * h))
        options, opt_data, keys = list(enumerate(all_options[page * h * w:(page + 1) * h * w])), data.copy(), list()
        shaped_options = [options[i:i + w] for i in range(0, min(len(options), w * h), w)]
        for row in shaped_options:
            keys.append(list())
            for n, opt in row:
                opt_data.update(opt)
                keys[-1].append(Key({'text': self.text, 'id': str(n)}).get_key(part=self, data=opt_data, **kwargs))
        return keys

    def act(self, key_id, data, **kwargs):
        w, h, page = self._get_page(data)
        super(Buttons, self).act(answer=data[format_data(self.opt_data_key, data)][page * h * w + int(key_id)], data=data, **kwargs)


get_raw_back_nav = lambda text='↩️ Back': ({'text': text, 'id': 'back', 'actions': [['BACK']]},)
get_raw_home_nav = lambda text='🏠 Home': ({'text': text, 'id': 'home', 'actions': [['HOME']]},)
get_raw_arrows_nav = lambda page_data_keys: ({'text': '◀️', 'id': 'arrow_l', 'actions': [['PAGE', page_data_keys, -1]]},
                                             {'text': f'{{{page_data_keys[0]}}}️ / {{{page_data_keys[1]}}}', 'id': 'page_counter', 'actions': [['SAVE', page_data_keys[0], 1]]},
                                             {'text': '▶️', 'id': 'arrow_r', 'actions': [['PAGE', page_data_keys, 1]]})

NAVIGATION_RAW_GENERATORS = {'back': get_raw_back_nav, 'home': get_raw_home_nav, 'arrows': get_raw_arrows_nav}


class Navigation(Buttons):
    PART_FLAG = 'n'

    def __init__(self, raw):
        super(Navigation, self).__init__(sum((NAVIGATION_RAW_GENERATORS[n[0]](*n[1:]) for n in row), start=tuple()) for row in raw)


KEYBOARD_PARTE_CLASSES = {'options': Options, 'buttons': Buttons, 'navigation': Navigation}

COMPONENTS_CLASSES = {'TEXT': Text, 'KEYBOARD': Keyboard, 'ANSWER': Answer, 'PHOTO': Photo, 'PHOTO_ANS': PhotoAns}
