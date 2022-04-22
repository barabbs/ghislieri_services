from modules.base_service import BaseService
from modules.service_pipe import Request
from . import var
import sqlite3 as sql
import logging

log = logging.getLogger(__name__)


def get_student_infos_dict(chat):
    return dict(zip(var.STUDENT_INFOS, chat[2:]))


def get_chat_dict(chat):
    return {'user_id': chat[0], 'last_message_id': chat[1], 'student_infos': get_student_infos_dict(chat), 'groups': set(chat[-1].split(",")) if chat[-1] is not None else set()}


class StudentDatabaser(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(StudentDatabaser, self).__init__(*args, **kwargs)
        self.connection, self.cursor = None, None
        self._load_database()

    def _load_database(self):
        self.connection = sql.connect(var.FILEPATH_DATABASE)
        self.cursor = self.connection.cursor()

    def _edit_database(self, user_id, attribute, value):
        self.cursor.execute(f"UPDATE {var.DATABASE_STUDENTS_TABLE} SET {attribute} = ? WHERE user_id = ?", (value, user_id))  # plz, don't do SQL injection on me :(
        self.connection.commit()

    # Requests

    def _request_get_chats(self, group=None, sort=False):
        self.cursor.execute(f"SELECT * FROM {var.DATABASE_STUDENTS_TABLE}")
        if group is None:
            chats = (get_chat_dict(chat) for chat in self.cursor.fetchall())
        else:
            chats = filter(lambda x: group in x['groups'], (get_chat_dict(chat) for chat in self.cursor.fetchall()))
        if sort:
            chats = sorted(chats, key=lambda x: x["student_infos"]["surname"] if x["student_infos"]["surname"] is not None else "")
        return tuple(chats)

    def _request_new_chat(self, user_id, last_message_id):
        self.cursor.execute(f"INSERT INTO {var.DATABASE_STUDENTS_TABLE} (user_id, last_message_id) VALUES (?, ?)", (user_id, last_message_id))
        self.connection.commit()
        self.cursor.execute(f"SELECT * FROM {var.DATABASE_STUDENTS_TABLE} WHERE user_id = ?", (user_id,))
        return get_chat_dict(self.cursor.fetchone())

    def _request_set_chat_last_message_id(self, user_id, last_message_id):
        self._edit_database(user_id, 'last_message_id', last_message_id)

    def _request_edit_student_info(self, user_id, info, value):
        self._edit_database(user_id, info, value)

    def _request_edit_group(self, user_id, group, edit):
        self.cursor.execute(f"SELECT * FROM {var.DATABASE_STUDENTS_TABLE} WHERE user_id = ?", (user_id,))
        groups = get_chat_dict(self.cursor.fetchone())['groups']
        if edit == "add":
            groups.add(group)
        if edit == "rm":
            try:
                groups.remove(group)
            except ValueError:
                pass
        self._edit_database(user_id, 'groups', ",".join(groups))
        self.send_request(Request("ghislieri_bot", "set_groups", user_id=user_id, groups=groups))

    def _request_remove_chat(self, user_id):
        self.cursor.execute(f"DELETE FROM {var.DATABASE_STUDENTS_TABLE} WHERE user_id = ?", (user_id,))
        self.connection.commit()

    # Exit

    def _exit(self):
        self.connection.commit()
        self.cursor.close()
        self.connection.close()
