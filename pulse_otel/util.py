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
    SESSION_ID,
)
import random
from traceloop.sdk import Traceloop

logger = logging.getLogger(__name__)

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

def extract_session_id(**kwargs) -> str:
    """
    Extracts the session ID from a 'baggage' header in a FastAPI Request object
    or directly from a 'headers' dict in kwargs.
    """

    session_id = None
    try:
        logger.debug(f"[pulse_agent] DEBUG - Extracting session ID from kwargs: {kwargs}")
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
        logger.error(f"[pulse_agent] Error extracting session ID: {e}")
    return session_id

def extract_session_id_from_body(**kwargs) -> Optional[str]:
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
                logger.debug(f"[pulse_agent] DEBUG - Found session_id in request body attributes: {request_body.session_id}")
                return getattr(request_body, "session_id")
    except Exception as e:
        logger.error(f"[pulse_agent] Error extracting session_id from body: {e}")

    return None


def _is_endpoint_reachable(endpoint_url: str, timeout: int = 3) -> bool:
    """
    Checks if a given endpoint URL is reachable within a specified timeout.
    Args:
        endpoint_url (str): The URL of the endpoint to check. Must include the hostname and optionally the port.
        timeout (int, optional): The timeout duration in seconds for the connection attempt. Defaults to 3 seconds.
    Returns:
        bool: True if the endpoint is reachable, False otherwise.
    Warnings:
        - If the `endpoint_url` is empty, a warning is printed, and the function assumes the endpoint is unreachable.
        - If the URL is malformed or cannot be parsed, a warning is printed, and the function assumes the endpoint is unreachable.
        - If the connection attempt fails due to socket errors, timeouts, or connection refusals, a warning is printed with details.
    Exceptions:
        - Handles `socket.error`, `ConnectionRefusedError`, `socket.timeout`, and `ValueError` gracefully by printing warnings.
        - Catches any other unexpected exceptions and prints a warning with the error details.
    """
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

def add_session_id_to_span_attributes(**kwargs):
    """
    Adds a session ID to span attributes by extracting it from the provided keyword arguments.

    This function attempts to extract a session ID using two methods:
    1. `extract_session_id`: Extracts the session ID from the provided arguments.
    2. `extract_session_id_from_body`: Extracts the session ID from the body of the provided arguments.

    If no session ID is found, a debug log message is generated indicating that no session ID was found.
    The extracted session ID is then added to the association properties using the `Traceloop.set_association_properties` method.

    Args:
        **kwargs: Arbitrary keyword arguments that may contain the session ID.

    Logs:
        Debug log if no session ID is found.

    Side Effects:
        Updates the association properties with the extracted session ID.

    """

    session_id = extract_session_id(**kwargs) or extract_session_id_from_body(**kwargs)

    if not session_id:
        logger.debug("[pulse_agent] No singlestore-session-id found")
        return
    properties = {
        SESSION_ID: session_id,
    }
    Traceloop.set_association_properties(properties)
