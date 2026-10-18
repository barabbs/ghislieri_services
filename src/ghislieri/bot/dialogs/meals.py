"""Canteen: meal bookings and reports."""

from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.text import Const

from ..common import BACK

ACCESS = "student"


class MealsSG(StatesGroup):
    main = State()
    admin = State()  # entry point linked from the admin menu


dialog = Dialog(
    Window(Const("🚧 In costruzione"), BACK, state=MealsSG.main),
    Window(Const("🚧 In costruzione"), BACK, state=MealsSG.admin),
)
