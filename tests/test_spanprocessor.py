import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from opentelemetry.baggage import set_baggage
from opentelemetry.context import Context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pulse_otel import (
    BAGGAGE_API_KEY,
    BAGGAGE_DOMAIN,
    BAGGAGE_NEXUS_ID,
    BAGGAGE_NEXUS_TYPE,
    BAGGAGE_NOVA_ID,
    BAGGAGE_NOVA_NAME,
    BAGGAGE_NOVA_TYPE,
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
    "SINGLESTOREDB_WORKLOAD_TYPE": "NotebookCodeService",
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
    "singlestore.nova.app.type": "NotebookCodeService",
    "singlestore.nova.app.name": "sqlbot",
}

REQUEST_ATTRS = ("singlestore.domain.id", "session.id", "singlestore.api_key.id", "turn.id")


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


@pytest.mark.parametrize(
    ("baggage_key", "attr_keys"),
    [
        (BAGGAGE_API_KEY, ["singlestore.api_key.id"]),
        (BAGGAGE_TURN, ["turn.id"]),
        (BAGGAGE_DOMAIN, ["singlestore.domain.id"]),
        (BAGGAGE_SESSION, ["session.id", "gen_ai.conversation.id", "traceloop.association.properties.session.id"]),
    ],
)
@patch.dict(os.environ, {}, clear=True)
def test_request_baggage_member_is_stamped(baggage_key, attr_keys):
    tracer, exporter = _new_tracer()

    attrs = _span_attrs(tracer, exporter, _baggage(**{baggage_key: "from-baggage"}))

    assert {key: attrs.get(key) for key in attr_keys} == dict.fromkeys(attr_keys, "from-baggage")


@pytest.mark.parametrize(
    ("baggage_key", "attr_key"),
    [
        (BAGGAGE_ORG, "singlestore.org.id"),
        (BAGGAGE_PROJECT, "singlestore.project.id"),
        (BAGGAGE_NEXUS_ID, "singlestore.nexus.app.id"),
        (BAGGAGE_NEXUS_TYPE, "singlestore.nexus.app.type"),
        (BAGGAGE_NOVA_ID, "singlestore.nova.app.id"),
        (BAGGAGE_NOVA_TYPE, "singlestore.nova.app.type"),
        (BAGGAGE_NOVA_NAME, "singlestore.nova.app.name"),
    ],
)
@patch.dict(os.environ, POD_ENV, clear=True)
def test_baggage_member_wins_over_env_and_env_fills_the_rest(baggage_key, attr_key):
    tracer, exporter = _new_tracer()

    attrs = _span_attrs(tracer, exporter, _baggage(**{baggage_key: "from-baggage"}))

    assert attrs[attr_key] == "from-baggage"
    assert {k: v for k, v in ENV_IDENTITY_ATTRS.items() if attrs[k] != "from-baggage"}.items() <= attrs.items()


@patch.dict(os.environ, POD_ENV, clear=True)
def test_env_identity_fills_span_when_baggage_is_empty():
    tracer, exporter = _new_tracer()

    attrs = _span_attrs(tracer, exporter, Context())

    assert ENV_IDENTITY_ATTRS.items() <= attrs.items()
    assert not set(REQUEST_ATTRS) & attrs.keys()


@pytest.mark.parametrize(
    ("env", "nova_type"),
    [
        ({"SINGLESTOREDB_WORKLOAD_TYPE": "NotebookCodeService"}, "NotebookCodeService"),
        ({"SINGLESTOREDB_APP_TYPE": "AGENT"}, "AGENT"),
        ({"SINGLESTOREDB_WORKLOAD_TYPE": "ScheduledNotebook", "SINGLESTOREDB_APP_TYPE": "AGENT"}, "ScheduledNotebook"),
    ],
)
def test_env_nova_type_prefers_workload_type(env, nova_type):
    with patch.dict(os.environ, env, clear=True):
        tracer, exporter = _new_tracer()

    assert _span_attrs(tracer, exporter, Context())["singlestore.nova.app.type"] == nova_type


@patch.dict(os.environ, {}, clear=True)
def test_no_baggage_and_no_env_stamps_nothing():
    tracer, exporter = _new_tracer()

    assert _span_attrs(tracer, exporter, Context()) == {}


@patch.dict(os.environ, POD_ENV, clear=True)
def test_processor_made_in_one_thread_stamps_span_started_in_another():
    with ThreadPoolExecutor(max_workers=1) as pool:
        tracer, exporter = pool.submit(_new_tracer).result()
    with ThreadPoolExecutor(max_workers=1) as pool:
        attrs = pool.submit(_span_attrs, tracer, exporter, Context()).result()

    assert ENV_IDENTITY_ATTRS.items() <= attrs.items()
