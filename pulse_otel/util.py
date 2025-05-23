import os
from pulse_otel.consts import (
    OTEL_COLLECTOR_ENDPOINT,
    DEFAULT_ENV_VARIABLES,
    ENV_VARIABLES_MAPPING,
    HEADER_INCOMING_SESSION_ID,
)



def get_environ_vars():
    """
    Reads specific environment variables and returns their values. If a variable is not set, returns its default value.

    Returns:
        dict: A dictionary containing the environment variables and their values.

    Example:
        {
            "singlestore.organization": "",
            "singlestore.project": "",
            "singlestore.notebooks.server.id": "",
            "singlestore.hostname": "",
            "singlestore.workload.type": "NotebookCodeService",
            "singlestore.nova.app.base.path": "",
            "singlestore.nova.app.base.url": "",
            "singlestore.nova.app.type": "AGENT",
            "singlestore.nova.app.id": "123456789",
            "singlestore.nova.app.name": "MY_APP_NAME",
            "singlestore.is.agent": "true",
        }

    """

    env_variables =  {key: os.getenv(key, default) for key, default in DEFAULT_ENV_VARIABLES.items()}

    formatted_env_variables = format_env_variables(env_variables)
    return formatted_env_variables

def format_env_variables(env_variables):
    
    new_data = {}
    for key, value in env_variables.items():
        # Find if any of the match keys exist in the current key
        new_key = key
        for match, replacement in ENV_VARIABLES_MAPPING.items():
            if match in key:
                new_key = replacement
                break
        new_data[new_key] = value

    def convert_key(key):
            return key.lower().replace('_', '.')

    converted_env_variables =  {convert_key(k): v for k, v in new_data.items()}
    return converted_env_variables

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
    
    if project_id is None or project_id == '':
        raise ValueError("[Pulse] SINGLESTOREDB_PROJECT is required but not found int env variables.")

    otel_collector_endpoint_str = str(OTEL_COLLECTOR_ENDPOINT)
    return otel_collector_endpoint_str.replace("{PROJECTID_PLACEHOLDER}", project_id)

def extract_session_id(kwargs):
        """
        Extracts the session ID from the 'baggage' header in the provided kwargs.

        Args:
            kwargs (dict): A dictionary that may contain a 'headers' key with HTTP headers.

        Returns:
            str or None: The extracted session ID if found, otherwise None.

        Notes:
            - The function looks for a 'baggage' header in the 'headers' dictionary.
            - It parses the 'baggage' header for a key matching HEADER_INCOMING_SESSION_ID.
            - If an error occurs during extraction, it prints an error message and returns None.
        """
        session_id = None
        try:
            if 'headers' in kwargs:
                headers = kwargs['headers']
                baggage = headers.get('baggage')
                if baggage:
                    parts = [item.strip() for item in baggage.split(',')]
                    for part in parts:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            if key.strip() == HEADER_INCOMING_SESSION_ID:
                                session_id = value.strip()
                                break
        except Exception as e:
            print(f"Error extracting session ID: {e}")
        return session_id
