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
import logging, os, requests, json

log = logging.getLogger(__name__)

# Telegram errors
CONNECTION_LOST_ERROR = "urllib3 HTTPError HTTPSConnectionPool"
EDIT_MSG_NOT_FOUND_ERROR = "Message to edit not found"
EDIT_MSG_IDENTICAL_ERROR = "Message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message"
DELETE_MSG_NOT_FOUND_ERROR = "Message to delete not found"
MESSAGE_CANT_BE_DELETED_ERROR = "Message can't be deleted for everyone"

UNDELETABLE_MESSAGE_TEXT = "Questo messaggio può essere eliminato"


def get_bot_token():
    with open(var.FILEPATH_BOT_TOKEN, 'r') as token_file:
        return token_file.readline()


def wait_for_internet():
    return
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
        dispatcher.add_handler(tlg.ext.MessageHandler(tlg.ext.Filters.text & (~tlg.ext.Filters.command), self._answer_handler))
        dispatcher.add_error_handler(self._error_handler)
        # TODO: Add Files Handler
        # TODO: Add StringCommandHandler to handle commands sent on the telegram chat

    def _error_handler(self, update, context):
        err = context.error
        # if err CONNECTION_LOST_ERROR in err.message:  #  TODO: Correct this "AttributeError: 'Error' object has no attribute 'message'"
        #     log.warning("Connection lost!")
        #     return
        log.error(f"Exception while handling an update: {err}")
        try:
            chat = self._get_chat(update)
            chat.reset_session(var.ERROR_MESSAGE_CODE)
            chat.data['error'] = err
            try:
                self._send_message(chat, del_user_msg=update.message.message_id)
            except AttributeError:
                self._send_message(chat, edit=True)
        except Exception:
            chat = None
        utl.log_error(err, chat=chat)

    def _chat_sync_handler(self, update, context):
        print(f"sync - {update.update_id}")
        # TODO:  Implement message refreshing every sometime as messages older than two days can't be deleted (PROBLEM: messages can't be sent without push notification, but only without wound)
        for chat in self.chats:
            update_notify = chat.sync(update.update_id)
            if update_notify is not None:
                self._send_message(chat, edit=not update_notify)

    def _remove_chat_handler(self, update, context):
        chat = next(filter(lambda x: x.user_id == update.update_id, self.chats))
        self.delete_message(chat_id=chat.user_id, message_id=chat.last_message_id)
        self.chats.remove(chat)
        log.info(f"Removed student with user_id {update.update_id}")

    def _start_command_handler(self, update, context):
        try:
            chat = self._get_chat(update)
            chat.reset_session()
        except NewUser as user:
            chat = user.chat
        self._send_message(chat, del_user_msg=update.message.message_id)

    def _keyboard_handler(self, update, context):
        try:
            chat = self._get_chat(update)
            chat.reply('KEYBOARD', callback=update.callback_query.data)
        except NewUser as user:
            chat = user.chat
        self._send_message(chat, edit=True)

    def _answer_handler(self, update, context):
        try:
            chat = self._get_chat(update)
            answer = update.message.text
            answer.replace("{", "{{")
            answer.replace("}", "}}")
            chat.reply('ANSWER', answer=answer)
        except NewUser as user:
            chat = user.chat
        self._send_message(chat, del_user_msg=update.message.message_id)

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
                        log.error(f"JSON error in file {filepath}")
                        utl.log_error(err)
        return messages

    def get_message(self, code):
        return self.messages[code]

    # Chats

    def _load_chats(self):
        return set(Chat(self, **s) for s in self.service.send_request(Request('student_databaser', 'get_chats')))

    def _get_chat(self, update):
        try:
            return next(filter(lambda c: c.user_id == update.effective_user.id, self.chats))
        except StopIteration:
            return self._new_student_signup(update)

    def _new_student_signup(self, update):
        user_id = update.effective_user.id
        log.info(f"Found new student with user_id {user_id}")
        new_msg_id = self.send_message(chat_id=user_id, text="Starting...")
        chat = Chat(self, **self.service.send_request(Request('student_databaser', 'new_chat', user_id, new_msg_id.message_id)))
        self.chats.add(chat)
        chat.reset_session(var.WELCOME_MESSAGE_CODE)
        raise NewUser(chat)

    # Sending & Editing

    def _send_message(self, chat, edit=False, del_user_msg=None):
        try:
            chat.check_auth()
        except MessageAuthorizationError as err:
            chat.reset_session(var.AUTH_ERROR_MESSAGE_CODE)
            chat.data['auth_error.code'] = err.msg_code
            utl.log_error(err, chat=chat, msg_code=err.msg_code)
        message_content = chat.get_message_content()
        if edit:
            self._edit_message(chat, message_content)
        else:
            self._send_and_delete_message(chat, message_content, del_user_msg)

    def _edit_message(self, chat, message_content):
        try:
            self.edit_message_text(**message_content)
        except telegram.error.BadRequest as e:
            if e.message == EDIT_MSG_NOT_FOUND_ERROR:
                log.warning(e.message)
                self._send_and_delete_message(chat, message_content)
            elif e.message == EDIT_MSG_IDENTICAL_ERROR:
                log.warning(e.message)
            else:
                raise

    def _send_and_delete_message(self, chat, message_content, del_user_msg=None):
        for m in (message_content['message_id'],) if del_user_msg is None else (message_content['message_id'], del_user_msg):
            try:
                self.delete_message(chat_id=message_content['chat_id'], message_id=m)
            except telegram.error.BadRequest as e:
                if e.message == DELETE_MSG_NOT_FOUND_ERROR:
                    log.warning(e.message)
                elif e.message == MESSAGE_CANT_BE_DELETED_ERROR:
                    log.warning(e.message)
                    self.edit_message_text(chat_id=chat.user_id, message_id=m, text=UNDELETABLE_MESSAGE_TEXT)
                else:
                    raise e
        message_content.pop('message_id')
        new_message = self.send_message(**message_content, disable_notification=True)
        new_id = new_message.message_id
        self.service.send_request(Request('student_databaser', 'set_chat_last_message_id', chat.user_id, new_id))
        chat.set_last_message_id(new_id)

    # Runtime

    def sync(self):
        self.update_queue.put(ChatSyncUpdate())

    def stop(self):
        for chat in self.chats:
            chat.stop()
            chat.reset_session(var.SHUTDOWN_MESSAGE_CODE)
            self._send_message(chat, edit=True)

    def exit(self):
        log.info("Bot exiting...")
        self.notif_center.exit()
        self.updater.stop()
        log.info("Bot exited")
