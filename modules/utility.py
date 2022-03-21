import os, datetime, traceback
from . import var


def log_error(error, severity="error", **kwargs):
    time = datetime.datetime.now().strftime(var.DATETIME_FORMAT)
    header = f"severity={severity}\ntime={time}"
    for k in kwargs:
        header += f"\n{k}={kwargs[k]}"
    error_str = ''.join(traceback.format_exception(None, error, error.__traceback__))
    with open(os.path.join(var.ERRORS_DIR, f"{severity}_{time}.gser"), 'w', encoding='utf-8') as f:
        f.write(f"{header}\n--------------------------------\n{error_str}")


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    def __getitem__(self, item):
        try:
            i, r = item.split(".", 1)
            return super(dotdict, self).__getitem__(i)[r]
        except ValueError:
            return super(dotdict, self).__getitem__(item)

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            value = dotdict(value)
        try:
            i, r = key.split(".", 1)
            super(dotdict, self).__getitem__(i).__setitem__(r, value)
        except ValueError:
            super(dotdict, self).__setitem__(key, value)
        except KeyError:
            d = dotdict()
            super(dotdict, self).__setitem__(i, d)
            d.__setitem__(r, value)


def get_weekday_name(date, abbr=False):
    if abbr:
        return ("lun", "mar", "mer", "gio", "ven", "sab", "dom")[date.weekday()]
    return ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")[date.weekday()]


def get_month_name(date, abbr=False):
    if abbr:
        return ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")[date.month - 1]
    return ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")[date.month - 1]
