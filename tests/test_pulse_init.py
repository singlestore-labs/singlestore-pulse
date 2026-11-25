import json
import logging
import os
import statistics
import time
from concurrent import futures
from unittest.mock import patch

import grpc
import pytest
from opentelemetry import trace
from opentelemetry.baggage import get_all
from opentelemetry.context import Context, attach, detach, get_current
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc
from opentelemetry.util._once import Once
from traceloop.sdk import Traceloop
from traceloop.sdk.tracing import tracing as traceloop_tracing

from pulse_otel import Pulse

POD_ENV = {"SINGLESTOREDB_ORGANIZATION": "env-org", "SINGLESTOREDB_PROJECT": "env-proj"}


def _exported_spans(path):
    decoder, text, spans = json.JSONDecoder(), path.read_text().strip(), []
    while text:
        span, end = decoder.raw_decode(text)
        spans.append(span)
        text = text[end:].lstrip()
    return spans


def _drop_traceloop_wrapper():
    wrapper = traceloop_tracing.TracerWrapper.__dict__.get("instance")
    if wrapper is not None:
        del traceloop_tracing.TracerWrapper.instance
    return wrapper


@pytest.fixture
def fresh_tracing(monkeypatch, tmp_path):
    # OTel sets the global tracer provider once per process, and Traceloop keeps one wrapper.
    monkeypatch.setattr(trace, "_TRACER_PROVIDER_SET_ONCE", Once())
    monkeypatch.setattr(trace, "_TRACER_PROVIDER", None)
    monkeypatch.chdir(tmp_path)
    # Real instrumentation would patch installed libraries for the rest of the session.
    monkeypatch.setattr(traceloop_tracing, "init_instrumentations", lambda *args, **kwargs: None)
    previous_wrapper = _drop_traceloop_wrapper()
    token = attach(Context())
    yield tmp_path
    detach(token)
    _drop_traceloop_wrapper()
    if previous_wrapper is not None:
        traceloop_tracing.TracerWrapper.instance = previous_wrapper


def test_span_started_while_traceloop_loads_instrumentations_gets_env_identity(fresh_tracing, monkeypatch):
    def start_span_during_init(*args, **kwargs):
        with trace.get_tracer("startup").start_as_current_span("startup-health-check"):
            pass

    monkeypatch.setattr(traceloop_tracing, "init_instrumentations", start_span_during_init)

    with patch.dict(os.environ, POD_ENV):
        Pulse(write_to_file=True)

    (span,) = [s for s in _exported_spans(fresh_tracing / "pulse_traces.json") if s["name"] == "startup-health-check"]
    assert span["attributes"]["singlestore.org.id"] == "env-org"
    assert span["attributes"]["singlestore.project.id"] == "env-proj"


def test_traceloop_tracing_disabled_leaves_no_global_provider(fresh_tracing):
    with patch.dict(os.environ, {**POD_ENV, "TRACELOOP_TRACING_ENABLED": "false"}):
        Pulse(write_to_file=True)

    assert isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider)


def test_pulse_leaves_the_callers_context_without_identity_baggage(fresh_tracing):
    with patch.dict(os.environ, POD_ENV):
        Pulse(write_to_file=True)

    assert get_all(get_current()) == {}


UNREACHABLE_COLLECTORS = {
    "refuses_connections": "http://127.0.0.1:1",
    "drops_packets": "http://10.255.255.1:4317",
}


class _Collector(trace_service_pb2_grpc.TraceServiceServicer):
    def __init__(self):
        self.spans = {}

    def Export(self, request, context):
        for resource_spans in request.resource_spans:
            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    self.spans[span.name] = {a.key: a.value.string_value for a in span.attributes}
        return trace_service_pb2.ExportTraceServiceResponse()


@pytest.fixture
def collector():
    servicer = _Collector()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    yield f"http://127.0.0.1:{port}", servicer
    server.stop(0)


@pytest.fixture
def otlp_tracing(fresh_tracing, monkeypatch):
    # The OTLP path adds a root log handler and a tracer provider with export threads.
    # The log exporter keeps the 10 s OTel default timeout, which would slow each teardown.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_TIMEOUT", "1")
    handlers = list(logging.root.handlers)
    yield
    trace.get_tracer_provider().shutdown()
    for handler in set(logging.root.handlers) - set(handlers):
        logging.root.removeHandler(handler)
        provider = getattr(handler, "_logger_provider", None)
        if provider is not None:
            provider.shutdown()


@pytest.mark.parametrize("endpoint", UNREACHABLE_COLLECTORS.values(), ids=UNREACHABLE_COLLECTORS.keys())
def test_span_end_does_not_wait_for_an_unreachable_collector(otlp_tracing, endpoint):
    Pulse(otel_collector_endpoint=endpoint, skip_reachability_check=True)
    tracer = trace.get_tracer("request")

    durations = []
    for _ in range(5):
        span = tracer.start_span("request-span")
        started = time.monotonic()
        span.end()
        durations.append(time.monotonic() - started)

    assert statistics.median(durations) < 0.01


@pytest.mark.parametrize(
    ("env", "max_seconds"),
    [
        ({}, 5),
        ({"OTEL_EXPORTER_OTLP_TRACES_TIMEOUT": "1"}, 2),
        ({"OTEL_EXPORTER_OTLP_TIMEOUT": "1"}, 2),
    ],
    ids=["default", "traces_env", "generic_env"],
)
def test_export_to_an_unreachable_collector_gives_up_within_the_timeout(otlp_tracing, monkeypatch, env, max_seconds):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_TIMEOUT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TIMEOUT", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    Pulse(otel_collector_endpoint=UNREACHABLE_COLLECTORS["drops_packets"], skip_reachability_check=True)

    trace.get_tracer("request").start_span("request-span").end()
    started = time.monotonic()
    trace.get_tracer_provider().force_flush()

    assert time.monotonic() - started < max_seconds


def test_spans_reach_a_running_collector(otlp_tracing, collector):
    endpoint, servicer = collector
    Pulse(otel_collector_endpoint=endpoint, skip_reachability_check=True)

    with trace.get_tracer("request").start_as_current_span("reaches-collector"):
        pass
    trace.get_tracer_provider().force_flush()

    assert "reaches-collector" in servicer.spans


def test_traceloop_session_alias_still_reaches_the_collector(otlp_tracing, collector):
    endpoint, servicer = collector
    Pulse(otel_collector_endpoint=endpoint, skip_reachability_check=True)

    Traceloop.set_association_properties({"session.id": "session-1"})
    with trace.get_tracer("request").start_as_current_span("with-session"):
        pass
    trace.get_tracer_provider().force_flush()

    assert servicer.spans["with-session"]["traceloop.association.properties.session.id"] == "session-1"
