"""Links to the college's Telegram channels and groups."""

from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.text import Const

from ..common import BACK

ACCESS = "student"


class ChannelsSG(StatesGroup):
    main = State()


dialog = Dialog(
    Window(Const("🚧 In costruzione"), BACK, state=ChannelsSG.main),
)
