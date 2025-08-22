# Otel collector endpoint URL for pushing traces and logs
OTEL_COLLECTOR_ENDPOINT = "http://otel-collector-{PROJECTID_PLACEHOLDER}.observability.svc.cluster.local:4317"
PULSE_INTERNAL_COLLECTOR_ENDPOINT = "otel-collector-pulse-internal-{NOVA_CELL_PLACEHOLDER}.observability.svc.cluster.local:4317"

HEADER_INCOMING_SESSION_ID = "singlestore-session-id"

# Formatted attribute names
APP_TYPE = "singlestore.nova.app.type"
APP_ID = "singlestore.nova.app.id"
APP_NAME = "singlestore.nova.app.name"
SESSION_ID = "session.id"
ORGANIZATION = "singlestore.organization"
PROJECT = "singlestore.project"
HOSTNAME = "singlestore.hostname"
IS_AGENT = "singlestore.is.agent"
WORKLOAD_TYPE = "singlestore.workload.type"
APP_BASE_PATH = "singlestore.nova.app.base.path"
APP_BASE_URL = "singlestore.nova.app.base.url"
LIVE_LOGS_FILE_PATH = "LIVE_LOGS_FILE_PATH"
SERVER_ID = "singlestore.notebooks.server.id"

# default env variables from notebook server
DEFAULT_ENV_VARIABLES = {
	"SINGLESTOREDB_ORGANIZATION": "",
	"SINGLESTOREDB_PROJECT": "",
	"HTTP_NOTEBOOKSSERVERID": "",
	"HOSTNAME": "",
	"SINGLESTOREDB_WORKLOAD_TYPE": "NotebookCodeService",
	"SINGLESTOREDB_APP_BASE_PATH": "",
	"SINGLESTOREDB_APP_BASE_URL": "",
	"SINGLESTOREDB_APP_TYPE": "AGENT",
	"SINGLESTOREDB_APP_ID": "123456789",
    "SINGLESTOREDB_APP_NAME": "MY_APP_NAME",
    "SINGLESTOREDB_IS_AGENT": "true",
}

ENV_VARIABLES_MAPPING = {
	"SINGLESTOREDB_APP_ID" : APP_ID,
	"SINGLESTOREDB_APP_NAME" : APP_NAME,
	"SINGLESTOREDB_APP_TYPE" : APP_TYPE,
	"SINGLESTOREDB_ORGANIZATION" : ORGANIZATION,
	"SINGLESTOREDB_PROJECT" : PROJECT,
	"HTTP_NOTEBOOKSSERVERID" : SERVER_ID,
	"SINGLESTOREDB_WORKLOAD_TYPE" : WORKLOAD_TYPE,
	"SINGLESTOREDB_APP_BASE_PATH" : APP_BASE_PATH,
	"SINGLESTOREDB_APP_BASE_URL" : APP_BASE_URL,
	"SINGLESTOREDB_IS_AGENT" : IS_AGENT,
	"HOSTNAME" : HOSTNAME,
}

# Local traces and logs output files
LOCAL_TRACES_FILE = "pulse_traces.json"
LOCAL_LOGS_FILE = "pulse_logs.txt"
