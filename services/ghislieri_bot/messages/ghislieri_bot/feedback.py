from ... import basemessages as bmsg
from datetime import datetime
import os
from . import var


class ThankYouMessage(bmsg.PushMessage):
    TEXT = "Grazie per la segnalazione! :grinning_face_with_smiling_eyes:"


class FeedbackMessage(bmsg.TextMessage, bmsg.BackMessage):
    TITLE = f":speech_balloon:    Segnalazioni e Suggerimenti"
    TEXT = f"Scrivi il {bmsg.fmt.bold('problema')} riscontrato o il {bmsg.fmt.bold('suggerimento')} per il bot"
    TEXT_ANSWER = bmsg.get_new_message_answer(ThankYouMessage)

    def get_answer_text(self, text, **kwargs):
        student = kwargs['student']
        time = datetime.now().strftime(var.DATETIME_FORMAT)
        header = f"name={student.get_info('name')}\nsurname={student.get_info('surname')}\nuser_id={student.user_id}\ntime={time}"
        with open(os.path.join(var.FEEDBACK_DIR, f"{student.user_id} - {time}.gbfb"), 'w', encoding='utf-8') as f:
            f.write(f"{header}\n\n{text}")
        return super(FeedbackMessage, self).get_answer_text(text, **kwargs)
