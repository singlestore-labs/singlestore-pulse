"""Baggage→span processor: stamps singlestore.* identity onto every span from
the W3C baggage on its parent context, so identity lands on all spans (not only
those a library explicitly tags). Producers seed the baggage; this projects it.
A dimension is stamped only when present, so session/domain appear only when a
chat/AuraAnalyst entrypoint seeded them."""

from opentelemetry.baggage import get_baggage
from opentelemetry.sdk.trace import SpanProcessor

from pulse_otel.consts import (
    ORGANIZATION,
    ORG_ID,
    SINGLESTORE_ORG_ID,
    PROJECT,
    PROJECT_ID,
    SINGLESTORE_PROJECT_ID,
    DOMAIN_ID,
    SESSION_ID,
    CONVERSATION_ID,
    SESSION_ID_ALIAS,
    NEXUS_APP_ID,
    NEXUS_APP_TYPE,
    APP_ID,
    APP_TYPE,
    APP_NAME,
    BAGGAGE_ORG,
    BAGGAGE_PROJECT,
    BAGGAGE_DOMAIN,
    BAGGAGE_SESSION,
    BAGGAGE_NEXUS_ID,
    BAGGAGE_NEXUS_TYPE,
    BAGGAGE_NOVA_ID,
    BAGGAGE_NOVA_TYPE,
    BAGGAGE_NOVA_NAME,
)


class BaggageSpanProcessor(SpanProcessor):
    def on_start(self, span, parent_context=None):
        def stamp(baggage_key, *attr_keys):
            value = get_baggage(baggage_key, parent_context)
            if value:
                for attr_key in attr_keys:
                    span.set_attribute(attr_key, value)

        stamp(BAGGAGE_ORG, ORGANIZATION, ORG_ID, SINGLESTORE_ORG_ID)
        stamp(BAGGAGE_PROJECT, PROJECT, PROJECT_ID, SINGLESTORE_PROJECT_ID)
        stamp(BAGGAGE_DOMAIN, DOMAIN_ID)
        stamp(BAGGAGE_SESSION, SESSION_ID, CONVERSATION_ID, SESSION_ID_ALIAS)
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
