import os
from unittest.mock import patch

import pytest

from pulse_otel.consts import DEFAULT_ENV_VARIABLES
from pulse_otel.util import (
    form_otel_collector_endpoint,
    format_env_variables,
    get_environ_vars,
)

# format_env_variables emits both the singlestore.* attributes and the canonical
# OTel org.id/project.id (plus singlestore.org.id/singlestore.project.id) so the
# notebook tier joins the Go services. See util.format_env_variables.


class TestFormatEnvVariables:
    def test_all_mapped(self):
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
            "org.id": "org1",
            "singlestore.org.id": "org1",
            "project.id": "proj1",
            "singlestore.project.id": "proj1",
            "service.version": "TestApp",
            "deployment.environment.name": "testtype",
        }
        assert format_env_variables(input_vars) == expected_output

    def test_some_unmapped(self):
        input_vars = {
            "SINGLESTOREDB_PROJECT": "proj2",
            "SOME_OTHER_VAR": "value1",
            "ANOTHER_VAR_WITH_UNDERSCORES": "value2",
        }
        expected_output = {
            "singlestore.project": "proj2",
            "some.other.var": "value1",
            "another.var.with.underscores": "value2",
            "project.id": "proj2",
            "singlestore.project.id": "proj2",
        }
        assert format_env_variables(input_vars) == expected_output

    def test_empty_input(self):
        assert format_env_variables({}) == {}

    def test_already_formatted(self):
        input_vars = {"singlestore.project": "proj3", "custom.key": "custom_value"}
        expected_output = {
            "singlestore.project": "proj3",
            "custom.key": "custom_value",
            "project.id": "proj3",
            "singlestore.project.id": "proj3",
        }
        assert format_env_variables(input_vars) == expected_output


class TestGetEnvironVars:
    @patch.dict(os.environ, {}, clear=True)
    def test_all_defaults(self):
        assert get_environ_vars() == format_env_variables(DEFAULT_ENV_VARIABLES)

    @patch.dict(
        os.environ,
        {
            "SINGLESTOREDB_ORGANIZATION": "my_org",
            "SINGLESTOREDB_PROJECT": "my_project",
            "HTTP_NOTEBOOKSSERVERID": "8ab506eb-ff38-4302-87bc-d9c421dada6f",
            "HOSTNAME": "my_host",
        },
        clear=True,
    )
    def test_some_set(self):
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
            "org.id": "my_org",
            "singlestore.org.id": "my_org",
            "project.id": "my_project",
            "singlestore.project.id": "my_project",
            # No service.version: the default app name is the placeholder.
            "deployment.environment.name": "notebookcodeservice",
        }
        assert get_environ_vars() == expected_output

    @patch.dict(
        os.environ,
        {
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
        },
        clear=True,
    )
    def test_all_set(self):
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
            "org.id": "org_all_set",
            "singlestore.org.id": "org_all_set",
            "project.id": "proj_all_set",
            "singlestore.project.id": "proj_all_set",
            "service.version": "NameAllSet",
            "deployment.environment.name": "typeallset",
        }
        assert get_environ_vars() == expected_output


class TestFormOtelCollectorEndpoint:
    def test_valid_project_id(self):
        project_id = "my-test-project-123"
        expected_url = f"http://otel-collector-{project_id}.observability.svc.cluster.local:4317"
        assert form_otel_collector_endpoint(project_id) == expected_url

    @pytest.mark.parametrize("project_id", [None, ""])
    def test_missing_project_id_raises(self, project_id):
        with pytest.raises(ValueError, match="SINGLESTOREDB_PROJECT is required"):
            form_otel_collector_endpoint(project_id)
