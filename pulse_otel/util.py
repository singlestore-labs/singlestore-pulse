import os
from pulse_otel.consts import OTEL_COLLECTOR_ENDPOINT


def get_configs():
    """
    Reads specific environment variables and returns their values. If a variable is not set, returns its default value.

    Returns:
        dict: A dictionary containing the environment variables and their values.

        example:
        {
                "SINGLESTOREDB_ORGANIZATION": "6179a453-89bc-4341-8885-287ada1e5dd8",
                "SINGLESTOREDB_PROJECT": "e003a14c-b9a6-4630-811c-0a13e04a568b",
                "HTTP_NOTEBOOKSSERVERID": "693c3fb9-f0c9-460e-926f-e7202526dddc",
                "HOSTNAME": "newdeploy-fn-693c3fb9-fission-nova-a3aa-8d63644fa018-0",
                "HTTP_FISSIONFUNCTIONNAME": "fn-693c3fb9",
                "SINGLESTOREDB_WORKLOAD_TYPE": "NotebookCodeService",
                "SINGLESTOREDB_APP_BASE_PATH": "/functions/b933504d-63bd-4700-8f19-4dd3d7bef123/",
                "SINGLESTOREDB_APP_BASE_URL": "https://apps.aws-virginia-nb2.svc.singlestore.com:8000/functions/b933504d-63bd-4700-8f19-4dd3d7bef123/",
                "APP_TYPE": "AGENT",
        }

    """
    env_variables_default = {
        "SINGLESTOREDB_ORGANIZATION": "",
        "SINGLESTOREDB_PROJECT": "",
        "HTTP_NOTEBOOKSSERVERID": "",
        "HOSTNAME": "",
        "HTTP_FISSIONFUNCTIONNAME": "",
        "SINGLESTOREDB_WORKLOAD_TYPE": "NotebookCodeService",
        "SINGLESTOREDB_APP_BASE_PATH": "",
        "SINGLESTOREDB_APP_BASE_URL": "",
        "APP_TYPE": "AGENT",
        "SINGLESTOREDB_APP_ID": "",
    }
    env_variables =  {key: os.getenv(key, default) for key, default in env_variables_default.items()}

    return env_variables

def form_otel_collector_endpoint(
    project_id: str = None,
) -> str:
    """
    Forms the OpenTelemetry collector endpoint URL.

    Args:
        project_id (str): The project ID to be inserted into the endpoint URL.

    Returns:
        str: The formatted OpenTelemetry collector endpoint URL.
    """
    if project_id is None:
        project_id = os.getenv("SINGLESTOREDB_PROJECT", "")
        if not project_id:
            raise ValueError("Project ID is required but not found int env variables.")
        
    otel_collector_endpoint_str = str(OTEL_COLLECTOR_ENDPOINT)
    return otel_collector_endpoint_str.replace("{PROJECTID_PLACEHOLDER}", project_id)

def fetch_resource_attributes():
    """
    Fetches and returns resource attributes from the environment.
    
    Returns:
    - A dictionary of resource attributes
    """
    resource_attributes = {
        "env": os.getenv("env", "nova-prod"),
        "agentName": os.getenv("agentName", "myagent"),
        # Add more attributes as needed
    }
    return resource_attributes
