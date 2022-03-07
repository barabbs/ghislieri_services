from emoji import emojize
import telegram as tlg
from . import var
from . import formatting as fmt
import logging

log = logging.getLogger(__name__)

class Message(object):
    TITLE = ""
    TEXT = ""

    def __init__(self, msg_id):
        self.msg_id = msg_id
        self.text = self.TEXT

    def _get_text(self, **kwargs):
        return self.text

    def get_content(self, **kwargs):  # TODO: Add Permissions
        content = {'text': emojize(self._get_text(**kwargs)),
                   'parse_mode': tlg.ParseMode.HTML}
        return content

    def get_answer_query(self, query, **kwargs):
        pass

    def get_answer_text(self, text, **kwargs):
        pass


def get_back_answer(n=1):
    return lambda: ('back', n)


def get_home_answer():
    return lambda: ('home',)


def get_new_message_answer(new_msg_class):  # TODO: see if it is better with message instance as argument rather than message class
    return lambda: ('new', new_msg_class, dict())


class BaseMessages(object):
    TITLE = ""
    TEXT = ""

    def __init__(self):
        self.text = self.TEXT

    def _get_text(self, **kwargs):
        return self.text

    def get_content(self, **kwargs):  # TODO: Add Permissions
        content = {'text': emojize(self._get_text(**kwargs)),
                   'parse_mode': tlg.ParseMode.HTML}
        return content

    def get_answer_query(self, query, **kwargs):
        pass

    def get_answer_text(self, text, **kwargs):
        pass

    # TODO: Add reply for file


class TextMessage(BaseMessages):
    TEXT_ANSWER = lambda: None

    def get_answer_text(self, text, **kwargs):
        return self.__class__.TEXT_ANSWER()


class QueryMessage(BaseMessages):
    BUTTONS = list()

    def __init__(self):
        super(QueryMessage, self).__init__()
        self.buttons = self.BUTTONS.copy()
        self.query_answers = dict()

    def _get_buttons(self, **kwargs):
        return self.buttons

    def _set_query_answers(self, buttons):
        self.query_answers = dict()
        for row in buttons:
            for b in row:
                self.query_answers[b[0]] = b[2]

    def get_content(self, **kwargs):
        content = super(QueryMessage, self).get_content(**kwargs)
        buttons = self._get_buttons(**kwargs)
        self._set_query_answers(buttons)
        keyboard = list(list(tlg.InlineKeyboardButton(emojize(b[1]), callback_data=b[0]) for b in row) for row in buttons)
        content['reply_markup'] = tlg.InlineKeyboardMarkup(keyboard)
        return content

    def get_answer_query(self, query, **kwargs):
        return self.query_answers[query]()


class OptionsTextMessage(TextMessage, QueryMessage):
    OPTIONS = list()

    def _get_buttons(self):
        return [[(str(i), option, None), ] for i, option in enumerate(self.OPTIONS)]

    def get_answer_query(self, query, **kwargs):
        try:
            return self.get_answer_text(self.OPTIONS[int(query)], **kwargs)
        except ValueError or IndexError:
            return super(OptionsTextMessage, self).get_answer_query(query, **kwargs)



class PushMessage(QueryMessage):
    BUTTON_TEXT = "OK"
    BUTTON_ANSWER = get_home_answer()

    def _get_buttons(self, **kwargs):
        return [[("push", self.BUTTON_TEXT, self.__class__.BUTTON_ANSWER), ], ]


class BackMessage(QueryMessage):

    def _get_buttons(self, **kwargs):
        return super(BackMessage, self)._get_buttons() + [[("back", ":right_arrow_curving_left: Back", get_back_answer()), ], ]
