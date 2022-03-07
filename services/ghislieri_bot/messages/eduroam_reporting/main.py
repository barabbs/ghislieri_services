from ... import basemessages as bmsg
from datetime import datetime
import os
from . import var


class ThankYouMessage(bmsg.PushMessage):
    TEXT = "Grazie per la segnalazione! :grinning_face_with_smiling_eyes:"


class MainMessage(bmsg.BackMessage, bmsg.OptionsTextMessage):
    TITLE = ":double_exclamation_mark:    Segnalazioni Eduroam"
    TEXT = bmsg.fmt.bold(TITLE) + "\nSeleziona una segnalazione o inviane una nuova"
    OPTIONS = var.REPORTS_LIST
    TEXT_ANSWER = bmsg.get_new_message_answer(ThankYouMessage)

    def get_answer_text(self, text, **kwargs):
        student = kwargs['student']
        time = datetime.now().strftime(var.DATETIME_FORMAT)
        header = f"name={student.get_info('name')}\nsurname={student.get_info('surname')}\nuser_id={student.user_id}\ntime={time}"
        file_name = f"{student.user_id} - {time}"
        with open(os.path.join(var.TEMP_REPORTS_DIR, f"{file_name}.{var.TEMP_REPORTS_EXT}"), 'w', encoding='utf-8') as f:
            f.write(f"{header}\n\n{text}")
        os.rename(os.path.join(var.TEMP_REPORTS_DIR, f"{file_name}.{var.TEMP_REPORTS_EXT}"), os.path.join(var.TEMP_REPORTS_DIR, f"{file_name}.{var.REPORTS_EXT}"))
        return super(MainMessage, self).get_answer_text(text, **kwargs)