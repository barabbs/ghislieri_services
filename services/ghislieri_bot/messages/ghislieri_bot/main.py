from ... import basemessages as bmsg
from .profile import ProfileMessage
from .feedback import FeedbackMessage
from .about import AboutMessage


class MainMessage(bmsg.BackMessage):
    TITLE = ":wrench:    Impostazioni"
    TEXT = bmsg.fmt.bold(TITLE)
    BUTTONS = [[("profile", ProfileMessage.TITLE, bmsg.get_new_message_answer(ProfileMessage)), ],
               [("feedback", FeedbackMessage.TITLE, bmsg.get_new_message_answer(FeedbackMessage)), ],
               [("about", AboutMessage.TITLE, bmsg.get_new_message_answer(AboutMessage)), ],
               ]
