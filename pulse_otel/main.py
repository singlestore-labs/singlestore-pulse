import functools
import os
import logging
import typing
import time
import inspect

from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import agent, tool

from opentelemetry import _logs
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind
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
from opentelemetry.trace import TracerProvider
from opentelemetry.sdk.trace import export, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from fastapi import Request


from pulse_otel.util import (
	get_environ_vars,
	form_otel_collector_endpoint,
	_is_endpoint_reachable,
	add_session_id_to_span_attributes,
	set_global_content_tracing,
	is_s2_owned_app,
	get_internal_collector_endpoint,
	is_force_content_tracing_enabled,
	set_span_attribute_size_limit
	)
from pulse_otel.consts import (
	LOCAL_TRACES_FILE,
	LOCAL_LOGS_FILE,
	PROJECT,
	LIVE_LOGS_FILE_PATH,
)
import logging

_pulse_instance = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tracer = trace.get_tracer(__name__)

class Pulse:
	def __init__(
		self,
		write_to_file: bool = False,
		write_to_traceloop: bool = False,
		api_key: str = None,
		otel_collector_endpoint: str = None,
		only_live_logs: bool = False,
		enable_trace_content=True,
		without_traceloop: bool = False,
		telemetry_enabled: bool = False,
		span_attribute_size_limit: int = 4 * 1024,
	):
		"""
		Initializes the Pulse class with configuration for logging and tracing.

		Args:
			write_to_file (bool): If True, writes traces and logs to local files. Used for local development.
			write_to_traceloop (bool): If True, sends traces and logs to Traceloop using the provided API key.
			api_key (str): API key for Traceloop. Required if `write_to_traceloop` is True.
			otel_collector_endpoint (str): Endpoint for the OpenTelemetry collector. Used if sending data to OTLP.
			only_live_logs (bool): If True, only live logs are captured and sent to a JSONL file.
			enable_trace_content (bool): If True, enables content tracing for spans.
			without_traceloop (bool): If True, disables Traceloop integration and uses OTLP or file exporters directly.
			telemetry_enabled (bool): If True, enables telemetry and sends traces/logs to the internal Pulse OTLP collector. Also it disables content tracing.

		Behavior:
			- If a Pulse instance already exists, reuses its configuration.
			- Sets up content tracing based on `enable_trace_content`.
			- If `write_to_traceloop` and `api_key` are provided, initializes Traceloop with log exporter.
			- If `write_to_file` and not `without_traceloop`, initializes Traceloop with custom file span exporter and log exporter.
			- If `only_live_logs`, sets up a JSONL log exporter for live logs.
			- If `without_traceloop` and `otel_collector_endpoint` is provided, sets up OTLP span exporter and optional file exporter.
			- If none of the above, determines OTLP collector endpoint (internal or external), sets up OTLP log exporter and Traceloop with OTLP span exporter.
			- Handles endpoint reachability and logs warnings if the OTLP collector is not reachable.
			- Always sets up appropriate logger providers, log processors, and handlers for OpenTelemetry logging.
		"""
		start_time = time.time()
		
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
				set_global_content_tracing(False)

				Traceloop.init(
					disable_batch=True,
					resource_attributes=self.config,
					api_key=api_key,
					logging_exporter=log_exporter,
					telemetry_enabled=False,
				)

			elif write_to_file and not without_traceloop:
				set_global_content_tracing(enable_trace_content and not telemetry_enabled)

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
					logging.root.addHandler(LoggingHandler()) # add filehandler to root logger
			elif without_traceloop and otel_collector_endpoint is not None:
				
				resource = Resource(attributes={
					SERVICE_NAME: "Pulse_OTel_Service",
				})
				provider = TracerProvider(resource=resource)
				exporter = OTLPSpanExporter(endpoint=otel_collector_endpoint, insecure=True)

				if write_to_file:
					logger.info(f"Writing traces to file: {LOCAL_TRACES_FILE}")
					exporter = CustomFileSpanExporter(LOCAL_TRACES_FILE)

				span_processor = BatchSpanProcessor(exporter)
				provider.add_span_processor(span_processor)
				trace.set_tracer_provider(provider)

				# Optional instrumentation for logging, requests, grpc, etc.
				LoggingInstrumentor().instrument(set_logging_format=True)
				RequestsInstrumentor().instrument()


			else:
				if is_force_content_tracing_enabled():
					logger.info("[PULSE] Force content tracing is enabled. Traces will be sent to project specific OpenTelemetry collector and Content Tracing will be enabled.")
					set_span_attribute_size_limit(span_attribute_size_limit)
				elif telemetry_enabled or is_s2_owned_app():
					if telemetry_enabled:
						logger.info("[PULSE] Telemetry enabled. Traces and logs will be sent to the Pulse Internal OpenTelemetry collector and Content Tracing will be disabled.")
					else:
						logger.info("[PULSE] S2 owned app detected. Traces and logs will be sent to the Pulse Internal OpenTelemetry collector and Content Tracing will be disabled.")

					set_global_content_tracing(False)
					otel_collector_endpoint = get_internal_collector_endpoint()

				if otel_collector_endpoint is None:
					try:
						projectID = self.config[str(PROJECT)]
					except KeyError:
						raise ValueError(f"Project ID '{PROJECT}' not found in configuration.")
					otel_collector_endpoint = form_otel_collector_endpoint(projectID)
				
				logger.info(f"[PULSE] Using OpenTelemetry collector endpoint: {otel_collector_endpoint}")

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

				# if not _is_endpoint_reachable(otel_collector_endpoint):
				# 	logger.warning(f"Warning: OTel collector endpoint {otel_collector_endpoint} is not reachable. Please enable Pulse Tracing or contact the support team for more assistance.")
				# 	return

				log_exporter = OTLPLogExporter(endpoint=otel_collector_endpoint)
				log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

				"""
					A LoggingHandler is then created, configured to capture logs at the DEBUG level and to use the custom logger provider. The Python logging system is configured via logging.basicConfig to use this handler and to set the root logger’s level to INFO. This means all logs at INFO level or higher will be processed and sent to the OTLP collector, while the handler itself is capable of handling DEBUG logs if needed.
				"""
				handler = LoggingHandler(level=logging.DEBUG, logger_provider=log_provider)
				logging.root.addHandler(handler)

				"""
					In Python logging, both the logger and the handler have their own log levels, and both levels must be satisfied for a log record to be processed and exported.

					1. Handler Level (LoggingHandler(level=logging.DEBUG, ...)):
					This means the handler is willing to process log records at DEBUG level and above (DEBUG, INFO, WARNING, etc.).

					2. Root Logger Level (logging.basicConfig(level=logging.INFO, ...)):
					This sets the minimum level for the root logger. Only log records at INFO level and above will be passed from the logger to the handler.
				"""
				logging.basicConfig(level=logging.INFO)

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
		end_time = time.time()
		logger.info(f"Pulse initialized successfully in {end_time - start_time:.2f} seconds.")

	@staticmethod
	def enable_content_tracing(enabled: bool = True):
		"""
		Enables or disables content tracing by attaching a context variable.
		Sets a key called override_enable_content_tracing in the OpenTelemetry context to True right before
		making the LLM call you want to trace with prompts. This will create a new context that will instruct instrumentations to log prompts and completions as span attributes.

		Args:
			enabled (bool): A flag to enable or disable content tracing. Defaults to True.
		"""
		attach(set_value("override_enable_content_tracing", enabled))

	@staticmethod
	def reset_span_attribute_size_limit():
		if 'OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT' in os.environ:
			del os.environ['OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT']

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

def traced_function(func):
	"""
	This is for internal testing purposes only. It wraps a function with OpenTelemetry tracing without Traceloop.
	"""
	if inspect.iscoroutinefunction(func):
		@functools.wraps(func)
		async def async_wrapper(*args, **kwargs):
			with tracer.start_as_current_span(func.__name__) as span:
				span.set_attribute("args", str(args))
				span.set_attribute("kwargs", str(kwargs))
				return await func(*args, **kwargs)
		return async_wrapper
	else:
		@functools.wraps(func)
		def sync_wrapper(*args, **kwargs):
			with tracer.start_as_current_span(func.__name__) as span:
				span.set_attribute("args", str(args))
				span.set_attribute("kwargs", str(kwargs))
				return func(*args, **kwargs)
		return sync_wrapper

def pulse_tool(_func=None, *, name=None, enable_content_tracing=True):
	"""
	Decorator to register a function as a tool. Can be used as @pulse_tool, @pulse_tool("name"), or @pulse_tool(name="name").
	If no argument is passed, uses the function name as the tool name.
	Args:
		_func: The function to be decorated.
		name: Optional name for the tool. If not provided, the function name is used.
		enable_content_tracing: Whether to enable content tracing for this tool. Defaults to False.
	Returns:
		A decorator that registers the function as a tool with the specified name.

	Usage:
		@pulse_tool("my_tool")
		def my_function():
			# Function implementation

		@pulse_tool
		def my_function():
			# Function implementation

		@pulse_tool(name="my_tool", enable_content_tracing=True)
		def my_function():
			# Function implementation
	"""
	def decorator(func):
		tool_name = name or func.__name__
		decorated_func = tool(tool_name)(func)
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			Pulse.enable_content_tracing(enable_content_tracing)
			return decorated_func(*args, **kwargs)
		return wrapper

	if _func is None:
		# Called as @pulse_tool() or @pulse_tool(name="...", enable_content_tracing=...)
		return decorator
	elif isinstance(_func, str):
		# Called as @pulse_tool("name") - this is actually the old pattern
		# We should handle this for backward compatibility
		def wrapper(func):
			tool_name = _func
			decorated_func = tool(tool_name)(func)
			@functools.wraps(func)
			def inner_wrapper(*args, **kwargs):
				Pulse.enable_content_tracing(enable_content_tracing)
				return decorated_func(*args, **kwargs)
			return inner_wrapper
		return wrapper
	else:
		# Called as @pulse_tool (without parentheses)
		return decorator(_func)

def pulse_agent(name, enable_content_tracing=True):
	"""
	A decorator factory that wraps a function with additional tracing and session ID logic.

	Args:
		name (str): The name to be used for the agent decorator.
		enable_content_tracing (bool): Whether to enable content tracing for this agent. Defaults to False.

	Returns:
		function: A decorator that wraps the target function, adding session ID to span attributes
		before invoking the decorated agent function.

	Usage:
		@pulse_agent("my_agent")
		def my_function(...):
			...

		@pulse_agent(name="my_agent", enable_content_tracing=True)
		def my_function(...):
			...
	"""
	def decorator(func):
		decorated_func = agent(name)(func)

		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			add_session_id_to_span_attributes(**kwargs)
			Pulse.enable_content_tracing(enable_content_tracing)
			return decorated_func(*args, **kwargs)

		return wrapper

	return decorator


def observe(name):
	"""
	A decorator factory that instruments a function for observability using opentelemetry tracing.
	Args:
		name (str): The name of the span to be created for tracing.
	Returns:
		Callable: A decorator that wraps the target function, extracting opentelemetry tracing context
		from the incoming request (if available), and starts a new tracing span using
		the provided name. If no context is found, a new span is started without context.
	Behavior:
		- Adds session ID to span attributes if available in kwargs.
		- Attempts to extract a tracing context from the 'request' argument or from positional arguments.
		- Starts a tracing span with the extracted context (if present) or as a new trace.
		- Logs debug information about the tracing context and span creation.
		- Supports usage both within and outside of HTTP request contexts.
	Example:
		@observe("my_function_span")
		def my_function(request: Request, ...):
			...
	"""
	def decorator(func):
		decorated_func = agent(name)(func)
		logger.debug("Decorating function with observe:", name)

		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			add_session_id_to_span_attributes(**kwargs)
			request: Request = kwargs.get("request")
			if request is None:
				for arg in args:
					if isinstance(arg, Request):
						request = arg
						break

			# Extract context from request if available
			ctx = extract(request.headers) if request else None

			if ctx:
				logger.debug(f"Starting span with context: {ctx}")
				# Start span with context
				with tracer.start_as_current_span(name, context=ctx, kind=SpanKind.SERVER):
					return decorated_func(*args, **kwargs)
			else:
				logger.debug("No context found, starting span without context.")
				
				# Start span without context
				# This is useful for cases where we want to start a span without any specific context
				# e.g., when the function is called outside of an HTTP request context
				# or when we want to create a fresh new trace or context is not properly propagated.
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

def setup_json_file_logger():
	"""
	Sets up logging to a JSONL file using OpenTelemetry if the exporter is available.
	"""
	jsonl_file_exporter = get_jsonl_file_exporter()
	if jsonl_file_exporter is not None:
		logger_provider = LoggerProvider()
		logger_provider.add_log_record_processor(SimpleLogRecordProcessor(jsonl_file_exporter))
		log_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
		logging.root.addHandler(log_handler)
		return logger_provider, log_handler
	return None, None

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
