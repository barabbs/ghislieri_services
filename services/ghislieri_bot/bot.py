from modules.service_pipe import Request
from modules import utility as utl
from .chat import Chat
from . import var
import telegram as tlg
import telegram.ext, telegram.utils.request
from time import sleep, time
import logging

log = logging.getLogger(__name__)

# Telegram errors
EDIT_MSG_NOT_FOUND = "Message to edit not found"
EDIT_MSG_IDENTICAL = "Message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message"
DELETE_MSG_NOT_FOUND = "Message to delete not found"

def get_bot_token():
    with open(var.FILEPATH_BOT_TOKEN, 'r') as token_file:
        return token_file.readline()


class ChatSyncUpdate(tlg.Update):
    def __init__(self):
        super(ChatSyncUpdate, self).__init__(int(time()))


class Bot(tlg.Bot):
    def __init__(self, service):
        """
        Bot class

        :param GhislieriBot service:
        """
        log.info(f"Bot initializing...")
        self.service = service
        super(Bot, self).__init__(token=get_bot_token(), request=tlg.utils.request.Request(con_pool_size=var.REQUEST_CONNECTION_POOL_SIZE))
        self.updater = tlg.ext.Updater(bot=self)
        self._handlers_setup()
        self.chats = self._load_chats()
        while True:
            try:
                self.update_queue = self.updater.start_polling()
            except tlg.error.NetworkError:
                log.error(f"Couldn't connect to server, retrying in {var.INITIAL_CONNECTION_RETRY_TIME} seconds")
                sleep(var.INITIAL_CONNECTION_RETRY_TIME)
            else:
                break
        log.info(f"Bot created")

    def _handlers_setup(self):
        dispatcher = self.updater.dispatcher
        dispatcher.add_handler(tlg.ext.TypeHandler(ChatSyncUpdate, self._chat_sync_handler))
        dispatcher.add_handler(tlg.ext.CommandHandler('start', self._command_handler))
        dispatcher.add_handler(tlg.ext.CallbackQueryHandler(self._query_handler))
        dispatcher.add_handler(tlg.ext.MessageHandler(tlg.ext.Filters.text & (~tlg.ext.Filters.command), self._text_handler))
        dispatcher.add_error_handler(self._error_handler)  # TODO: BUG FIX - Raises tlg.error.NetworkError if not connected to internet (move near self.updater.start_polling() - line 28)
        # TODO: Add Files Handler
        # TODO: Add StringCommandHandler to handle commands sent on the telegram chat

    def _load_chats(self):
        return set(Chat(**s) for s in self.service.send_request(Request('student_databaser', 'get_students')))

    def _get_chat(self, update):
        try:
            return next(filter(lambda c: c.user_id == update.effective_user.id, self.chats))
        except StopIteration:
            self._new_student_signup(update)

    def _new_student_signup(self, update):
        log.info(f"Found new student with user_id {update.effective_user.id}")
        # TODO : Write new student signup
        # welcome_msg = WelcomeMessage()
        # new_msg_id = self.send_message(chat_id=update.message.chat.id, **welcome_msg.get_content())  # TODO: Visual bug - message gets sent and then deleted inside _command_handler
        # student = self.databaser.new_student(update.effective_user.id, update.message.chat.id, new_msg_id.message_id)
        # student.add_reset_message(welcome_msg)
        # return student

    # Handlers

    def _error_handler(self, update, context):
        log.error(f"Exception while handling an update: {context.error}")
        try:
            chat = self._get_chat(update.effective_user.id)
        except Exception:  # TODO: See if there's a better way to do this
            chat = None
        utl.log_error(context.error, chat=chat)

    def _chat_sync_handler(self, update, context):
        for chat in self.chats:
            update_edit = chat.sync(update.update_id)
            if update_edit is not None:
                self._send_message(chat, edit=update_edit)

    def _command_handler(self, update, context):
        chat = self._get_chat(update)
        chat.reset_session()
        self._send_message(chat, del_user_msg=update.message.message_id)

    def _query_handler(self, update, context):
        chat = self._get_chat(update)
        chat.respond('query', update.callback_query.data)
        self._send_message(chat, edit=True)

    def _text_handler(self, update, context):
        chat = self._get_chat(update)
        chat.respond('text', update.message.text)
        self._send_message(chat, del_user_msg=update.message.message_id)

    # Message sending

    def _send_message(self, chat, edit=False, del_user_msg=None):
        message_content = chat.get_message_content()
        if edit:
            self._edit_message(chat, message_content)
        else:
            self._send_and_delete_message(chat, message_content, del_user_msg)

    def _edit_message(self, chat, message_content):
        try:
            self.edit_message_text(**message_content)
        except telegram.error.BadRequest as e:
            if e.message == EDIT_MSG_NOT_FOUND:
                log.warning(e.message)
                self._send_and_delete_message(chat, message_content)
            elif e.message == EDIT_MSG_IDENTICAL:
                log.warning(e.message)
            else:
                log.error(f"Exception while editing a message: {e}")
                utl.log_error(e)

    def _send_and_delete_message(self, chat, message_content, del_user_msg=None):
        try:
            self.delete_message(chat_id=message_content['chat_id'], message_id=message_content['message_id'])
            if del_user_msg is not None:
                self.delete_message(chat_id=message_content['chat_id'], message_id=del_user_msg)
        except telegram.error.BadRequest as e:
            if e.message == DELETE_MSG_NOT_FOUND:
                log.warning(e.message)
            else:
                log.error(f"Exception while sending and deleting a message: {e}")
                utl.log_error(e)
        message_content.pop('message_id')
        new_message = self.send_message(**message_content)
        self.service.send_request(chat.set_last_message_id(new_message.message_id))

    # Runtime

    def run(self):
        log.info("Bot started")
        try:
            while True:
                self.update_queue.put(ChatSyncUpdate())
                sleep(var.STUDENT_UPDATE_SECONDS_INTERVAL)
        except KeyboardInterrupt:
            log.info("Bot received exit signal")
        finally:
            self.exit()
        log.info("Bot finished")

    def exit(self):
        log.info("Bot exiting...")
        self.updater.stop()
        pass  # TODO: Terminating procedures
        log.info("Bot exited")
