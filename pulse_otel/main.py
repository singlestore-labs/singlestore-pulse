import functools
import os
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import agent, tool
from opentelemetry import _logs

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler, LogData
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogExporter, LogExportResult, SimpleLogRecordProcessor
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
from typing import Callable
import typing

from pulse_otel.util import get_environ_vars, form_otel_collector_endpoint
from pulse_otel.consts import (
	LOCAL_TRACES_FILE,
	LOCAL_LOGS_FILE,
	SESSION_ID,
	HEADER_INCOMING_SESSION_ID,
	PROJECT,
	LIVE_LOGS_FILE_PATH,
)
import logging

class Pulse:
	def __init__(self, write_to_file: bool = False, write_to_traceloop: bool = False, api_key: str = None, otel_collector_endpoint: str = None):
		"""
		Initializes the main class with configuration for logging and tracing.

		Args:
			write_to_file (bool): Determines whether to write logs and traces to a file. 
								  If False, logs and traces are sent to an OpenTelemetry collector.
								  Defaults to False.This mode is for local development.
			write_to_traceloop (bool): Determines whether to send logs and traces to Traceloop.
			api_key (str): The API key for Traceloop. Required if `write_to_traceloop` is True.
			otel_collector_endpoint (str): The endpoint for the OpenTelemetry collector. 

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
		try:
			self.config = get_environ_vars()
			if write_to_traceloop and api_key:
				log_exporter = self.init_log_provider()

				Traceloop.init(
					disable_batch=True,
					resource_attributes=self.config,
					api_key=api_key,
					logging_exporter=log_exporter
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
				
				if otel_collector_endpoint is None:
					try:
						projectID = self.config[str(PROJECT)]
					except KeyError:
						raise ValueError(f"Project ID '{PROJECT}' not found in configuration.")
					otel_collector_endpoint = form_otel_collector_endpoint(projectID)

				"""
					Use the provided OTLP collector endpoint
					First, a new LoggerProvider is created and set as the global logger provider. This object manages loggers and their configuration for the application. Next, an OTLPLogExporter is instantiated with the given endpoint, which is responsible for sending log records to the OTLP collector. The exporter is wrapped in a BatchLogRecordProcessor, which batches log records for efficient export, and this processor is registered with the logger provider.
				"""
				log_provider = LoggerProvider()
				_logs.set_logger_provider(log_provider)
				log_exporter = OTLPLogExporter(endpoint=otel_collector_endpoint)
				log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

				# create json log exporter for live logs
				jsonl_file_exporter = get_jsonl_file_exporter()
				if jsonl_file_exporter is not None:
					log_provider.add_log_record_processor(SimpleLogRecordProcessor(jsonl_file_exporter))

				"""
					A LoggingHandler is then created, configured to capture logs at the DEBUG level and to use the custom logger provider. The Python logging system is configured via logging.basicConfig to use this handler and to set the root logger’s level to INFO. This means all logs at INFO level or higher will be processed and sent to the OTLP collector, while the handler itself is capable of handling DEBUG logs if needed.
				"""
				handler = LoggingHandler(level=logging.DEBUG, logger_provider=log_provider)

				"""
					In Python logging, both the logger and the handler have their own log levels, and both levels must be satisfied for a log record to be processed and exported.

					1. Handler Level (LoggingHandler(level=logging.DEBUG, ...)):
					This means the handler is willing to process log records at DEBUG level and above (DEBUG, INFO, WARNING, etc.).

					2. Root Logger Level (logging.basicConfig(level=logging.INFO, ...)):
					This sets the minimum level for the root logger. Only log records at INFO level and above will be passed from the logger to the handler.
				"""
				logging.basicConfig(level=logging.INFO, handlers=[handler])

				Traceloop.init(
					disable_batch=True,
					api_endpoint=otel_collector_endpoint,
					resource_attributes=self.config,
					exporter=OTLPSpanExporter(endpoint=otel_collector_endpoint, insecure=True),
					logging_exporter=log_exporter,
				)
		except Exception as e:
			print(f"Error initializing Pulse: {e}")
			

	def init_log_provider(self):
		"""
		Initializes the log provider and sets up the logging configuration.
		"""
		# Create the log provider and processor
		log_provider = LoggerProvider()
		log_exporter = FileLogExporter(LOCAL_LOGS_FILE)
		log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

		# create json log exporter for live logs
		jsonl_file_exporter = get_jsonl_file_exporter()
		if jsonl_file_exporter is not None:
			log_provider.add_log_record_processor(SimpleLogRecordProcessor(jsonl_file_exporter))

		# Set the log provider
		_logs.set_logger_provider(log_provider)

		# Create a standard logging handler to bridge stdlib and OTel
		handler = LoggingHandler()
		logging.root.setLevel(logging.INFO)
		logging.root.addHandler(handler)
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

def get_jsonl_log_file_path():
	"""
	Gets the filename for live logs from env vars
	"""
	return os.getenv(LIVE_LOGS_FILE_PATH)

def get_jsonl_file_exporter():
	"""
	get json log exporter if env var exists and parent director exists
	"""
	jsonl_log_file_path = get_jsonl_log_file_path()
	if jsonl_log_file_path is not None and jsonl_log_file_path != "" and os.path.exists(os.path.dirname(jsonl_log_file_path)):
		print(f"Logging to file: {jsonl_log_file_path}")
		return JSONLFileLogExporter(jsonl_log_file_path)
	print("No JSON log file provided. Skipping JSON log export.")
	return None


class JSONLFileLogExporter(LogExporter):
	def __init__(self, file_path):
		self.file_path = file_path
		try:
			self.f = open(self.file_path, 'a', encoding='utf-8')
		except Exception as e:
			print(f"Failed to open file {self.file_path}: {e}")
			self.f = None

	def export(self, batch: typing.Sequence[LogData]) -> LogExportResult:
		if self.f is None:
			return LogExportResult.FAILURE
		try:
			for r in batch:
				self.f.write(r.log_record.to_json(None) + '\n')
				self.f.flush()
			return LogExportResult.SUCCESS
		except Exception as e:
			print(f"Failed to write to file {self.file_path}: {e}")
			return LogExportResult.FAILURE

	def shutdown(self):
		if self.f:
			self.f.close()
