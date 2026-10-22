"""Access control on crafted callbacks (aiogram-dialog does not check `when=` on presses by itself)."""

from aiogram.types import InlineKeyboardButton
from conftest import client, make_user

from ghislieri import users


class Crafted:
    """Button locator returning arbitrary callback data, like a modified Telegram client would send."""

    def __init__(self, data: str):
        self.data = data

    def find_button(self, message):
        return InlineKeyboardButton(text="x", callback_data=self.data)


async def test_hidden_buttons_refuse_presses(dp, app, message_manager):
    make_user(app.conn, 5, users.ALUMNUS)
    c = client(dp, app, 5)
    await c.send("/start")
    home = message_manager.last_message()
    intent = home.reply_markup.inline_keyboard[0][0].callback_data.split("\x1d")[0]
    for hidden in ("meals", "admin"):  # meals has no router guard: only the central check stops it
        message_manager.reset_history()
        await c.click(home, Crafted(f"{intent}\x1d{hidden}"))
        assert all("Collegio Ghislieri" in m.text for m in message_manager.sent_messages)
