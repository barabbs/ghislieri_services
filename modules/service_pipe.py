from multiprocessing import Pipe, Lock


class Request(object):
    def __init__(self, service_name, r_type, *args, **kwargs):
        self.service_name, self.r_type = service_name, r_type
        self.args, self.kwargs = args, kwargs


class ServicePipe(object):
    def __init__(self):
        self.service_conn, self.requests_conn = Pipe(duplex=True)
        self.lock = Lock()

    def send_request(self, request):
        with self.lock:
            self.requests_conn.send(request)
            result = self.requests_conn.recv()
            if isinstance(result, Exception):
                raise result
        return result

    def get_request(self):
        if self.service_conn.poll():
            return self.service_conn.recv()

    def send_back_result(self, result):
        self.service_conn.send(result)

    def close(self):
        self.service_conn.close()
