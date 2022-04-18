from . import var
from modules.service_pipe import ServicePipe, Request
from modules.base_service import BaseService, StopService
from services.student_databaser.student_databaser import StudentDatabaser
from services.email_service.email_service import EmailService
from services.meals_management.meals_management import MealsManagement
from services.eduroam_reporter.eduroam_reporter import EduroamReporter
from services.ghislieri_bot.ghislieri_bot import GhislieriBot
from multiprocessing import Event
import logging, os

log = logging.getLogger(__name__)

SERVICES_CLASSES = {'student_databaser': StudentDatabaser,
                    'email_service': EmailService,
                    'meals_management': MealsManagement,
                    'eduroam_reporter': EduroamReporter,
                    'ghislieri_bot': GhislieriBot}


class GhislieriServices(BaseService):
    SERVICE_NAME = "ghislieri_services"

    def __init__(self, services):
        """
        Class for managing all services

        :param tuple[str] services: the services to start
        """
        log.info("GhislieriServices initializing...")
        super(GhislieriServices, self).__init__(dict(tuple((s, ServicePipe()) for s in ('ghislieri_services',) + services)), Event())
        self.services = dict()
        self._init_services(services)

    def _init_services(self, services):
        for s in services:
            self.services[s] = SERVICES_CLASSES[s](self.services_pipes, self.stop_event)

    # Requests

    def _request_shutdown(self):
        self.pipe.send_back_result(None)
        raise StopService

    def _request_get_errors(self):
        return tuple({"filename": f} for f in sorted(os.listdir(var.ERRORS_DIR)))

    def _request_get_logs(self):
        return tuple({"filename": f} for f in sorted(os.listdir(var.LOGS_DIR)))

    def _request_get_error(self, filename):
        with open(os.path.join(var.ERRORS_DIR, filename)) as file:
            return file.read()

    def _request_get_log(self, filename):
        with open(os.path.join(var.LOGS_DIR, filename)) as file:
            return file.read()

    # Runtime

    def run(self):
        for s in self.services:
            self.services[s].start()
        log.info("All Services started")
        try:
            super(GhislieriServices, self).run()
        except KeyboardInterrupt:
            log.warning(f"{self.SERVICE_NAME} forced stopping (KeyboardInterrupt)...")
            self._exit()
            log.info(f"{self.SERVICE_NAME} terminated")

    def _exit(self):
        for service, pipe in self.services_pipes.items():
            if service == 'ghislieri_services':
                continue
            pipe.send_request(Request(service, 'stop'))
            log.debug(f"'stop' request received by {service} service")
        log.debug(f"Stopping all services services")
        self.stop_event.set()
        for service in self.services.values():
            service.join()
            log.debug(f"Process of {service} service terminated")
