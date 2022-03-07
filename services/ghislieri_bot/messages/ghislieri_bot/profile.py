from ... import basemessages as bmsg
from . import var


def get_edit_info_message_class(info, text_answer):
    class EditInfoMessage(bmsg.TextMessage, bmsg.BackMessage):
        TEXT = f"Inserisci il tuo {bmsg.fmt.bold(var.STUDENT_INFOS[info])}"
        TEXT_ANSWER = text_answer

        def get_answer_text(self, text, **kwargs):
            kwargs['databaser'].edit_student_info(kwargs['student'], info, text)
            return super(EditInfoMessage, self).get_answer_text(text, **kwargs)

    return EditInfoMessage


def get_recap_info_message_class(info):
    class RecapAttributeMessage(bmsg.QueryMessage):
        BUTTONS = [[("back", ":right_arrow_curving_left: Back", bmsg.get_back_answer()),
                    ("edit", ":pencil: Modifica", bmsg.get_new_message_answer(get_edit_info_message_class(info, bmsg.get_back_answer()))), ], ]

        def _get_text(self, **kwargs):
            info_val = kwargs['student'].get_info(info)
            if info_val is not None:
                return f"{var.STUDENT_INFOS[info].capitalize()}    {bmsg.fmt.bold(info_val)}"
            else:
                return f"{var.STUDENT_INFOS[info].capitalize()} non ancora aggiunto"

    return RecapAttributeMessage


class ProfileMessage(bmsg.BackMessage):
    TITLE = f":bust_in_silhouette:    Profilo"
    TEXT = f"Consulta e modifica le tue informazioni"
    BUTTONS = list([(k, var.STUDENT_INFOS[k].capitalize(), bmsg.get_new_message_answer(get_recap_info_message_class(k))), ] for k in var.STUDENT_INFOS)
