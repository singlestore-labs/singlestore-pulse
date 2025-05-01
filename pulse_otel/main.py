import functools
import os

from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import agent, tool
from opentelemetry import _events, _logs, trace

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogExporter, LogExportResult
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from fastapi import Request, Response
from fastapi.responses import JSONResponse

import random
from functools import wraps
import uuid
import logging
from typing import Callable, Any

from pulse_otel.util import get_environ_vars, form_otel_collector_endpoint
from pulse_otel.consts import (
	LOCAL_TRACES_FILE,
	LOCAL_LOGS_FILE,
	SESSION_ID,
	HEADER_INCOMING_SESSION_ID,
	PROJECT
)
import logging

class Pulse:
	def __init__(self, write_to_file: bool = False, write_to_traceloop: bool = False, api_key: str = None):	
		"""
		Initializes the main class with configuration for logging and tracing.

		Args:
			write_to_file (bool): Determines whether to write logs and traces to a file.
								  If False, logs and traces are sent to an OpenTelemetry collector.
								  Defaults to False.
			write_to_traceloop (bool): Determines whether to send logs and traces to Traceloop.
			api_key (str): The API key for Traceloop. Required if `write_to_traceloop` is True.

		Behavior:
			- If `write_to_file` is False:
				- Configures an OpenTelemetry collector endpoint based on the project configuration.
				- Sets up a logger provider and an OTLP log exporter for sending logs.
				- Configures a logging handler with the specified logger provider.
				- Initializes Traceloop with the OTLP span exporter and resource attributes.
			- If `write_to_file` is True:
				- Initializes a custom log provider for file-based logging.
				- Initializes Traceloop with a custom file span exporter and resource attributes.
		"""
		self.config = get_environ_vars()
		if write_to_traceloop and api_key:

			Traceloop.init(
				disable_batch=True, 
				resource_attributes=self.config,
				api_key=api_key,
			)
			
		elif write_to_file:

			log_exporter = self.init_log_provider()
			Traceloop.init(
				disable_batch=True, 
				exporter=CustomFileSpanExporter(LOCAL_TRACES_FILE),
				resource_attributes=self.config,
				logging_exporter=log_exporter
				)
			
		else:

			otel_collector_endpoint = form_otel_collector_endpoint(self.config[str(PROJECT)])
			
			log_provider = LoggerProvider()
			_logs.set_logger_provider(log_provider)
			log_exporter = OTLPLogExporter(endpoint=otel_collector_endpoint)
			log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

			handler = LoggingHandler(level=logging.DEBUG, logger_provider=log_provider)

			logging.basicConfig(level=logging.INFO, handlers=[handler])

			Traceloop.init(
				disable_batch=True, 
				api_endpoint=otel_collector_endpoint,
				resource_attributes=self.config,
				exporter=OTLPSpanExporter(endpoint=otel_collector_endpoint, insecure=True)
			)
            
	def init_log_provider(self):
		"""
		Initializes the log provider and sets up the logging configuration.
		"""
		# Create the log provider and processor
		log_provider = LoggerProvider()
		log_exporter = FileLogExporter(LOCAL_LOGS_FILE)
		log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
	
		# Set the log provider
		_logs.set_logger_provider(log_provider)
	
		logging.basicConfig(level=logging.INFO)
	
		# Create a standard logging handler to bridge stdlib and OTel
		handler = LoggingHandler()
	
		# Use the handler with Python’s standard logging
		logger = logging.getLogger("myapp")
		logger.setLevel(logging.INFO)
		logger.addHandler(handler)
		return log_exporter
            
	def pulse_add_session_id(self, session_id=None, **kwargs):
		"""
		Decorator to set Traceloop association properties for a function.
		
		Parameters:
		- session_id: Optional session_id identifier
		- **kwargs: Any additional association properties
		"""
		def decorator(func):
			def wrapper(*args, **kwargs_inner):

				properties = {}
				if session_id:
					properties["session_id"] = session_id
				properties.update(kwargs)  
				
				# Set the association properties
				Traceloop.set_association_properties(properties)
				return func(*args, **kwargs_inner)
			return wrapper
		return decorator

      
	def add_traceid_header(self, func: Callable) -> Callable:
		@wraps(func)
		async def wrapper(request: Request, *args, **kwargs) -> Response:
			# Generate unique trace ID
			trace_id = str(uuid.uuid4())
			
			# Extract session ID from request headers if present
			session_id = request.headers.get("X-SINGLESTORE-AI-SESSION-ID", "N/A")
			
			try:
				# Execute the original function
				result = await func(request, *args, **kwargs)
				
				# If result is already a Response object
				if isinstance(result, Response):
					result.headers["X-SINGLESTORE-TRACE-ID"] = trace_id
					return result
			
				return JSONResponse(
					content=result,
					headers={"X-SINGLESTORE-TRACE-ID": trace_id}
				)
				
			except Exception as e:
				raise e
				
		return wrapper
	

def pulse_tool(func):
	"""
	A decorator that wraps a given function with a third-party `tool` decorator 
	while preserving the original function's metadata.

	Args:
		func (Callable): The function to be wrapped.

	Returns:
		Callable: The wrapped function with preserved metadata.
	"""
	# Wrap the original function with the third-party decorator
	decorated_func = tool(func)

	# Preserve metadata and return
	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		return decorated_func(*args, **kwargs)

	return wrapper

def pulse_agent(func):
	"""
	A decorator that wraps a function to extract a `singlestore-session-id` from the 
	`baggage` header in the keyword arguments (if present) and associates it with 
	Traceloop properties.

	The decorated function is then wrapped with the `agent` decorator.

	Args:
		func (Callable): The function to be decorated.

	Returns:
		Callable: The wrapped function with additional functionality for handling 
		`singlestore-session-id` and associating it with Traceloop properties.
	"""
	@functools.wraps(func)
	def wrapped(*args, **kwargs):
		session_id = None
		if 'headers' in kwargs:
			headers = kwargs['headers']
			baggage = headers.get('baggage')
			if baggage:
				# baggage header is a comma-separated string of key=value pairs
				# example: baggage: key1=value1;property1;property2, key2 = value2, key3=value3; propertyKey=propertyValue
				parts = [item.strip() for item in baggage.split(',')]
				for part in parts:
					if '=' in part:
						key, value = part.split('=', 1)
						if key.strip() == HEADER_INCOMING_SESSION_ID:
							session_id = value.strip()
							break

		if session_id:
			properties = {SESSION_ID: session_id}
			Traceloop.set_association_properties(properties)
			print(f"[pulse_agent] singlestore-session-id: {session_id}")
		else:
			random_session_id = random.randint(10**15, 10**16 - 1)
			properties = {SESSION_ID: str(random_session_id)}
			Traceloop.set_association_properties(properties)
			print("[pulse_agent] No singlestore-session-id found in baggage.")

		return agent(func)(*args, **kwargs)

	return wrapped


class CustomFileSpanExporter(SpanExporter):
    def __init__(self, file_name):
        self.file_name = file_name

    def export(self, spans):
        with open(self.file_name, "a") as f:
            for span in spans:
                f.write(span.to_json() + "\n")
        return SpanExportResult.SUCCESS


class FileLogExporter(LogExporter):
    def __init__(self, file_name):
        self.file_name = file_name

    def export(self, batch):
        with open(self.file_name, "a") as f:
            for log_data in batch:
                log_record = log_data.log_record  # Access the actual log record
                formatted_log = (
                    f"Timestamp: {log_record.timestamp}, "
                    f"Severity: {log_record.severity_text}, "
                    f"Message: {log_record.body}, "
					f"Span ID : {format(log_record.span_id, '016x')}, "
					f"Trace ID : {format(log_record.trace_id, '016x')}"
                )
                f.write(formatted_log + "\n")
        return LogExportResult.SUCCESS

    def shutdown(self):
        # No specific shutdown logic needed for file-based exporting
        pass
