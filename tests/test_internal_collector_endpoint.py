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
    # Set up a valid HTTP_FORWARDEDHOST
    monkeypatch.setenv("HTTP_FORWARDEDHOST", "nova-gateway.nova-cell.example.com")
    # Patch the PULSE_INTERNAL_COLLECTOR_ENDPOINT constant
    
    result = get_internal_collector_endpoint()
    print(result)
    assert result == "http://otel-collector-pulse-internal-nova-cell.observability.svc.cluster.local:4317"

def test_get_internal_collector_endpoint_positive_stg(monkeypatch):
    # Set up a valid HTTP_FORWARDEDHOST
    monkeypatch.setenv("HTTP_FORWARDEDHOST", "nova-gateway-stg.nova-cell-stg.example.com")
    # Patch the PULSE_INTERNAL_COLLECTOR_ENDPOINT constant
    
    result = get_internal_collector_endpoint()
    print(result)
    assert result == "http://otel-collector-pulse-internal-nova-cell-stg.observability.svc.cluster.local:4317"

def test_get_internal_collector_endpoint_missing_env(monkeypatch):
    # Ensure HTTP_FORWARDEDHOST is not set
    monkeypatch.delenv("HTTP_FORWARDEDHOST", raising=False)
    with pytest.raises(ValueError) as excinfo:
        get_internal_collector_endpoint()
    assert "HTTP_FORWARDEDHOST is required" in str(excinfo.value)

def test_get_internal_collector_endpoint_invalid_format(monkeypatch):
    # Set an invalid HTTP_FORWARDEDHOST
    monkeypatch.setenv("HTTP_FORWARDEDHOST", "invalidhost.example.com")
    with pytest.raises(ValueError) as excinfo:
        get_internal_collector_endpoint()
    assert "Unable to extract nova cell" in str(excinfo.value)

def test_get_internal_collector_endpoint_wrong_prefix(monkeypatch):
    # Set a host that does not start with nova-gateway
    monkeypatch.setenv("HTTP_FORWARDEDHOST", "otherprefix.nova-cell.example.com")
    with pytest.raises(ValueError) as excinfo:
        get_internal_collector_endpoint()
    assert "Unable to extract nova cell" in str(excinfo.value)
