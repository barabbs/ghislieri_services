import os, traceback
import datetime as dt
import subprocess
import re
from . import var

def get_unused_filepath(filepath, sep="_"):
    i = 0
    base, ext = os.path.splitext(filepath)
    while os.path.exists(filepath):
        i += 1
        filepath = f"{base}{sep}{i}{ext}"
    return filepath


def log_error(error, severity="error", **kwargs):
    time = get_str_from_time()
    header = f"severity={severity}\ntime={time}"
    for k in kwargs:
        header += f"\n{k}={kwargs[k]}"
    error_str = ''.join(traceback.format_exception(None, error, error.__traceback__))
    with open(get_unused_filepath(os.path.join(var.ERRORS_DIR, f"{severity}_{time}.gser"), sep="-"), 'w', encoding='utf-8') as f:
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


def get_str_from_time(dtime=None, date=False):
    return (dt.datetime.now() if dtime is None else dtime).strftime(var.DATE_FORMAT if date else var.DATETIME_FORMAT)


def get_time_from_str(t_str=None):
    return dt.datetime.now() if t_str is None else dt.datetime.strptime(t_str, var.DATETIME_FORMAT)


def get_weekday_name(date, abbr=False):
    if abbr:
        return ("lun", "mar", "mer", "gio", "ven", "sab", "dom")[date.weekday()]
    return ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")[date.weekday()]


def get_month_name(date, abbr=False):
    if abbr:
        return ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")[date.month - 1]
    return ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")[date.month - 1]


def get_text_hist(data, data_key, end_str):
    m = max(d[data_key] for d in data)
    m = m if m > 0 else 1
    return "\n".join(tuple(f"{i:02} {'█' * round(20 * d[data_key] / m)}{'░' * (20 - round(20 * d[data_key] / m))} {end_str.format(**d)}" for i, d in enumerate(data)))


def convert_docx_to_pdf(source, timeout=None):
    directory, filename = os.path.dirname(source), os.path.basename(source)
    args = ['libreoffice', '--headless', '--convert-to', 'pdf', filename]
    subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, cwd=directory)
    return os.path.join(directory, os.path.splitext(filename)[0] + ".pdf")
