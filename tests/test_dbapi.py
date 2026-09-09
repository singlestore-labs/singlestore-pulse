import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pulse_otel import instrument_db_connection, util

STATEMENT = "SELECT name FROM customers WHERE email = 'a@b.com'"


class FakeCursor:
    def execute(self, *args, **kwargs):
        return None

    def close(self):
        return None


class FakeConnection:
    def cursor(self, *args, **kwargs):
        return FakeCursor()


@pytest.fixture
def exporter():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


def _execute_and_read_statement(exporter):
    conn = instrument_db_connection(FakeConnection(), "mysql")
    conn.cursor().execute(STATEMENT)
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    return spans[0]


class TestInstrumentDbConnection:
    def test_omits_the_statement_when_content_is_not_allowed(self, exporter, mocker):
        mocker.patch.object(util, "_content_allowed", False)

        span = _execute_and_read_statement(exporter)

        assert "db.statement" not in span.attributes
        assert span.attributes["db.system"] == "mysql"
        assert span.name == "SELECT"

    def test_keeps_the_statement_when_content_is_allowed(self, exporter, mocker):
        mocker.patch.object(util, "_content_allowed", True)

        span = _execute_and_read_statement(exporter)

        assert span.attributes["db.statement"] == STATEMENT
