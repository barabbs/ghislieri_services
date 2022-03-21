from modules.service_pipe import ServicePipe, Request
from services.student_databaser.student_databaser import StudentDatabaser
from services.meals_reservation.meals_reservation import MealsReservation
from services.eduroam_reporter.eduroam_reporter import EduroamReporter
from services.ghislieri_bot.ghislieri_bot import GhislieriBot
from multiprocessing import Event
import logging

log = logging.getLogger(__name__)

SERVICES_CLASSES = {'student_databaser': StudentDatabaser,
                    'meals_reservation': MealsReservation,
                    'eduroam_reporter': EduroamReporter,
                    'ghislieri_bot': GhislieriBot}


class GhislieriServices(object):
    def __init__(self, services):
        """
        Class for managing all services

        :param tuple[str] services: the services to start
        """
        log.info("GhislieriServices initializing...")
        self.services_pipes = dict(tuple((s, ServicePipe()) for s in ('ghislieri_services',) + services))
        self.stop_event = Event()
        self.services = dict()
        self._init_services(services)

    def _init_services(self, services):
        for s in services:
            self.services[s] = SERVICES_CLASSES[s](self.services_pipes, self.stop_event)

    def run(self):
        for s in self.services:
            self.services[s].start()
        log.info("All Services started")
        try:
            while True:
                k = input(" >  ")
                if k == 'q':
                    break
                elif k == 's':
                    print(self._send_request(Request('student_databaser', 'get_students')))
        except KeyboardInterrupt:
            pass

        self._exit()
        log.info("GhislieriServices terminated")

    def _exit(self):
        log.info("GhislieriServices terminating...")
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

    def _send_request(self, request):  # TODO: Consider inheritance of GhislieriServices from BaseService
        return self.services_pipes[request.service_name].send_request(request=request)
