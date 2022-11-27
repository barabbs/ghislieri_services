from modules import utility as utl
from modules import var
import logging, sys

logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(var.FILEPATH_LOG)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(levelname)s;%(asctime)s;%(name)s;%(processName)s;%(message)s'))
logger.addHandler(file_handler)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(logging.Formatter('%(levelname)s\t%(asctime)s\t%(name)s\t%(processName)s\t%(message)s'))
logger.addHandler(stream_handler)

from modules.ghislieri_services import GhislieriServices


def main():
    try:
        services = tuple(filter(lambda x: x[0] != '-', sys.argv[1:]))
        gs = GhislieriServices(services)
        gs.run()
    except Exception as e:
        logger.critical(f"Critical error while running GhislieriServices: {e}")
        utl.log_error(e, severity="critical")


if __name__ == '__main__':
    main()
