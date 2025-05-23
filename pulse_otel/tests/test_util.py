# tests/test_util.py
import pytest
import os
from unittest.mock import patch

# Assuming your project structure allows this import
from pulse_otel.util import get_environ_vars, format_env_variables, form_otel_collector_endpoint
from pulse_otel.consts import DEFAULT_ENV_VARIABLES, ENV_VARIABLES_MAPPING, OTEL_COLLECTOR_ENDPOINT

# --- Tests for format_env_variables ---

def test_format_env_variables_positive_all_mapped():
    """Test formatting when all input keys are in ENV_VARIABLES_MAPPING."""
    input_vars = {
        "SINGLESTOREDB_ORGANIZATION": "org1",
        "SINGLESTOREDB_PROJECT": "proj1",
        "HTTP_NOTEBOOKSSERVERID": "8ab506eb-ff38-4302-87bc-d9c421dada6f",
        "HOSTNAME": "host1",
        "SINGLESTOREDB_WORKLOAD_TYPE": "TestType",
        "SINGLESTOREDB_APP_BASE_PATH": "/path/to/app",
        "SINGLESTOREDB_APP_BASE_URL": "http://app.url",
        "SINGLESTOREDB_APP_TYPE": "TEST_APP",
        "SINGLESTOREDB_APP_ID": "app987",
        "SINGLESTOREDB_APP_NAME": "TestApp",
        "SINGLESTOREDB_IS_AGENT": "false",
    }
    expected_output = {
        "singlestore.organization": "org1",
        "singlestore.project": "proj1",
        "singlestore.notebooks.server.id": "8ab506eb-ff38-4302-87bc-d9c421dada6f",
        "singlestore.hostname": "host1",
        "singlestore.workload.type": "TestType",
        "singlestore.nova.app.base.path": "/path/to/app",
        "singlestore.nova.app.base.url": "http://app.url",
        "singlestore.nova.app.type": "TEST_APP",
        "singlestore.nova.app.id": "app987",
        "singlestore.nova.app.name": "TestApp",
        "singlestore.is.agent": "false",
    }
    assert format_env_variables(input_vars) == expected_output

def test_format_env_variables_positive_some_unmapped():
    """Test formatting with a mix of mapped and unmapped keys."""
    input_vars = {
        "SINGLESTOREDB_PROJECT": "proj2",
        "SOME_OTHER_VAR": "value1",
        "ANOTHER_VAR_WITH_UNDERSCORES": "value2"
    }
    expected_output = {
        "singlestore.project": "proj2",
        "some.other.var": "value1",
        "another.var.with.underscores": "value2"
    }
    assert format_env_variables(input_vars) == expected_output

def test_format_env_variables_negative_empty_input():
    """Test formatting with an empty input dictionary."""
    input_vars = {}
    expected_output = {}
    assert format_env_variables(input_vars) == expected_output

def test_format_env_variables_positive_already_formatted():
    """Test formatting when keys are already in the target format (lowercase, dots)."""
    input_vars = {
        "singlestore.project": "proj3",
        "custom.key": "custom_value"
    }
    # The function should still process them, but the output format remains the same
    expected_output = {
        "singlestore.project": "proj3",
        "custom.key": "custom_value"
    }
    assert format_env_variables(input_vars) == expected_output

# --- Tests for get_environ_vars ---

@patch.dict(os.environ, {}, clear=True) # Start with clean environment
def test_get_environ_vars_positive_all_defaults():
    """Test get_environ_vars when no relevant env vars are set (uses defaults)."""
    # Expected output is the formatted version of DEFAULT_ENV_VARIABLES
    expected_output = format_env_variables(DEFAULT_ENV_VARIABLES)
    assert get_environ_vars() == expected_output

@patch.dict(os.environ, {
    "SINGLESTOREDB_ORGANIZATION": "my_org",
    "SINGLESTOREDB_PROJECT": "my_project",
    "HTTP_NOTEBOOKSSERVERID": "8ab506eb-ff38-4302-87bc-d9c421dada6f",
    "HOSTNAME": "my_host",
    # Other variables will use defaults from DEFAULT_ENV_VARIABLES
}, clear=True)
def test_get_environ_vars_positive_some_set():
    """Test get_environ_vars when some env vars are set and others use defaults."""
    # Build expected output manually based on set vars and defaults
    expected_output = {
        "singlestore.organization": "my_org",
        "singlestore.project": "my_project",
        "singlestore.notebooks.server.id": "8ab506eb-ff38-4302-87bc-d9c421dada6f",
        "singlestore.hostname": "my_host",
        "singlestore.workload.type": DEFAULT_ENV_VARIABLES["SINGLESTOREDB_WORKLOAD_TYPE"],
        "singlestore.nova.app.base.path": DEFAULT_ENV_VARIABLES["SINGLESTOREDB_APP_BASE_PATH"],
        "singlestore.nova.app.base.url": DEFAULT_ENV_VARIABLES["SINGLESTOREDB_APP_BASE_URL"],
        "singlestore.nova.app.type": DEFAULT_ENV_VARIABLES["SINGLESTOREDB_APP_TYPE"],
        "singlestore.nova.app.id": DEFAULT_ENV_VARIABLES["SINGLESTOREDB_APP_ID"],
        "singlestore.nova.app.name": DEFAULT_ENV_VARIABLES["SINGLESTOREDB_APP_NAME"],
        "singlestore.is.agent": DEFAULT_ENV_VARIABLES["SINGLESTOREDB_IS_AGENT"],
    }
    assert get_environ_vars() == expected_output


@patch.dict(os.environ, {
    "SINGLESTOREDB_ORGANIZATION": "org_all_set",
    "SINGLESTOREDB_PROJECT": "proj_all_set",
    "HTTP_NOTEBOOKSSERVERID": "8ab506eb-ff38-4302-87bc-d9c421dada6f",
    "HOSTNAME": "host_all_set",
    "SINGLESTOREDB_WORKLOAD_TYPE": "TypeAllSet",
    "SINGLESTOREDB_APP_BASE_PATH": "/all/set",
    "SINGLESTOREDB_APP_BASE_URL": "http://all.set",
    "SINGLESTOREDB_APP_TYPE": "APP_ALL_SET",
    "SINGLESTOREDB_APP_ID": "id_all_set",
    "SINGLESTOREDB_APP_NAME": "NameAllSet",
    "SINGLESTOREDB_IS_AGENT": "false",
}, clear=True)
def test_get_environ_vars_positive_all_set():
    """Test get_environ_vars when all relevant env vars are explicitly set."""
    expected_output = {
        "singlestore.organization": "org_all_set",
        "singlestore.project": "proj_all_set",
        "singlestore.notebooks.server.id": "8ab506eb-ff38-4302-87bc-d9c421dada6f",
        "singlestore.hostname": "host_all_set",
        "singlestore.workload.type": "TypeAllSet",
        "singlestore.nova.app.base.path": "/all/set",
        "singlestore.nova.app.base.url": "http://all.set",
        "singlestore.nova.app.type": "APP_ALL_SET",
        "singlestore.nova.app.id": "id_all_set",
        "singlestore.nova.app.name": "NameAllSet",
        "singlestore.is.agent": "false",
    }
    assert get_environ_vars() == expected_output

# --- Tests for form_otel_collector_endpoint ---

def test_form_otel_collector_endpoint_positive():
    """Test forming the endpoint with a valid project ID."""
    project_id = "my-test-project-123"
    expected_url = f"http://otel-collector-{project_id}.observability.svc.cluster.local:4317"
    assert form_otel_collector_endpoint(project_id) == expected_url

def test_form_otel_collector_endpoint_negative_none():
    """Test forming the endpoint with project_id=None."""
    with pytest.raises(ValueError, match="SINGLESTOREDB_PROJECT is required"):
        form_otel_collector_endpoint(None)

def test_form_otel_collector_endpoint_negative_empty_string():
    """Test forming the endpoint with project_id=''."""
    with pytest.raises(ValueError, match="SINGLESTOREDB_PROJECT is required"):
        form_otel_collector_endpoint("")

# You might add more tests, e.g., for project IDs with special characters if relevant,
# although the current implementation doesn't seem to validate the content, just presence.
