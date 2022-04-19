from . import utility as utl
from . import var
from multiprocessing import Process
import schedule as sch
from time import sleep, time
import logging

log = logging.getLogger(__name__)


class StopService(Exception):
    pass


class BaseService(Process):
    SERVICE_NAME = ""

    def __init__(self, services_pipes, stop_event):
        """
        Base class for the different services. Manages the requests handling from and sending to the ServicesPipes

        :param dict[ServicePipe] services_pipes: a dict of all the pipes between
        :param Event stop_event:
        """
        log.info(f"Service {self.SERVICE_NAME} initializing...")
        super(BaseService, self).__init__()
        self.services_pipes = services_pipes
        self.stop_event = stop_event
        self.pipe = self.services_pipes[self.SERVICE_NAME]
        self.scheduler = sch.Scheduler()
        self._load_tasks()

    def _load_tasks(self):
        pass

    def send_request(self, request):
        return self.services_pipes[request.service_name].send_request(request=request)

    def run(self):
        log.info(f"{self.SERVICE_NAME} started")
        try:
            while True:
                t = time()
                self._update()
                self._execute_tasks()
                self._handle_requests()
                sleep(max(0., var.SERVICE_UPDATE_INTERVAL - (time() - t)))
        except StopService:
            log.info(f"{self.SERVICE_NAME} stopping...")
        finally:
            self._exit()
        log.info(f"{self.SERVICE_NAME} terminated")

    def _update(self):
        pass

    def _execute_tasks(self):
        self.scheduler.run_pending()

    def _handle_requests(self):
        while True:
            req = self.pipe.get_request()
            if req is None:
                return
            log.debug(f"{self.SERVICE_NAME} received request {req.r_type} with args {req.args} and kwargs {req.kwargs}")
            try:
                res = getattr(self, f'_request_{req.r_type}')(*req.args, **req.kwargs)
            except StopService:
                raise
            except Exception as err:
                log.error(f"Error while processing request {req.r_type} with args {req.args} and kwargs {req.kwargs}")
                utl.log_error(err, service=self.SERVICE_NAME, r_type=req.r_type, args=req.args, kwargs=req.kwargs)
                res = err
            self.pipe.send_back_result(res)

    def _request_stop(self):
        log.info(f"{self.SERVICE_NAME} received stop request")
        self._stop()
        self.pipe.send_back_result(None)
        while not self.stop_event.is_set():
            self._handle_requests()  # TODO: Add sleep time between cycles?
        self.pipe.close()
        raise StopService

    def _stop(self):
        pass

    def _exit(self):
        pass
