from . import utility as utl
from . import var
import datetime as dt
from multiprocessing import Process
import schedule as sch
from time import sleep, time
import logging

log = logging.getLogger(__name__)


class StopService(Exception):
    pass


_EMPTY_EXECS_STATS = {"time": 0., "num": 0, "long": 0}
_EMPTY_REQS_STATS = {"num": 0, "err": 0}


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
        self.statistics = self._load_statistics()
        self._load_tasks()

    def _load_statistics(self):
        execs, reqs = _EMPTY_EXECS_STATS.copy(), _EMPTY_REQS_STATS.copy()
        return {"start_time": dt.datetime.now(), "execs": execs, "reqs": reqs, "history": {"execs": [execs, ] * 24, "reqs": [reqs, ] * 24, }}

    def _load_tasks(self):
        self.scheduler.every().hours.at(":00").do(self._task_update_statistics)

    def send_request(self, request):
        return self.services_pipes[request.service_name].send_request(request=request)

    # Requests

    def _request_stop(self):
        log.info(f"{self.SERVICE_NAME} received stop request")
        self._stop()
        self.pipe.send_back_result(None)
        while not self.stop_event.is_set():
            t = time()
            self._handle_requests()
            sleep(max(0., var.SERVICE_UPDATE_INTERVAL - (time() - t)))
        self.pipe.close()
        raise StopService

    def _request_get_statistics(self):
        return self._get_statistics()

    def _handle_requests(self):
        while True:
            req = self.pipe.get_request()
            if req is None:
                return
            log.debug(f"{self.SERVICE_NAME} received request {req.r_type} with args {req.args} and kwargs {req.kwargs}")
            try:
                self.statistics["reqs"]["num"] += 1
                res = getattr(self, f'_request_{req.r_type}')(*req.args, **req.kwargs)
                self.pipe.send_back_result(res)
            except StopService:
                raise
            except Exception as err:
                log.error(f"Error while processing request {req.r_type} with args {req.args} and kwargs {req.kwargs}")
                self.statistics["reqs"]["err"] += 1
                utl.log_error(err, service=self.SERVICE_NAME, r_type=req.r_type, args=req.args, kwargs=req.kwargs)
                self.pipe.send_back_result(err)

    # Tasks

    def _task_update_statistics(self):
        hour, execs, reqs = dt.datetime.now().hour, _EMPTY_EXECS_STATS.copy(), _EMPTY_REQS_STATS.copy()
        self.statistics["execs"], self.statistics["reqs"] = execs, reqs
        self.statistics["history"]["execs"][hour], self.statistics["history"]["reqs"][hour] = execs, reqs

    def _execute_tasks(self):
        self.scheduler.run_pending()

    # Statistics

    def _update_exec_statistics(self, exec_time):
        self.statistics["execs"]["time"] += exec_time
        self.statistics["execs"]["num"] += 1
        self.statistics["execs"]["long"] += 0 if exec_time < var.SERVICE_UPDATE_INTERVAL else 1

    def _get_statistics(self):
        for e in self.statistics["history"]["execs"]:
            e["mean_exec_time"] = e["time"] / max(1, e["num"])
        stats = self.statistics.copy()
        stats["start_time"] = stats["start_time"].strftime(var.DATETIME_FORMAT)
        stats["hists"] = {"execs": utl.get_text_hist(self.statistics["history"]["execs"], "mean_exec_time", "{mean_exec_time:0.3}    long {long}"),
                          "reqs": utl.get_text_hist(self.statistics["history"]["reqs"], "num", "{num:7}    err: {err}")}
        return stats

        # Runtime

    def run(self):
        log.info(f"{self.SERVICE_NAME} started")
        try:
            while True:
                t = time()
                self._update()
                self._execute_tasks()
                self._handle_requests()
                exec_time = time() - t
                self._update_exec_statistics(exec_time)
                sleep(max(0., var.SERVICE_UPDATE_INTERVAL - exec_time))
        except StopService:
            log.info(f"{self.SERVICE_NAME} stopping...")
        finally:
            self._exit()
        log.info(f"{self.SERVICE_NAME} terminated")

    def _update(self):
        pass

    def _stop(self):
        pass

    def _exit(self):
        pass
