from modules.service_pipe import Request
from modules import utility as utl
from modules.utility import dotdict
from .chat import Chat, MessageAuthorizationError
from .message import Message
from .notifications import NotificationCenter
from . import var
import telegram as tlg
import telegram.ext, telegram.utils.request
from time import sleep, time
import logging, os, requests, json, sys

log = logging.getLogger(__name__)

# Telegram errors
TIMED_OUT_ERROR = "Timed out"
CONNECTION_LOST_ERROR = "urllib3 HTTPError HTTPSConnectionPool"

EDIT_MSG_NOT_TEXT = "There is no text in the message to edit"
EDIT_MSG_NOT_FOUND_ERROR = "Message to edit not found"
EDIT_MSG_IDENTICAL_ERROR = "Message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message"
DELETE_MSG_NOT_FOUND_ERROR = "Message to delete not found"
MESSAGE_CANT_BE_DELETED_ERROR = "Message can't be deleted for everyone"

UNDELETABLE_MESSAGE_TEXT = "Puoi <b>eliminare</b> questo <b>messaggio</b>"


class NoNetworkErrorsUpdater(logging.Filter):
    def filter(self, record):
        return CONNECTION_LOST_ERROR not in record.getMessage()


logging.getLogger("telegram.ext.updater").addFilter(NoNetworkErrorsUpdater())
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3.connectionpool").setLevel(logging.ERROR)


def get_bot_token():
    with open(var.FILEPATH_BOT_TOKEN, 'r') as token_file:
        return token_file.readline()


def wait_for_internet():
    log.info(f"Internet Connection - waiting...")
    while True:
        try:
            requests.get('https://api.telegram.org')
            break
        except requests.exceptions.ConnectionError:
            sleep(var.CONNECTION_RETRY_TIME)
    log.info("Internet Connection - connected")


class ChatSyncUpdate(tlg.Update):
    def __init__(self):
        super(ChatSyncUpdate, self).__init__(int(time()))


class RemoveChatUpdate(tlg.Update):  # TODO: Consider removing this
    def __init__(self, user_id):
        super(RemoveChatUpdate, self).__init__(user_id)


class NewUser(Exception):
    def __init__(self, chat, *args):
        self.chat = chat
        super(NewUser, self).__init__(*args)


class Bot(tlg.Bot):
    def __init__(self, service):
        """
        Bot class

        :param GhislieriBot service:
        """
        log.info(f"Bot initializing...")
        wait_for_internet()
        self.service = service
        super(Bot, self).__init__(token=get_bot_token(), request=tlg.utils.request.Request(con_pool_size=var.REQUEST_CONNECTION_POOL_SIZE))
        self.updater = tlg.ext.Updater(bot=self)
        self._load_handlers()
        self.messages = self._load_messages(var.MESSAGES_DIR)
        self.chats = self._load_chats()
        self.notif_center = NotificationCenter()
        self.update_queue = self.updater.start_polling()
        self.sync()
        log.info(f"Bot created")

    # Handlers

    def _load_handlers(self):
        dispatcher = self.updater.dispatcher
        dispatcher.add_handler(tlg.ext.TypeHandler(ChatSyncUpdate, self._chat_sync_handler))
        dispatcher.add_handler(tlg.ext.TypeHandler(RemoveChatUpdate, self._remove_chat_handler))
        dispatcher.add_handler(tlg.ext.CommandHandler('start', self._start_command_handler))
        dispatcher.add_handler(tlg.ext.CallbackQueryHandler(self._keyboard_handler))
        dispatcher.add_handler(tlg.ext.MessageHandler(tlg.ext.Filters.photo, self._photo_handler))
        dispatcher.add_handler(tlg.ext.MessageHandler(tlg.ext.Filters.text, self._answer_handler))
        dispatcher.add_handler(tlg.ext.MessageHandler(tlg.ext.Filters.all, self._delete_handler))
        dispatcher.add_error_handler(self._error_handler)
        # TODO: Add Files Handler
        # TODO: Add StringCommandHandler to handle commands sent on the telegram chat

    def _error_handler(self, update, context):
        err = context.error
        if TIMED_OUT_ERROR in getattr(err, "message", ""):
            log.warning(f"Connection timed out!")
            wait_for_internet()
            return
        if CONNECTION_LOST_ERROR in getattr(err, "message", ""):
            log.warning(f"Connection lost!")
            return
        try:
            chat = self.get_chat_from_id(update.effective_user.id)
        except (StopIteration, AttributeError):
            chat = None

        log.error(f"Exception while handling an update: {err}")
        utl.log_error(err, chat=chat)

    def _chat_sync_handler(self, update, context):
        # TODO:  Implement message refreshing every sometime as messages older than two days can't be deleted (PROBLEM: messages can't be sent without push notification, but only without wound)
        for chat in self.chats.copy():
            update_notify = chat.sync(update.update_id)
            if update_notify is not None:
                self._dispatch_message(chat, edit=not update_notify)

    def _remove_chat_handler(self, update, context):
        self._remove_chat(self.get_chat_from_id(update.update_id))

    def _start_command_handler(self, update, context):
        try:
            chat = self._get_chat_from_update(update)
            chat.reset_session()
        except NewUser as user:
            chat = user.chat
        chat.add_msg_to_delete(update.message.message_id)
        self._dispatch_message(chat, edit=False)

    def _keyboard_handler(self, update, context):
        try:
            chat = self._get_chat_from_update(update)
            chat.reply('KEYBOARD', callback=update.callback_query.data)
        except NewUser as user:
            chat = user.chat
        self._dispatch_message(chat)

    def _answer_handler(self, update, context):
        try:
            chat = self._get_chat_from_update(update)
            answer = update.message.text_html  # TODO: Do better sanification of answer
            chat.reply('ANSWER', answer=answer)
        except NewUser as user:
            chat = user.chat
        chat.add_msg_to_delete(update.message.message_id)
        self._dispatch_message(chat)

    def _photo_handler(self, update, context):
        try:
            chat = self._get_chat_from_update(update)
            chat.reply('PHOTO_ANS', photo=update.message.photo[-1])
        except NewUser as user:
            chat = user.chat
        chat.add_msg_to_delete(update.message.message_id)
        self._dispatch_message(chat)

    def _delete_handler(self, update, context):
        try:
            chat = self._get_chat_from_update(update)
        except NewUser as user:
            chat = user.chat
        chat.add_msg_to_delete(update.message.message_id)
        self._dispatch_message(chat)

    # Messages

    def _load_messages(self, path):
        messages = dotdict()
        for filename in os.listdir(path):
            filepath = os.path.join(path, filename)
            if os.path.isdir(os.path.join(path, filename)):
                messages[filename] = self._load_messages(filepath)
            else:
                with open(filepath, encoding='UTF-8') as file:
                    try:
                        messages[filename.split('.')[0]] = Message(json.load(file))
                    except json.decoder.JSONDecodeError as err:
                        log.error(f"JSON error {err} in file {filepath}")
                        utl.log_error(err)
        return messages

    def get_message(self, code):
        return self.messages[code]

    # Chats

    def _load_chats(self):
        return set(Chat(self, **s) for s in self.service.send_request(Request('student_databaser', 'get_chats')))

    def _get_chat_from_update(self, update):
        try:
            return self.get_chat_from_id(update.effective_user.id)
        except StopIteration:
            return self._new_student_signup(update)

    def get_chat_from_id(self, user_id):
        return next(filter(lambda c: c.user_id == user_id, self.chats))

    def _new_student_signup(self, update):
        user_id = update.effective_user.id
        log.info(f"Found new student with user_id {user_id}")
        new_msg_id = self.send_message(chat_id=user_id, text="Starting...")
        chat = Chat(self, **self.service.send_request(Request('student_databaser', 'new_chat', user_id, new_msg_id.message_id)))
        self.chats.add(chat)
        chat.reset_session(var.WELCOME_MESSAGE_CODE)
        raise NewUser(chat)

    def expire_notification(self, user_id):
        self.get_chat_from_id(user_id).expire_notification()

    def get_chats_stats(self):
        stats = {"active": 0, "home": 0, "block": 0, "notif": 0}
        for c in self.chats:
            last_int = c.last_interaction
            if isinstance(last_int, bool):
                stats["home" if last_int else "block"] += 1
            elif isinstance(last_int, int):
                stats["active"] += 1
            else:
                stats["notif"] += 1
        return stats

    def _remove_chat(self, chat, delete=True):
        if delete:
            self.delete_message(chat_id=chat.user_id, message_id=chat.last_message_id)
        self.chats.remove(chat)
        log.info(f"Removed student with user_id {chat.user_id}")

    # Sending & Editing

    def _dispatch_message(self, chat, edit=True):
        try:
            message_content = chat.get_message_content()
        except MessageAuthorizationError as err:
            log.error(f"User {chat} hasn't got the auth to access msg {err.msg_code}")
            utl.log_error(err, chat=chat, msg_code=err.msg_code)
            message_content = err.msg_content
        try:
            next_msg_to_del = list()
            photo = self._send_photo(chat, message_content, next_msg_to_del)
            if edit and not photo:
                self._edit_message(chat, message_content)
            else:
                self._send_message(chat, message_content)
            self._delete_message(chat)
            chat.set_msg_to_delete(next_msg_to_del)
        except telegram.error.Unauthorized as err:
            log.warning(f"Got Unauthorized error [{getattr(err, 'message', '')}] for user {chat}, removing...")
            self._remove_chat(chat, delete=False)

    def _delete_message(self, chat):
        for m in chat.msg_to_delete:
            try:
                self.delete_message(chat_id=chat.user_id, message_id=m)
            except telegram.error.BadRequest as err:
                if err.message == DELETE_MSG_NOT_FOUND_ERROR:
                    log.warning(f"{chat} - {err.message}")
                elif err.message == MESSAGE_CANT_BE_DELETED_ERROR:
                    log.warning(f"{chat} - {err.message}")
                    try:
                        self.edit_message_text(chat_id=chat.user_id, message_id=m, text=UNDELETABLE_MESSAGE_TEXT, parse_mode=tlg.ParseMode.HTML)
                    except telegram.error.BadRequest:
                        pass
                else:
                    log.error(f"Exception while deleting a message: {err}")
                    utl.log_error(err, chat=chat)

    def _send_photo(self, chat, message_content, next_msg_to_del):
        photo_content = message_content.pop('photo', None)
        if photo_content is not None:
            with open(photo_content.pop("filepath"), "rb") as f:
                photo_msg = self.send_photo(chat_id=chat.user_id, photo=f, **photo_content)
            next_msg_to_del.append(photo_msg.message_id)
            return True
        return False

    def _edit_message(self, chat, message_content):
        try:
            self.edit_message_text(chat_id=chat.user_id, message_id=chat.last_message_id, **message_content)
        except telegram.error.BadRequest as err:
            if err.message == EDIT_MSG_NOT_FOUND_ERROR:
                log.warning(f"{chat} - {err.message}")
            elif err.message == EDIT_MSG_IDENTICAL_ERROR:
                log.warning(f"{chat} - {err.message}")
            else:
                raise

    def _send_message(self, chat, message_content):
        chat.add_msg_to_delete(chat.last_message_id)
        new_message = self.send_message(chat_id=chat.user_id, **message_content, disable_notification=False)  # TODO: utilise "disable_notification"
        new_id = new_message.message_id
        self.service.send_request(Request('student_databaser', 'set_chat_last_message_id', chat.user_id, new_id))
        chat.set_last_message_id(new_id)

    # Runtime

    def sync(self):
        if "--no_sync" not in sys.argv:
            self.update_queue.put(ChatSyncUpdate())

    def stop(self):
        for chat in self.chats.copy():
            chat.stop()
            chat.reset_session(var.SHUTDOWN_MESSAGE_CODE)
            self._dispatch_message(chat, edit=True)

    def exit(self):
        log.info("Bot exiting...")
        self.notif_center.exit()
        self.updater.stop()
        log.info("Bot exited")
