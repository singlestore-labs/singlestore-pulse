import pytest

from pulse_otel.util import get_internal_collector_endpoint


@pytest.mark.parametrize(
    "cell_short_name, expected",
    [
        (
            "nova-cell",
            "http://otel-collector-pulse-internal-nova-cell.observability.svc.cluster.local:4317",
        ),
        (
            "nova-cell-stg",
            "http://otel-collector-pulse-internal-nova-cell-stg.observability.svc.cluster.local:4317",
        ),
    ],
)
def test_get_internal_collector_endpoint(monkeypatch, cell_short_name, expected):
    monkeypatch.setenv("SINGLESTOREDB_CELL_SHORT_NAME", cell_short_name)
    assert get_internal_collector_endpoint() == expected


def test_get_internal_collector_endpoint_missing_env(monkeypatch):
    monkeypatch.delenv("SINGLESTOREDB_CELL_SHORT_NAME", raising=False)
    with pytest.raises(ValueError, match="SINGLESTOREDB_CELL_SHORT_NAME is required"):
        get_internal_collector_endpoint()
