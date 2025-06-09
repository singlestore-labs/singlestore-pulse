import functools
import os
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import agent, tool
from opentelemetry import _logs, trace


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

from contextvars import copy_context

from functools import wraps
import logging
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
	PROJECT,
	LIVE_LOGS_FILE_PATH,
)
import logging

logger = logging.getLogger(__name__)

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

def s2_agent1(name):
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			ctx = copy_context()
			trace_callback = kwargs.pop("trace_callback", None)  # Accept optional callback

			async def async_wrapper():
				add_session_id_to_span_attributes(**kwargs)
				tracer = trace.get_tracer(__name__)
				
				with tracer.start_as_current_span(name) as span:
					trace_id_hex = format(span.get_span_context().trace_id, "032x")
					logger.debug(f"[s2_agent wrapper] Started span. TraceID: {trace_id_hex}")
					
					if trace_callback:
						trace_callback(trace_id_hex)  # Notify the caller

					decorated_func = agent(name)(func)
					async for item in decorated_func(*args, **kwargs):
						yield item

			return ctx.run(async_wrapper)
		return wrapper
	return decorator

def healthcheckpulse():
	return {
		"status": "ok",
		"message": "Pulse is running",
		"version": "1.0.0",
	}
