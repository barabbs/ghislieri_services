"""Main menu."""

from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Row, Start
from aiogram_dialog.widgets.text import Const

from .. import common
from ..common import HomeSG, perm
from . import admin, calendar, channels, meals, printing, settings, submissions

ACCESS = None

dialog = Dialog(
    Window(
        Const("🟥🟨    <b>Collegio Ghislieri</b>    🟨🟥"),
        Start(Const("🗓   Calendario"), id="calendar", state=calendar.CalendarSG.main, when=common.perm_active),
        Start(Const("🍽️    Mensa"), id="meals", state=meals.MealsSG.main, when=perm(meals.ACCESS)),
        Row(
            Start(Const("🖨    Stampa"), id="print", state=printing.PrintingSG.main, when=perm(printing.ACCESS)),
            Start(
                Const("📯    Canali e Gruppi"),
                id="channels",
                state=channels.ChannelsSG.main,
                when=perm(channels.ACCESS),
            ),
        ),
        Start(
            Const("📩    Invia Contenuti"),
            id="submit",
            state=submissions.SubmissionsSG.main,
            when=perm(submissions.ACCESS),
        ),
        Row(
            Start(
                Const("🔧    Impostazioni"),
                id="settings",
                state=settings.SettingsSG.main,
                when=common.perm_active,
            ),
            Start(Const("🔓    Admin"), id="admin", state=admin.AdminSG.main, when=perm(admin.ACCESS)),
        ),
        state=HomeSG.main,
    ),
)
