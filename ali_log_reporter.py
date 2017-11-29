import socket
import Queue
import threading
import time
from aliyun.log.logexception import LogException
from aliyun.log.putlogsrequest import PutLogsRequest
from aliyun.log.logitem import LogItem
from aliyun.log.logclient import LogClient



class AliLogReporter : 
    def __init__(self, endpoint, access_id, access_key, project, logstore, max_buffer_trace = 10000, batch_size = 100, buffer_interval = 10) : 
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
        self.send_thread = threading.Thread(target = self.sed_trace_thread)
        self.send_thread.setDaemon(True)
        self.send_thread.start()


    def sed_trace_thread(self) : 
        while self.running : 
            if self.semaphore.acquire() :
                self.send_trace(False)
        self.send_trace(True)

    def send_trace(self, send_all = False) : 
        while self.trace_queue.empty() == False and (send_all or self.trace_queue.qsize() > self.batch_size or time.time() - self.last_send_time > self.buffer_interval) : 
            logitemList = []
            while self.trace_queue.empty() == False and len(logitemList) < self.batch_size : 
                logitemList.append(self.trace_queue.get())
            try : 
                request = PutLogsRequest(self.project, self.logstore, "", "", logitemList)
                self.logClient.put_logs(request)
            except LogException as e : 
                print "Send Failed:" + e.__str__()
            self.last_send_time = time.time()
        

    def report_span(self, span) : 
        if self.trace_queue.qsize() > self.max_buffer_trace : 
            print "discard trace as queue full, trace_id:" + str(span.context.trace_id) +"\tspan_id:" + str(span.context.span_id)  \
                + "\tparent_id:" + str(span.context.parent_id) + "\tservice_name:" + span.tracer.service_name  \
                + "\tOperation_name:" + span.operation_name + "\tstart_time:" + str(span.start_time) + "\tend_time:" + str(span.end_time)  \
                + "\ttags:" + str(span.tags) + "\tlogs:" + str(span.logs)

        logItem = LogItem()
        logItem.set_time(int(time.time()))
        logItem.push_back("TraceID", str(span.context.trace_id))
        logItem.push_back("SpanID", str(span.context.span_id))
        logItem.push_back("ParentSpanID", str(span.context.parent_id))
        logItem.push_back("ServiceName", span.tracer.service_name)
        logItem.push_back("OperationName", span.operation_name)
        start_time = (long)(span.start_time * 1000 * 1000 * 1000)
        end_time = (long)(span.end_time * 1000 * 1000 * 1000)
        logItem.push_back("StartTime", str(start_time))
        logItem.push_back("Duration", str(end_time - start_time))
        logItem.push_back("process.hostname", self.hostname)
        logItem.push_back("process.ips", self.ip)

        
        tag_map = dict()
        for tag in span.tags: 
            tag_map["tag." + str(tag.key)] = str(tag.value)

        for key,value in tag_map.items() : 
            logItem.push_back(key, value)

        log_list = []
        for log in span.logs : 
            log_list.append(str(log.value))
        if len(log_list) > 0 : 
            logItem.push_back("logs", str(log_list))

        self.trace_queue.put(logItem)

        if self.trace_queue.qsize() > self.max_buffer_trace or time.time() - self.last_send_time > self.buffer_interval : 
            self.semaphore.release()

    def flush(self) : 
        if self.trace_queue.empty() == False : 
            self.send_trace(True)
        

    def close(self) :  # when the reporter is closed ,it should never be used again 
        self.running = False
        self.semaphore.release()
        self.send_thread.join(10)  
        if self.trace_queue.empty() == False : 
            print "Trace exit while there are still " + str(self.trace_queue.qsize()) + " traces not send"

