"""College calendar."""

from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.text import Const

from ..common import BACK

ACCESS = None


class CalendarSG(StatesGroup):
    main = State()
    admin = State()  # entry point linked from the admin menu


dialog = Dialog(
    Window(Const("🚧 In costruzione"), BACK, state=CalendarSG.main),
    Window(Const("🚧 In costruzione"), BACK, state=CalendarSG.admin),
)
