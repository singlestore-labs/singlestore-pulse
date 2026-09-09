"""DB-API instrumentation that keeps the client span without the statement.

The upstream instrumentation always writes the full SQL text to db.statement,
and exposes no option to suppress it, so a content-less destination would
receive every statement a query runs against customer data. These proxies reuse
the upstream classes and drop that one attribute.
"""

from typing import Any

from opentelemetry.instrumentation.dbapi import (
    CursorTracer,
    DatabaseApiIntegration,
    TracedConnectionProxy,
    TracedCursorProxy,
)
from opentelemetry.semconv.trace import SpanAttributes

from pulse_otel.util import is_content_allowed


class _StatementRedactingCursorTracer(CursorTracer):
    def _populate_span(self, span: Any, cursor: Any, *args: tuple[Any, ...]) -> None:
        if is_content_allowed():
            super()._populate_span(span, cursor, *args)
            return
        if not span.is_recording():
            return
        # Everything upstream records except the statement. The operation is
        # already the span name, so nothing is lost by leaving db.statement unset.
        span.set_attribute(SpanAttributes.DB_SYSTEM, self._db_api_integration.database_system)
        span.set_attribute(SpanAttributes.DB_NAME, self._db_api_integration.database)
        for key, value in self._db_api_integration.span_attributes.items():
            span.set_attribute(key, value)


class _StatementRedactingCursorProxy(TracedCursorProxy):
    def __init__(self, cursor: Any, db_api_integration: DatabaseApiIntegration):
        super().__init__(cursor, db_api_integration)
        self._self_cursor_tracer = _StatementRedactingCursorTracer(db_api_integration)


class _StatementRedactingConnectionProxy(TracedConnectionProxy):
    def cursor(self, *args: Any, **kwargs: Any):
        return _StatementRedactingCursorProxy(
            self.__wrapped__.cursor(*args, **kwargs),
            self._self_db_api_integration,
        )


def instrument_db_connection(
    connection: Any,
    database_system: str = "mysql",
    name: str = "pulse_otel",
    version: str = "",
) -> Any:
    """
    Instruments a DB-API connection so each query emits a client span.

    The span carries the operation as its name, plus the database and server
    attributes. db.statement is set only where content is allowed, so timing and
    error rates survive on a content-less destination while the query text does
    not leave the process.

    Args:
        connection: The DB-API connection to instrument.
        database_system: Identifier for the database system, e.g. "mysql".
        name: Instrumentation module name.
        version: Instrumentation module version.

    Returns:
        The instrumented connection.
    """
    integration = DatabaseApiIntegration(name, database_system, version=version)
    integration.get_connection_attributes(connection)
    return _StatementRedactingConnectionProxy(connection, integration)
