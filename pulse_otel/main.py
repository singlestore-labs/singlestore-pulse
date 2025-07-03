import functools
import os
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import agent, tool
from opentelemetry import _logs

from opentelemetry.context import attach, set_value
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

from functools import wraps
import uuid
import logging
from typing import Callable
import typing

from pulse_otel.util import (
	get_environ_vars, 
	form_otel_collector_endpoint, 
	_is_endpoint_reachable,
	add_session_id_to_span_attributes,
	)
from pulse_otel.consts import (
	LOCAL_TRACES_FILE,
	LOCAL_LOGS_FILE,
	SESSION_ID,
	HEADER_INCOMING_SESSION_ID,
	PROJECT,
	LIVE_LOGS_FILE_PATH,
)
import logging

_pulse_instance = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Pulse:
	def __init__(
		self,
		write_to_file: bool = False,
		write_to_traceloop: bool = False,
		api_key: str = None,
		otel_collector_endpoint: str = None,
		only_live_logs: bool = False,
	):
		"""
		Initializes the main class with configuration for logging and tracing.

		Args:
			write_to_file (bool): Determines whether to write logs and traces to a file. 
								  If False, logs and traces are sent to an OpenTelemetry collector.
								  Defaults to False.This mode is for local development.
			write_to_traceloop (bool): Determines whether to send logs and traces to Traceloop.
			api_key (str): The API key for Traceloop. Required if `write_to_traceloop` is True.
			otel_collector_endpoint (str): The endpoint for the OpenTelemetry collector. 
			only_live_logs (bool): If True, only live logs are captured and sent to a JSONL file.
								   This is useful for debugging and development purposes.

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

		global _pulse_instance

		if _pulse_instance is not None:
			logger.info("Pulse instance already exists. Skipping initialization.")
			# Copy the existing instance's attributes to this instance
			self.__dict__.update(_pulse_instance.__dict__)
			return

		try:
			self.config = get_environ_vars()
			if write_to_traceloop and api_key:
				log_exporter = self.init_log_provider()

				Traceloop.init(
					disable_batch=True,
					resource_attributes=self.config,
					api_key=api_key,
					logging_exporter=log_exporter,
				)

			elif write_to_file:

				log_exporter = self.init_log_provider()
				Traceloop.init(
					disable_batch=True,
					exporter=CustomFileSpanExporter(LOCAL_TRACES_FILE),
					resource_attributes=self.config,
					logging_exporter=log_exporter,
				)
			elif only_live_logs:
				# create json log exporter for live logs
				jsonl_file_exporter = get_jsonl_file_exporter()
				if jsonl_file_exporter is not None:
					log_provider = LoggerProvider()
					_logs.set_logger_provider(log_provider)
					log_provider.add_log_record_processor(SimpleLogRecordProcessor(jsonl_file_exporter))
					logging.basicConfig(level=logging.INFO, handlers=[LoggingHandler()])
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

				# create json log exporter for live logs
				jsonl_file_exporter = get_jsonl_file_exporter()
				if jsonl_file_exporter is not None:
					log_provider.add_log_record_processor(SimpleLogRecordProcessor(jsonl_file_exporter))

				if not _is_endpoint_reachable(otel_collector_endpoint):
					logger.warning(f"Warning: OTel collector endpoint {otel_collector_endpoint} is not reachable. Please enable Pulse Tracing or contact the support team for more assistance.")
					return

				log_exporter = OTLPLogExporter(endpoint=otel_collector_endpoint)
				log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

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
					telemetry_enabled=False,
				)
		except Exception as e:
			logger.error(f"Error initializing Pulse: {e}")
		
		# Set the global instance
		_pulse_instance = self
		logger.info("Pulse initialized successfully.")

	def enable_content_tracing(self, enabled: bool = True):
		"""
		Enables or disables content tracing by attaching a context variable.
		Sets a key called override_enable_content_tracing in the OpenTelemetry context to True right before 
		making the LLM call you want to trace with prompts. This will create a new context that will instruct instrumentations to log prompts and completions as span attributes.

		Args:
			enabled (bool): A flag to enable or disable content tracing. Defaults to True.
		"""
		attach(set_value("override_enable_content_tracing", enabled))

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


def pulse_tool(_func=None, *, name=None):
	"""
	Decorator to register a function as a tool. Can be used as @pulse_tool, @pulse_tool("name"), or @pulse_tool(name="name").
	If no argument is passed, uses the function name as the tool name.
	Args:
		_func: The function to be decorated.
		name: Optional name for the tool. If not provided, the function name is used.
	Returns:
		A decorator that registers the function as a tool with the specified name.

	Usage:
		@pulse_tool("my_tool")
		def my_function():
			# Function implementation

		@pulse_tool
		def my_function():
			# Function implementation

		@pulse_tool(name="my_tool")
		def my_function():
			# Function implementation
	"""
	def decorator(func):
		tool_name = name or func.__name__
		decorated_func = tool(tool_name)(func)
		return decorated_func

	if _func is None:
		# Called as @pulse_tool() or @pulse_tool(name="...")
		return decorator
	elif isinstance(_func, str):
		# Called as @pulse_tool("name") - this is actually the old pattern
		# We should handle this for backward compatibility
		def wrapper(func):
			tool_name = _func
			decorated_func = tool(tool_name)(func)
			return decorated_func
		return wrapper
	else:
		# Called as @pulse_tool (without parentheses)
		return decorator(_func)

def pulse_agent(name):
	"""
	A decorator factory that wraps a function with additional tracing and session ID logic.

	Args:
		name (str): The name to be used for the agent decorator.

	Returns:
		function: A decorator that wraps the target function, adding session ID to span attributes
		before invoking the decorated agent function.

	Usage:
		@pulse_agent("my_agent")
		def my_function(...):
			...

		@pulse_agent(name="my_agent")
		def my_function(...):
			...
	"""
	def decorator(func):
		decorated_func = agent(name)(func)

		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			add_session_id_to_span_attributes(**kwargs)
			return decorated_func(*args, **kwargs)

		return wrapper

	return decorator

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
		logger.debug(f"Logging to file: {jsonl_log_file_path}")
		return JSONLFileLogExporter(jsonl_log_file_path)
	logger.debug("No JSON log file provided. Skipping JSON log export.")
	return None

class JSONLFileLogExporter(LogExporter):
	def __init__(self, file_path):
		self.file_path = file_path
		try:
			self.f = open(self.file_path, 'a', encoding='utf-8')
		except Exception as e:
			logger.error(f"Failed to open file {self.file_path}: {e}")
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
			logger.error(f"Failed to write to file {self.file_path}: {e}")
			return LogExportResult.FAILURE

	def shutdown(self):
		if self.f:
			self.f.close()
