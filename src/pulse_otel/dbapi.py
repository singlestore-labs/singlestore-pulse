"""DB-API instrumentation that keeps the client span without the statement.

The upstream instrumentation always writes the full SQL text to db.statement,
and exposes no option to suppress it, so a content-less destination would
receive every statement a query runs against customer data. These proxies reuse
the upstream classes and drop that one attribute.
"""

from __future__ import annotations

from typing import Any, Generic

from opentelemetry.instrumentation.dbapi import (
    ConnectionT,
    CursorT,
    CursorTracer,
    DatabaseApiIntegration,
    TracedConnectionProxy,
    TracedCursorProxy,
)
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Span, TracerProvider

from pulse_otel.util import is_content_allowed


class _StatementRedactingCursorTracer(CursorTracer[CursorT], Generic[CursorT]):
    def _populate_span(self, span: Span, cursor: CursorT, *args: tuple[Any, ...]) -> None:
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


class _StatementRedactingCursorProxy(TracedCursorProxy[CursorT], Generic[CursorT]):
    def __init__(self, cursor: CursorT, db_api_integration: DatabaseApiIntegration) -> None:
        super().__init__(cursor, db_api_integration)
        self._self_cursor_tracer = _StatementRedactingCursorTracer[CursorT](db_api_integration)


class _StatementRedactingConnectionProxy(TracedConnectionProxy[ConnectionT], Generic[ConnectionT]):
    def cursor(self, *args: Any, **kwargs: Any) -> _StatementRedactingCursorProxy[Any]:
        return _StatementRedactingCursorProxy(
            self.__wrapped__.cursor(*args, **kwargs),
            self._self_db_api_integration,
        )


def instrument_db_connection(
    connection: ConnectionT,
    database_system: str = "mysql",
    name: str = "pulse_otel",
    version: str = "",
    tracer_provider: TracerProvider | None = None,
) -> TracedConnectionProxy[ConnectionT]:
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
        tracer_provider: Provider to record spans on. Defaults to the global one.

    Returns:
        The instrumented connection.
    """
    integration = DatabaseApiIntegration(name, database_system, version=version, tracer_provider=tracer_provider)
    integration.get_connection_attributes(connection)
    return _StatementRedactingConnectionProxy(connection, integration)
