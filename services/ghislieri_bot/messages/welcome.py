from modules import basemessages as bmsg
from .home import HomeMessage
from .ghislieri_bot.profile import get_edit_info_message_class

InsertSurnameMessage = get_edit_info_message_class('surname', bmsg.get_new_message_answer(HomeMessage))
InsertNameMessage = get_edit_info_message_class('name', bmsg.get_new_message_answer(InsertSurnameMessage))


class WelcomeMessage(bmsg.PushMessage):
    TEXT = f"Benvenuto su {bmsg.fmt.bold('Ghislieri Bot')}, il bot per i {bmsg.fmt.italic('servizi del Collegio')}! :grinning_face_with_smiling_eyes:"
    BUTTON_TEXT = "Prosegui"
    BUTTON_ANSWER = bmsg.get_new_message_answer(InsertNameMessage)
