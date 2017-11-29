# jaeger-client-python-alilog-reporter
Ali LogService reporter for jaeger python client, used to send data to Ali Log service.



## Required

```
 pip install -t . jaeger-client
 pip install -U -t . aliyun-log-python-sdk
```



## Sample

    log_level = logging.DEBUG
    logging.getLogger('').handlers = []
    logging.basicConfig(format='%(asctime)s %(message)s', level=log_level)
    
    config = Config(
        config={ # usually read from some yaml config
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name='your-app-name',
    )
    
    tracer = config.initialize_tracer()
    log_endpoint = 'http://cn-hangzhou.log.aliyuncs.com/'
    access_id = ''
    access_key = ''
    log_project =  ''
    log_logstore =  ''
    reporter = AliLogReporter(log_endpoint, access_id, access_key, log_project, log_logstore) 
    tracer.reporter = reporter
    
    time.sleep(1)
    with tracer.start_span('TestSpan') as span:
        span.log_event('test message 111', payload={'life': 111})
        span.log_event('test message 222', payload={'life': 222})
    
        time.sleep(1)
        with tracer.start_span('ChildSpan', child_of=span) as child_span:
            time.sleep(1)
            child_span.log_event('down below 111')
            child_span.log_event('down below 222')
            child_span.error("make a error", ["error info"])
    
    with tracer.start_span('NextSpan') as xspan:
        xspan.error("error again")
        time.sleep(0.4)
    
    reporter.flush()  # flush any buffered spans




## Use In Aliyun FC

```
1. install required package in local machine
   mkdir /tmp/code
   cd /tmp/code
   pip install -t . jaeger-client
   pip install -U -t . aliyun-log-python-sdk

2. put code into /tmp/code
   cp ali_log_reporter.py /tmp/code/
   cp sample_for_fc.py  /tmp/code
  
3. set ali log service required parameter in sample_for_fc.py
	log_endpoint 
	access_id
	access_key
	log_project
	log_logstore

4. config Fc use fcli : 
	https://help.aliyun.com/document_detail/52995.html?spm=5176.doc56316.2.21.Gj7iyd
	
5. use fcli to creat fc function
	https://help.aliyun.com/document_detail/56316.html?spm=5176.doc52995.6.591.fK3YPp
	./fcli shell
	>>> mks tracing    # create a service named tracing
	>>> cd tracing
	>>> mkf sls-tracing -h sample_for_fc.handler --runtime python2.7 -d  /tmp/code/   # create a function 
	>>> invk sls-tracing  # invoke function

```

