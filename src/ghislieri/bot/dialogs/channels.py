"""Links to the college's Telegram channels and groups."""

from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Row, SwitchTo, Url
from aiogram_dialog.widgets.text import Const

from ..common import BACK, perm

ACCESS = "student"


class ChannelsSG(StatesGroup):
    main = State()
    associations = State()
    sports = State()


def link(text: str, url: str, when=None) -> Url:
    return Url(Const(text), Const(url), when=when)


# Each CTS group is for the students of one area.
CTS = {
    "sci_tech": "https://t.me/+aEzuMNgySDlhNjk8",
    "biomed": "https://t.me/+d_NmzD2DdIw2MTU0",
    "social_sci": "https://t.me/+HRcLbDbnzqo0ZjVk",
    "human_sci": "https://t.me/+6E9rpbpdEv0xYmQ0",
}

TO_MAIN = SwitchTo(Const("↩️ Indietro"), id="to_main", state=ChannelsSG.main)

dialog = Dialog(
    Window(
        Const("📯    <b>Canali</b> e <b>Gruppi</b> Telegram del <b>Collegio</b>"),
        link("🟥🟨  Canale Alunni  🟨🟥", "https://t.me/+iikDkY01v8IzZTU0"),
        Row(
            link("📑    Rettorato", "https://t.me/+o8cd9I-LD80xODZk"),
            *(link("👥    CTS", url, when=perm(group)) for group, url in CTS.items()),
        ),
        SwitchTo(Const("🏛    Associazioni Studentesche    🧬"), id="associations", state=ChannelsSG.associations),
        SwitchTo(Const("⚽    Attività Sportive    🏀"), id="sports", state=ChannelsSG.sports),
        BACK,
        state=ChannelsSG.main,
    ),
    Window(
        Const("📯    <b>Canali</b> delle <b>Associazioni Studentesche</b>"),
        link("🔬    Ghislieri Scienza", "https://t.me/+HPp6RHiNbsYxZTE0"),
        link("🏛    Philosophicum Ghislieri", "https://t.me/+yK29NfmXbdwyMGI0"),
        link("🎻    Bardi Ghisleriani", "https://t.me/+lic4qD4Za5hjZjVk"),
        TO_MAIN,
        state=ChannelsSG.associations,
    ),
    Window(
        Const("📯    <b>Gruppi attività sportive</b>"),
        Row(
            link("⚽️    Calcio  (M)", "https://t.me/+T1pjLkISM7MzOWVk"),
            link("🏀    Basket  (M)", "https://t.me/+6ExwzX_OQkIzZWU8"),
        ),
        Row(
            link("🏐️    Pallavolo", "https://t.me/+boGtEJbvmWwyOGQ0"),
            link("🎾️    Tennis", "https://t.me/+pPtgf4w2EGcyMWQ0"),
        ),
        Row(
            link("🐉️    Dragonboat", "https://t.me/+IMQtsljwTOdmYzA0"),
            link("🏋️️    Palestra", "https://t.me/+jC9xtwMHckI1NGY0"),
        ),
        link("🏆️    SuperSega", "https://t.me/+5f5d1aHWstBjMjY0"),
        TO_MAIN,
        state=ChannelsSG.sports,
    ),
)
