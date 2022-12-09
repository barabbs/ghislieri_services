from modules.base_service import BaseService
from modules.service_pipe import Request
from . import var
from modules import utility as utl

import subprocess
import logging, os

log = logging.getLogger(__name__)


def get_printer_address():
    with open(var.FILEPATH_PRINTER_ADDRESS, 'r') as printer_address:
        return printer_address.readline()


class PrinterService(BaseService):
    SERVICE_NAME = var.SERVICE_NAME

    def __init__(self, *args, **kwargs):
        self.address = get_printer_address()
        super(PrinterService, self).__init__(*args, **kwargs)

    def _request_print_files(self, filepaths, copies=1, page_list=None, **kwargs):
        opt_agrs = ""
        for k, v in kwargs.items():
            if v is not None:
                opt_agrs += f"-o {k}={v} "
        pages_arg = "" if page_list is None else f"-P {page_list} "
        try:
            copies = int(copies)
        except ValueError:
            copies = 1
        try:
            for fpath in filepaths:
                directory, filename = os.path.dirname(fpath), os.path.basename(fpath)
                subprocess.run(f'lp -n {copies} {opt_agrs}-t "ghislieri_services {utl.get_str_from_time()}" {pages_arg}"{filename}"', capture_output=True, check=True,
                               timeout=var.PRINT_PROCESS_TIMEOUT, cwd=directory, shell=True)
        except subprocess.CalledProcessError as err:
            return {"ok": False, "text": f"Errore nella stampa\n\n{err.stderr.decode('utf-8')}"}
        except subprocess.TimeoutExpired as err:
            return {"ok": False, "text": f"Timeout processo di stampa"}
        return {"ok": True, "text": ""}


SERVICE_CLASS = PrinterService
