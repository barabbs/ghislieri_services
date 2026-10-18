"""Content submissions: eduroam reports, social media posts."""

from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.text import Const

from ..common import BACK

ACCESS = "student"


class SubmissionsSG(StatesGroup):
    main = State()


dialog = Dialog(
    Window(Const("🚧 In costruzione"), BACK, state=SubmissionsSG.main),
)
