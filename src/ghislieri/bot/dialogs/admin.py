"""Admin menu."""

from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.text import Const

from ..common import BACK

ACCESS = "master"


class AdminSG(StatesGroup):
    main = State()


dialog = Dialog(
    Window(Const("🚧 In costruzione"), BACK, state=AdminSG.main),
)
