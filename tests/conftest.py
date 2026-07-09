"""Shared fixtures for singlestore-pulse tests."""

import pytest


@pytest.fixture(autouse=True)
def reset_pulse_instance():
    """Clear the module-level Pulse singleton around every test so instances don't leak."""
    import pulse_otel.main

    pulse_otel.main._pulse_instance = None
    yield
    pulse_otel.main._pulse_instance = None
