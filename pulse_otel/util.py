import logging
import os
import socket
from urllib.parse import urlparse
from typing import Optional

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

def extract_session_id(kwargs: dict) -> str:
    """
    Extracts the session ID from a 'baggage' header in a FastAPI Request object
    or directly from a 'headers' dict in kwargs.
    """
    logger = logging.getLogger(__name__)

    session_id = None
    try:
        logger.info(f"[pulse_agent] DEBUG - Extracting session ID from kwargs: {kwargs}")
        session_id = kwargs.get('session_id')
        if session_id:
            return session_id
        request = kwargs.get('request')
        if request and hasattr(request, "headers"):
            headers = getattr(request, "headers", {})
        else:
            headers = kwargs.get("headers", {})

        baggage = headers.get('baggage') if hasattr(headers, "get") else None
        if baggage:
            parts = [item.strip() for item in baggage.split(',')]
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key.strip() == HEADER_INCOMING_SESSION_ID:
                        session_id = value.strip()
                        break
    except Exception as e:
        print(f"[pulse_agent] Error extracting session ID: {e}")
    return session_id

def extract_session_id_from_body(kwargs: dict) -> Optional[str]:
    """
    Extracts the 'session_id' from the request body stored in kwargs['body'].
    Supports both dict-like objects and Pydantic models.
    Returns None if not found or if any error occurs.
    """
    try:
        request_body = kwargs.get("body")
        if request_body:
           
            if isinstance(request_body, dict):
                return request_body.get("session_id")
            
            # For attribute-style (e.g., Pydantic model)
            elif hasattr(request_body, "session_id"):
                print(f"[pulse_agent] DEBUG - Found session_id in request body attributes: {request_body.session_id}")
                return getattr(request_body, "session_id")
    except Exception as e:
        print(f"[pulse_agent] Error extracting session_id from body: {e}")

    return None


def _is_endpoint_reachable(endpoint_url: str, timeout: int = 3) -> bool:
    if not endpoint_url:
        print("Warning: OTel endpoint URL is empty. Assuming unreachable.")
        return False
    try:

        parsed_url = urlparse(endpoint_url)
        host = parsed_url.hostname
        port = parsed_url.port

        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.error, ConnectionRefusedError, socket.timeout) as e:
        # Define host/port for error message, using defaults if parsing failed before assignment.
        error_host_str = host if 'host' in locals() and host is not None else "unknown (parsing error)"
        # Port is expected to be 4317 if format is correct.
        error_port_str = str(port) if 'port' in locals() and port is not None else "unknown (parsing error or not 4317)"
        
        print(f"Warning: OTel endpoint {endpoint_url} (resolved to {error_host_str}:{error_port_str}) is not reachable: {e}")
        return False
    except ValueError as e: # Handle potential errors from urlparse if URL is malformed
        print(f"Warning: Malformed OTel endpoint URL '{endpoint_url}': {e}. Assuming unreachable.")
        return False
    except Exception as e: # Catch any other unexpected errors during the check
        print(f"Warning: An unexpected error occurred while checking OTel endpoint reachability for {endpoint_url}: {e}")
        return False
