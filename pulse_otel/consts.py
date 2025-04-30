OTEL_COLLECTOR_ENDPOINT = "http://otel-collector-{PROJECTID_PLACEHOLDER}.observability.svc.cluster.local:4317"
LOCAL_TRACES_FILE = "traceloop_traces.json"
LOCAL_LOGS_FILE = "traceloop_logs.txt"
HEADER_INCOMING_SESSION_ID = "singlestore-session-id"

# Formatted attribute names
APP_TYPE = "singlestore.nova.app.type"
APP_ID = "singlestore.nova.app.id"
APP_NAME = "singlestore.nova.app.name"
SESSION_ID = "session.id"

# default env variables from notebook server
DEFAULT_ENV_VARIABLES = {
	"SINGLESTOREDB_ORGANIZATION": "",
	"SINGLESTOREDB_PROJECT": "",
	"HTTP_NOTEBOOKSSERVERID": "",
	"HOSTNAME": "",
	"HTTP_FISSIONFUNCTIONNAME": "",
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
}
