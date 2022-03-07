from ... import basemessages as bmsg
from . import var

class AboutMessage(bmsg.BackMessage):
    TITLE = f":information:    Informazioni"
    TEXT = var.ABOUT_BOT
