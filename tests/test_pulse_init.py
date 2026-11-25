import json
import os
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.baggage import get_all
from opentelemetry.context import Context, attach, detach, get_current
from opentelemetry.util._once import Once
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
