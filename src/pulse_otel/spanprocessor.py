"""Stamps singlestore.* identity onto every span from its parent context's W3C baggage.
A missing org/project/nexus/nova member falls back to the pod env identity; request dims
(domain/session/turn/api key) come from baggage only."""

from opentelemetry.baggage import get_baggage
from opentelemetry.sdk.trace import SpanProcessor

from pulse_otel.consts import (
    API_KEY_ID,
    APP_ID,
    APP_NAME,
    APP_TYPE,
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
    CONVERSATION_ID,
    DOMAIN_ID,
    NEXUS_APP_ID,
    NEXUS_APP_TYPE,
    ORG_ID,
    ORGANIZATION,
    PROJECT,
    PROJECT_ID,
    SESSION_ID,
    SESSION_ID_ALIAS,
    SINGLESTORE_ORG_ID,
    SINGLESTORE_PROJECT_ID,
    TURN_ID,
)
from pulse_otel.identity import _process_identity_baggage


class BaggageSpanProcessor(SpanProcessor):
    def __init__(self):
        self._env_identity = _process_identity_baggage()

    def on_start(self, span, parent_context=None):
        def stamp(baggage_key, *attr_keys):
            value = get_baggage(baggage_key, parent_context) or self._env_identity.get(baggage_key)
            if value:
                for attr_key in attr_keys:
                    span.set_attribute(attr_key, value)

        stamp(BAGGAGE_ORG, ORGANIZATION, ORG_ID, SINGLESTORE_ORG_ID)
        stamp(BAGGAGE_PROJECT, PROJECT, PROJECT_ID, SINGLESTORE_PROJECT_ID)
        stamp(BAGGAGE_DOMAIN, DOMAIN_ID)
        stamp(BAGGAGE_SESSION, SESSION_ID, CONVERSATION_ID, SESSION_ID_ALIAS)
        stamp(BAGGAGE_TURN, TURN_ID)
        stamp(BAGGAGE_API_KEY, API_KEY_ID)
        stamp(BAGGAGE_NEXUS_ID, NEXUS_APP_ID)
        stamp(BAGGAGE_NEXUS_TYPE, NEXUS_APP_TYPE)
        stamp(BAGGAGE_NOVA_ID, APP_ID)
        stamp(BAGGAGE_NOVA_TYPE, APP_TYPE)
        stamp(BAGGAGE_NOVA_NAME, APP_NAME)

    def on_end(self, span):
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True
