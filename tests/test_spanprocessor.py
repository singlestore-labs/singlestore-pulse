import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from opentelemetry.baggage import set_baggage
from opentelemetry.context import Context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pulse_otel import (
    BAGGAGE_API_KEY,
    BAGGAGE_DOMAIN,
    BAGGAGE_NEXUS_ID,
    BAGGAGE_NOVA_ID,
    BAGGAGE_ORG,
    BAGGAGE_PROJECT,
    BAGGAGE_SESSION,
    BAGGAGE_TURN,
    BaggageSpanProcessor,
)

POD_ENV = {
    "SINGLESTOREDB_ORGANIZATION": "env-org",
    "SINGLESTOREDB_PROJECT": "env-proj",
    "SINGLESTOREDB_NEXUS_APP_ID": "env-nexus",
    "SINGLESTOREDB_NEXUS_APP_TYPE": "AuraAnalyst",
    "SINGLESTOREDB_APP_ID": "env-nova",
    "SINGLESTOREDB_APP_TYPE": "AGENT",
    "SINGLESTOREDB_APP_NAME": "sqlbot",
}

ENV_IDENTITY_ATTRS = {
    "singlestore.org.id": "env-org",
    "singlestore.organization": "env-org",
    "org.id": "env-org",
    "singlestore.project.id": "env-proj",
    "singlestore.project": "env-proj",
    "project.id": "env-proj",
    "singlestore.nexus.app.id": "env-nexus",
    "singlestore.nexus.app.type": "AuraAnalyst",
    "singlestore.nova.app.id": "env-nova",
    "singlestore.nova.app.type": "AGENT",
    "singlestore.nova.app.name": "sqlbot",
}

REQUEST_ATTRS = (
    "singlestore.domain.id",
    "session.id",
    "singlestore.api_key.id",
    "turn.id",
)


def _new_tracer():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(BaggageSpanProcessor())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


def _span_attrs(tracer, exporter, context):
    with tracer.start_as_current_span("op", context=context):
        pass
    (span,) = exporter.get_finished_spans()
    return dict(span.attributes)


def _baggage(**members):
    ctx = Context()
    for key, value in members.items():
        ctx = set_baggage(key, value, context=ctx)
    return ctx


@patch.dict(os.environ, {}, clear=True)
def test_request_baggage_is_stamped_on_span():
    tracer, exporter = _new_tracer()
    ctx = _baggage(
        **{
            BAGGAGE_API_KEY: "key-1",
            BAGGAGE_TURN: "turn-1",
            BAGGAGE_DOMAIN: "dom-1",
            BAGGAGE_SESSION: "sess-1",
        }
    )

    attrs = _span_attrs(tracer, exporter, ctx)

    assert attrs["singlestore.api_key.id"] == "key-1"
    assert attrs["turn.id"] == "turn-1"
    assert attrs["singlestore.domain.id"] == "dom-1"
    assert attrs["session.id"] == "sess-1"
    assert attrs["gen_ai.conversation.id"] == "sess-1"
    assert attrs["traceloop.association.properties.session.id"] == "sess-1"


@patch.dict(os.environ, POD_ENV, clear=True)
def test_env_identity_fills_span_when_baggage_is_empty():
    tracer, exporter = _new_tracer()

    attrs = _span_attrs(tracer, exporter, Context())

    assert ENV_IDENTITY_ATTRS.items() <= attrs.items()
    assert not set(REQUEST_ATTRS) & attrs.keys()


@patch.dict(os.environ, POD_ENV, clear=True)
def test_baggage_member_wins_over_env():
    tracer, exporter = _new_tracer()
    ctx = _baggage(
        **{
            BAGGAGE_ORG: "bag-org",
            BAGGAGE_PROJECT: "bag-proj",
            BAGGAGE_NEXUS_ID: "bag-nexus",
            BAGGAGE_NOVA_ID: "bag-nova",
        }
    )

    attrs = _span_attrs(tracer, exporter, ctx)

    assert attrs["singlestore.org.id"] == "bag-org"
    assert attrs["singlestore.project.id"] == "bag-proj"
    assert attrs["singlestore.nexus.app.id"] == "bag-nexus"
    assert attrs["singlestore.nova.app.id"] == "bag-nova"
    # Members missing from baggage still come from the env.
    assert attrs["singlestore.nexus.app.type"] == "AuraAnalyst"
    assert attrs["singlestore.nova.app.name"] == "sqlbot"


@patch.dict(os.environ, {}, clear=True)
def test_no_baggage_and_no_env_stamps_nothing():
    tracer, exporter = _new_tracer()

    attrs = _span_attrs(tracer, exporter, Context())

    assert attrs == {}


@patch.dict(os.environ, POD_ENV, clear=True)
def test_processor_made_in_one_thread_stamps_span_started_in_another():
    with ThreadPoolExecutor(max_workers=1) as pool:
        tracer, exporter = pool.submit(_new_tracer).result()
    with ThreadPoolExecutor(max_workers=1) as pool:
        attrs = pool.submit(_span_attrs, tracer, exporter, None).result()

    assert ENV_IDENTITY_ATTRS.items() <= attrs.items()
