BOLD, END_BOLD = '<b>', '</b>'
ITALIC, END_ITALIC = '<i>', '</i>'
UNDERLINE, END_UNDERLINE = '<u>', '</u>'
STRIKE, END_STRIKE = '<s>', '</s>'
MONO, END_MONO = '<code>', '</code>'

SANIFY = (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'))


def sanify(string):
    for i in SANIFY:
        string = string.replace(*i)
    return string


def bold(string):
    return BOLD + str(string) + END_BOLD


def italic(string):
    return ITALIC + str(string) + END_ITALIC


def underline(string):
    return UNDERLINE + str(string) + END_UNDERLINE


def strike(string):
    return STRIKE + str(string) + END_STRIKE


def mono(string):
    return MONO + str(string) + END_MONO
