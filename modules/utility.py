import os, datetime, traceback
from . import var


def log_error(error, severity="error"):
    time = datetime.datetime.now().strftime(var.DATETIME_FORMAT)
    header = f"severity={severity}\ntime={time}"
    error_str = ''.join(traceback.format_exception(None, error, error.__traceback__))
    with open(os.path.join(var.ERRORS_DIR, f"{severity}_{time}.gser"), 'w', encoding='utf-8') as f:
        f.write(f"{header}\n--------------------------------\n{error_str}")
