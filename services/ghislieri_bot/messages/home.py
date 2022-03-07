from .. import basemessages as bmsg
import importlib


class HomeMessage(bmsg.QueryMessage):
    TEXT = f":red_square::yellow_square::red_square::yellow_square:    {bmsg.fmt.bold('Collegio Ghislieri')}    :yellow_square::red_square::yellow_square::red_square:"
    BOT_SERVICES = ('eduroam_reporting', 'ghislieri_bot')

    def _get_buttons(self, **kwargs):
        buttons = list()
        for service in self.BOT_SERVICES:
            message = importlib.import_module(f"services.ghislieri_bot.messages.{service}.main").MainMessage
            buttons.append([(service, message.TITLE, bmsg.get_new_message_answer(message)), ])
        return buttons
