from . import var
from modules.service_pipe import ServicePipe, Request
from modules.base_service import BaseService, StopService, NoResultRequest
from multiprocessing import Event
import html
import importlib
import logging, os
from math import ceil

log = logging.getLogger(__name__)


class GhislieriServices(BaseService):
    SERVICE_NAME = "ghislieri_services"

    def __init__(self, services):
        """
        Class for managing all services

        :param tuple[str] services: the services to start
        """
        log.info("GhislieriServices initializing...")
        super(GhislieriServices, self).__init__(dict(tuple((s, ServicePipe()) for s in ('ghislieri_services',) + services)), Event())
        self.service_modules, self.services = dict(), dict()
        for s in services:
            self._init_services(s)

    def _init_services(self, service):
        self.service_modules[service] = importlib.import_module(f"services.{service}.{service}")
        self.services[service] = self.service_modules[service].SERVICE_CLASS(self.services_pipes, self.stop_event)

    # Requests

    def _request_shutdown(self):
        self.pipe.send_back_result(None)
        raise StopService

    def _request_restart_service(self, service):
        log.info(f"Restarting service {service}")
        self.pipe.send_back_result(None)
        self.services_pipes[service].send_request(Request(service, 'stop'))
        self.stop_event.set()
        self.services[service].join()
        self.stop_event.clear()
        self.service_modules[service] = importlib.reload(self.service_modules[service])
        self.services[service] = self.service_modules[service].SERVICE_CLASS(self.services_pipes, self.stop_event)
        self.services[service].start()
        raise NoResultRequest

    def _request_get_errors(self):
        return tuple({"filename": f} for f in sorted(os.listdir(var.ERRORS_DIR)))

    def _request_get_logs(self):
        return tuple({"filename": f} for f in sorted(os.listdir(var.LOGS_DIR)))

    def _request_get_error(self, filename):
        with open(os.path.join(var.ERRORS_DIR, filename)) as file:
            return html.escape(file.read())

    def _request_get_log(self, filename, page):
        with open(os.path.join(var.LOGS_DIR, filename)) as file:
            raw = file.readlines()
            return {"max_pages": ceil(len(raw) / var.MAX_LOGS_PER_PAGE),
                    "page": "".join(f"{l[0][:4]}  {l[1][5:19]}  {l[3].split('-')[0]:16} {l[4]}" for l in (k.split(";") for k in raw[(page - 1) * var.MAX_LOGS_PER_PAGE:page * var.MAX_LOGS_PER_PAGE]))}

    def _request_get_version(self):
        with open(os.path.join(var.CHANGELOGS_DIR, var.CHANGELOGS_FILENAME)) as file:
            return {"version": var.VERSION, "changelog": file.read()}

    def _request_test(self, **kwargs):
        print(kwargs)

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
        super(GhislieriServices, self)._exit()
