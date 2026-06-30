import os
from unittest.mock import patch

from opentelemetry.baggage import get_all
from opentelemetry.context import Context

from pulse_otel.consts import (
    APP_NAME_PLACEHOLDER,
    BAGGAGE_ORG,
    BAGGAGE_PROJECT,
    BAGGAGE_NOVA_ID,
    BAGGAGE_NOVA_TYPE,
    BAGGAGE_NOVA_NAME,
)
from pulse_otel.identity import _IdentityBaggagePropagator, seed_identity_baggage


@patch.dict(
    os.environ,
    {
        "SINGLESTOREDB_ORGANIZATION": "org1",
        "SINGLESTOREDB_PROJECT": "proj1",
        "SINGLESTOREDB_APP_ID": "app1",
        "SINGLESTOREDB_APP_TYPE": "AGENT",
        "SINGLESTOREDB_APP_NAME": "sqlbot",
    },
    clear=True,
)
def test_seed_identity_baggage_sets_all_keys():
    bag = get_all(seed_identity_baggage(Context()))
    assert bag[BAGGAGE_ORG] == "org1"
    assert bag[BAGGAGE_PROJECT] == "proj1"
    assert bag[BAGGAGE_NOVA_ID] == "app1"
    assert bag[BAGGAGE_NOVA_TYPE] == "AGENT"
    assert bag[BAGGAGE_NOVA_NAME] == "sqlbot"


@patch.dict(os.environ, {"SINGLESTOREDB_ORGANIZATION": "org1"}, clear=True)
def test_seed_identity_baggage_drops_empty_keys():
    bag = get_all(seed_identity_baggage(Context()))
    assert bag[BAGGAGE_ORG] == "org1"
    assert BAGGAGE_PROJECT not in bag
    assert BAGGAGE_NOVA_ID not in bag


@patch.dict(
    os.environ,
    {"SINGLESTOREDB_ORGANIZATION": "org1", "SINGLESTOREDB_APP_NAME": APP_NAME_PLACEHOLDER},
    clear=True,
)
def test_seed_identity_baggage_drops_placeholder_app_name():
    bag = get_all(seed_identity_baggage(Context()))
    assert BAGGAGE_NOVA_NAME not in bag


@patch.dict(
    os.environ,
    {"SINGLESTOREDB_ORGANIZATION": "org1", "SINGLESTOREDB_APP_ID": "app1"},
    clear=True,
)
def test_propagator_injects_identity_into_baggage_header():
    carrier = {}
    _IdentityBaggagePropagator().inject(carrier, context=Context())
    assert "baggage" in carrier
    assert "org1" in carrier["baggage"]
    assert "app1" in carrier["baggage"]
