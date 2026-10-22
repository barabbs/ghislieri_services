"""Main menu."""

from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Row, Start, Url
from aiogram_dialog.widgets.text import Const

from ... import users
from .. import common
from ..common import HomeSG, perm
from . import admin, calendar, channels, meals, settings, submissions

ACCESS = None

# Booking sheet of the college's sports field (Campetto), shared on Google Sheets.
CAMPETTO = "https://docs.google.com/spreadsheets/d/1RYa6c-XFP4OnfNmixJt9J0aVFMm2-F3debBzjVxFPHU/edit?usp=sharing"

dialog = Dialog(
    Window(
        Const("🟥🟨 <b>Collegio Ghislieri</b> 🟨🟥"),
        Start(Const("🗓 Calendario"), id="calendar", state=calendar.CalendarSG.main, when=common.perm_active),
        Start(Const("🍽️ Mensa"), id="meals", state=meals.MealsSG.main, when=perm(meals.ACCESS)),
        Start(Const("📯 Canali e Gruppi"), id="channels", state=channels.ChannelsSG.main, when=perm(channels.ACCESS)),
        Row(
            Url(Const("📍 Prenota Campetto"), Const(CAMPETTO), when=perm(users.STUDENT)),
            Start(
                Const("📩 Invia Contenuti"),
                id="submit",
                state=submissions.SubmissionsSG.main,
                when=perm(submissions.ACCESS),
            ),
        ),
        Row(
            Start(
                Const("🔧 Impostazioni"),
                id="settings",
                state=settings.SettingsSG.main,
                when=common.perm_active,
            ),
            Start(Const("🔓 Admin"), id="admin", state=admin.AdminSG.main, when=perm(admin.ACCESS)),
        ),
        state=HomeSG.main,
    ),
)
