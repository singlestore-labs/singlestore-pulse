import os
import pytest
from pulse_otel.util import get_internal_collector_endpoint
from pulse_otel.consts import PULSE_INTERNAL_COLLECTOR_ENDPOINT

import importlib

def set_env(key, value):
    os.environ[key] = value

def unset_env(key):
    if key in os.environ:
        del os.environ[key]

def test_get_internal_collector_endpoint_positive(monkeypatch):
    # Set up a valid SINGLESTOREDB_CELL_SHORT_NAME
    monkeypatch.setenv("SINGLESTOREDB_CELL_SHORT_NAME", "nova-cell")
    # Patch the PULSE_INTERNAL_COLLECTOR_ENDPOINT constant
    
    result = get_internal_collector_endpoint()
    print(result)
    assert result == "http://otel-collector-pulse-internal-nova-cell.observability.svc.cluster.local:4317"

def test_get_internal_collector_endpoint_positive_stg(monkeypatch):
    # Set up a valid SINGLESTOREDB_CELL_SHORT_NAME
    monkeypatch.setenv("SINGLESTOREDB_CELL_SHORT_NAME", "nova-cell-stg")
    # Patch the PULSE_INTERNAL_COLLECTOR_ENDPOINT constant
    
    result = get_internal_collector_endpoint()
    print(result)
    assert result == "http://otel-collector-pulse-internal-nova-cell-stg.observability.svc.cluster.local:4317"

def test_get_internal_collector_endpoint_missing_env(monkeypatch):
    # Ensure SINGLESTOREDB_CELL_SHORT_NAME is not set
    monkeypatch.delenv("SINGLESTOREDB_CELL_SHORT_NAME", raising=False)
    with pytest.raises(ValueError) as excinfo:
        get_internal_collector_endpoint()
    assert "SINGLESTOREDB_CELL_SHORT_NAME is required" in str(excinfo.value)
