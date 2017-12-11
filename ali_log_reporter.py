import socket
import Queue
import threading
import time
from aliyun.log.logexception import LogException
from aliyun.log.putlogsrequest import PutLogsRequest
from aliyun.log.logitem import LogItem
from aliyun.log.logclient import LogClient


class AliLogReporter:
    def __init__(self, endpoint, access_id, access_key, project, logstore, max_buffer_trace=10000, batch_size=100,
                 buffer_interval=10):
        self.trace_queue = Queue.Queue()
        self.semaphore = threading.Semaphore(0)
        self.batch_size = batch_size
        self.max_buffer_trace = max_buffer_trace
        self.buffer_interval = buffer_interval
        self.running = True
        self.logClient = LogClient(endpoint, access_id, access_key, "")
        self.project = project
        self.logstore = logstore
        self.hostname = socket.gethostname()
        self.ip = socket.gethostbyname(self.hostname)
        self.last_send_time = time.time()
        self.send_thread = threading.Thread(target=self.sed_trace_thread)
        self.send_thread.setDaemon(True)
        self.send_thread.start()

    def sed_trace_thread(self):
        while self.running:
            if self.semaphore.acquire():
                self.send_trace(False)
        self.send_trace(True)

    @property
    def is_send_time(self):
        return self.trace_queue.qsize() > self.batch_size or time.time() - self.last_send_time > self.buffer_interval

    def send_trace(self, send_all=False):
        while not self.trace_queue.empty() and (send_all or self.is_send_time):
            log_items = []
            while self.trace_queue.empty() == False and len(log_items) < self.batch_size:
                log_items.append(self.trace_queue.get())
            try:
                request = PutLogsRequest(self.project, self.logstore, "", "", log_items)
                self.logClient.put_logs(request)
            except LogException as e:
                print("Send Failed:{}".format(e))
            self.last_send_time = time.time()

    @staticmethod
    def int_to_hex(value):
        if value is None:
            return str(0)
        return '{:x}'.format(value)

    def report_span(self, span):

        start_time = long(span.start_time * 1000 * 1000 * 1000)
        end_time = long(span.end_time * 1000 * 1000 * 1000)

        if self.trace_queue.qsize() > self.max_buffer_trace:
            help_message = "discard trace as queue full, "
            help_message += '\t'.join(["{k}:{v}".format(k=k, v=getattr(span, k)) for k in span.__slots__])
            help_message += '\t'.join(
                ["{k}:{v}".format(k=k, v=getattr(span.context, k)) for k in span.context.__slots__])
            print(help_message)

        log_item = LogItem()
        log_item.set_time(int(time.time()))
        log_item.push_back("TraceID", self.int_to_hex(span.context.trace_id))
        log_item.push_back("SpanID", self.int_to_hex(span.context.span_id))
        log_item.push_back("ParentSpanID", self.int_to_hex(span.context.parent_id))

        log_item.push_back("ServiceName", span.tracer.service_name)
        log_item.push_back("OperationName", span.operation_name)
        log_item.push_back("StartTime", str(start_time))
        log_item.push_back("Duration", str(end_time - start_time))
        log_item.push_back("process.hostname", self.hostname)
        log_item.push_back("process.ips", self.ip)

        tag_map = dict()
        for tag in span.tags:
            tag_map["tag." + str(tag.key)] = str(tag.value)

        for key, value in tag_map.items():
            log_item.push_back(key, value)

        log_list = []
        for log in span.logs:
            log_list.append(str(log.value))
        if len(log_list) > 0:
            log_item.push_back("logs", str(log_list))

        self.trace_queue.put(log_item)

        if self.is_send_time:
            self.semaphore.release()

    def send(self):
        if not self.trace_queue.empty():
            self.send_trace(True)

    def close(self):  # when the reporter is closed ,it should never be used again
        self.running = False
        self.semaphore.release()
        self.send_thread.join(10)
        if not self.trace_queue.empty():
            print("Trace exit while there are still {} traces not send".format(self.trace_queue.qsize()))

