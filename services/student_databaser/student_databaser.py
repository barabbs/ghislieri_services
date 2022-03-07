from . import var
from modules.base_service import BaseService
import sqlite3 as sql
import logging

log = logging.getLogger(__name__)


class StudentDatabaser(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        super(StudentDatabaser, self).__init__(*args, **kwargs)
        self.connection, self.cursor = None, None
        log.info(f"{self.SERVICE_NAME} loading...")
        self._load_database()

    def _load_database(self):
        self.connection = sql.connect(var.FILEPATH_DATABASE)
        self.cursor = self.connection.cursor()

    def _edit_database(self, user_id, attribute, value):
        self.cursor.execute(f"UPDATE {var.DATABASE_STUDENTS_TABLE} SET {attribute} = ? WHERE user_id = ?", (value, user_id))
        self.connection.commit()

    # Requests
    def _request_get_students(self):
        self.cursor.execute(f"SELECT * FROM {var.DATABASE_STUDENTS_TABLE}")
        return tuple({'user_id': s[0], 'last_message_id': s[1], 'student_infos': dict(zip(var.STUDENT_INFOS, s[2:]))} for s in self.cursor.fetchall())

    def _request_set_student_last_message_id(self, user_id, last_message_id):
        self._edit_database(user_id, 'last_message_id', last_message_id)

    def _request_edit_student_info(self, user_id, info, value):
        self._edit_database(user_id, info, value)

    # -------------------------------- OLD CODE --------------------------------

    # def _request_new_student(self, user_id, chat_id, last_message_id):
    #     self.cursor.execute(f"INSERT INTO {var.DATABASE_STUDENTS_TABLE} (user_id, chat_id, last_message_id) VALUES (?, ?, ?)",
    #                         (user_id, chat_id, last_message_id))  # plz, don't do SQL injection on me :(
    #     self.connection.commit()
    #     new_student = Student(user_id, chat_id, last_message_id)
    #     self.students.add(new_student)
    #     return new_student
    #
    # def _request_get_student(self, user_id):
    #     try:
    #         return next(filter(lambda s: s.user_id == user_id, self.students))
    #     except StopIteration:
    #         log.debug("User not found")
    #         return None

    # -------------------------------- OLD CODE --------------------------------

    # Exit

    def _exit(self):
        self.connection.commit()
        self.cursor.close()
        self.connection.close()
