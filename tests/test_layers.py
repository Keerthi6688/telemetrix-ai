import os
from unittest.mock import MagicMock, patch

import requests as requests_module

import pandas as pd
import pytest

from metrics_collector import MetricsCollector
import upload_to_minio


# ---------------------------------------------------------------------------
# Layer 1-2: Instrumentation + Telemetry Collection (unit tests, mocked Prometheus)
# ---------------------------------------------------------------------------

def _prom_result(value):
    """Build a fake successful Prometheus instant-query response."""
    return {
        "status": "success",
        "data": {"result": [{"metric": {}, "value": [1700000000, str(value)]}]},
    }


def _prom_empty():
    return {"status": "success", "data": {"result": []}}


def test_first_value_extracts_scalar():
    assert MetricsCollector._first_value(_prom_result(42.5)) == 42.5


def test_first_value_returns_none_on_empty_series():
    assert MetricsCollector._first_value(_prom_empty()) is None


def test_first_value_returns_none_on_query_error():
    assert MetricsCollector._first_value({"status": "error"}) is None


def test_query_prometheus_handles_connection_failure():
    collector = MetricsCollector()
    with patch("metrics_collector.requests.get", side_effect=requests_module.exceptions.ConnectionError("down")):
        result = collector.query_prometheus("up")
    assert result["status"] == "error"


def test_query_prometheus_returns_json_on_success():
    collector = MetricsCollector()
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "success", "data": {"result": []}}
    mock_response.raise_for_status.return_value = None
    with patch("metrics_collector.requests.get", return_value=mock_response):
        result = collector.query_prometheus("up")
    assert result["status"] == "success"


def test_first_value_returns_none_on_malformed_series():
    malformed = {"status": "success", "data": {"result": [{"metric": {}, "value": ["not_a_pair"]}]}}
    assert MetricsCollector._first_value(malformed) is None


def test_get_latency_p95_ms_uses_duration_histogram():
    collector = MetricsCollector()
    with patch.object(collector, "query_prometheus", return_value=_prom_result(123.456)) as mock_q:
        latency = collector.get_latency_p95_ms("checkout")
    assert latency == 123.456
    assert "traces_span_metrics_duration_milliseconds_bucket" in mock_q.call_args[0][0]
    assert 'service_name="checkout"' in mock_q.call_args[0][0]


def test_get_throughput_rps_defaults_to_zero_with_no_data():
    collector = MetricsCollector()
    with patch.object(collector, "query_prometheus", return_value=_prom_empty()):
        assert collector.get_throughput_rps("cart") == 0.0


def test_get_error_rate_pct_is_zero_when_no_traffic():
    collector = MetricsCollector()
    with patch.object(collector, "query_prometheus", return_value=_prom_empty()):
        assert collector.get_error_rate_pct("product-catalog") == 0.0


def test_get_error_rate_pct_computes_ratio():
    collector = MetricsCollector()
    responses = [_prom_result(100.0), _prom_result(5.0)]  # total, then errors
    with patch.object(collector, "query_prometheus", side_effect=responses):
        rate = collector.get_error_rate_pct("checkout")
    assert rate == 5.0


def test_get_error_rate_pct_clamps_to_100_on_rate_overshoot():
    collector = MetricsCollector()
    # rate() over sparse counters can make errors appear to exceed total
    # within a window; the result must still be a valid percentage.
    responses = [_prom_result(95.0), _prom_result(96.5)]
    with patch.object(collector, "query_prometheus", side_effect=responses):
        rate = collector.get_error_rate_pct("checkout")
    assert rate == 100.0


def test_get_cpu_percent_queries_container_metric():
    collector = MetricsCollector()
    with patch.object(collector, "query_prometheus", return_value=_prom_result(12.3)) as mock_q:
        cpu = collector.get_cpu_percent("cart")
    assert cpu == 12.3
    assert "container_cpu_utilization_ratio" in mock_q.call_args[0][0]


def test_get_memory_percent_queries_container_metric():
    collector = MetricsCollector()
    with patch.object(collector, "query_prometheus", return_value=_prom_result(45.0)):
        assert collector.get_memory_percent("cart") == 45.0


def test_get_metrics_for_component_returns_all_four_signals():
    collector = MetricsCollector()
    with patch.object(collector, "get_latency_p95_ms", return_value=150.0), \
         patch.object(collector, "get_throughput_rps", return_value=10.0), \
         patch.object(collector, "get_error_rate_pct", return_value=0.5), \
         patch.object(collector, "get_cpu_percent", return_value=30.0), \
         patch.object(collector, "get_memory_percent", return_value=40.0):
        metrics = collector.get_metrics_for_component("checkout")

    assert metrics["component"] == "checkout"
    assert metrics["scenario"] == "normal"
    for signal in ("latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"):
        assert signal in metrics


def test_get_metrics_for_component_accepts_scenario_label():
    collector = MetricsCollector()
    with patch.object(collector, "get_latency_p95_ms", return_value=9000.0), \
         patch.object(collector, "get_throughput_rps", return_value=1.0), \
         patch.object(collector, "get_error_rate_pct", return_value=45.0), \
         patch.object(collector, "get_cpu_percent", return_value=90.0), \
         patch.object(collector, "get_memory_percent", return_value=95.0):
        metrics = collector.get_metrics_for_component("cart", scenario="degraded")
    assert metrics["scenario"] == "degraded"


def test_cli_main_collects_and_saves_csv_and_parquet(tmp_path, monkeypatch):
    """Exercises metrics_collector.py's __main__ block in-process (runpy).

    runpy re-executes the file as a fresh module, so patches on the
    already-imported metrics_collector module's class/functions don't
    reach code running inside that fresh execution - only truly global,
    already-imported singletons (the `requests` and `time` modules
    themselves) are shared. Mock at that level instead.
    """
    import runpy
    import sys

    import requests as requests_module

    times = iter([0, 0, 100])
    monkeypatch.setattr("metrics_collector.time.time", lambda: next(times))
    monkeypatch.setattr("metrics_collector.time.sleep", lambda s: None)

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "success", "data": {"result": []}}
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr(requests_module, "get", lambda *a, **k: mock_response)

    out_prefix = str(tmp_path / "metrics")
    monkeypatch.setattr(sys, "argv", ["metrics_collector.py", "--duration", "1", "--out-prefix", out_prefix])
    monkeypatch.chdir(tmp_path)  # contains the __main__ block's incidental os.makedirs("data")

    import metrics_collector as mc_module
    runpy.run_path(mc_module.__file__, run_name="__main__")

    assert os.path.exists(f"{out_prefix}.csv")
    assert os.path.exists(f"{out_prefix}.parquet")


def test_collect_from_all_components_runs_one_pass_per_component(monkeypatch):
    collector = MetricsCollector()
    times = iter([0, 0, 100])  # start, first while-check (still under), second (past end)
    monkeypatch.setattr("metrics_collector.time.time", lambda: next(times))
    monkeypatch.setattr("metrics_collector.time.sleep", lambda s: None)
    with patch.object(collector, "get_metrics_for_component") as mock_get:
        mock_get.return_value = {
            "timestamp": "t", "component": "checkout", "scenario": "normal",
            "latency_p95_ms": 1.0, "throughput_rps": 1.0, "error_rate_pct": 0.0,
            "cpu_percent": 1.0, "memory_percent": 1.0,
        }
        result = collector.collect_from_all_components(
            duration_minutes=1, interval_seconds=0, components=["checkout", "cart"]
        )
    assert len(result) == 2  # one pass, two components
    assert mock_get.call_count == 2


def test_save_to_parquet_writes_file(tmp_path):
    collector = MetricsCollector()
    collector.data = [{
        "timestamp": "2026-01-01T00:00:00", "component": "cart", "scenario": "normal",
        "latency_p95_ms": 10.0, "throughput_rps": 1.0, "error_rate_pct": 0.0,
        "cpu_percent": 5.0, "memory_percent": 20.0,
    }]
    out = tmp_path / "metrics.parquet"
    df = collector.save_to_parquet(str(out))
    assert out.exists()
    assert len(pd.read_parquet(out)) == len(df) == 1


def test_save_to_csv_writes_expected_columns(tmp_path):
    collector = MetricsCollector()
    collector.data = [
        {
            "timestamp": "2026-01-01T00:00:00",
            "component": "checkout",
            "scenario": "normal",
            "latency_p95_ms": 100.0,
            "throughput_rps": 5.0,
            "error_rate_pct": 0.0,
            "cpu_percent": 20.0,
            "memory_percent": 30.0,
        }
    ]
    out = tmp_path / "metrics.csv"
    df = collector.save_to_csv(str(out))
    assert out.exists()
    assert len(df) == 1


# ---------------------------------------------------------------------------
# Layer 3: Historical Storage (integration tests, mocked MinIO)
# ---------------------------------------------------------------------------

def test_ensure_bucket_creates_when_missing():
    client = MagicMock()
    client.bucket_exists.return_value = False
    assert upload_to_minio.ensure_bucket(client) is True
    client.make_bucket.assert_called_once_with(upload_to_minio.BUCKET_NAME)


def test_ensure_bucket_skips_creation_when_present():
    client = MagicMock()
    client.bucket_exists.return_value = True
    assert upload_to_minio.ensure_bucket(client) is True
    client.make_bucket.assert_not_called()


def test_upload_partitioned_writes_one_object_per_component(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    df = pd.DataFrame(
        [
            {"component": "checkout", "latency_p95_ms": 1, "throughput_rps": 1,
             "error_rate_pct": 0, "cpu_percent": 1, "memory_percent": 1, "timestamp": "t1"},
            {"component": "cart", "latency_p95_ms": 2, "throughput_rps": 2,
             "error_rate_pct": 0, "cpu_percent": 2, "memory_percent": 2, "timestamp": "t2"},
        ]
    )
    client = MagicMock()
    uploaded = upload_to_minio.upload_partitioned(client, df, date="2026-01-01")

    assert uploaded == [
        "cart/2026-01-01/metrics.parquet",
        "checkout/2026-01-01/metrics.parquet",
    ]
    assert client.put_object.call_count == 2


def test_upload_to_minio_returns_false_when_csv_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("upload_to_minio.get_client", return_value=MagicMock()):
        assert upload_to_minio.upload_to_minio("does_not_exist.csv") is False


def test_get_client_builds_minio_client_with_expected_config():
    client = upload_to_minio.get_client()
    assert client is not None


def test_ensure_bucket_returns_false_on_s3_error():
    from minio.error import S3Error

    client = MagicMock()
    client.bucket_exists.side_effect = S3Error(
        code="AccessDenied", message="denied", resource="/", request_id="1",
        host_id="h", response=MagicMock(),
    )
    assert upload_to_minio.ensure_bucket(client) is False


def test_upload_to_minio_returns_false_when_bucket_check_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pd.DataFrame([{"component": "cart"}]).to_csv("metrics.csv", index=False)
    with patch("upload_to_minio.get_client", return_value=MagicMock()), \
         patch("upload_to_minio.ensure_bucket", return_value=False):
        assert upload_to_minio.upload_to_minio("metrics.csv") is False


def test_upload_to_minio_returns_false_when_dataframe_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pd.DataFrame(columns=["component"]).to_csv("metrics.csv", index=False)
    with patch("upload_to_minio.get_client", return_value=MagicMock()), \
         patch("upload_to_minio.ensure_bucket", return_value=True):
        assert upload_to_minio.upload_to_minio("metrics.csv") is False


def test_cli_main_invokes_upload_to_minio(tmp_path, monkeypatch, capsys):
    """Exercises upload_to_minio.py's __main__ block in-process (runpy).

    runpy re-executes the file fresh, so `from minio import Minio` inside
    that execution re-resolves against the live minio package - patching
    the class there (the true shared singleton) is what actually reaches
    it, unlike patching upload_to_minio.get_client on the already-imported
    module object.
    """
    import runpy

    import minio as minio_module

    class FakeMinioClient:
        def __init__(self, *a, **k):
            pass

        def bucket_exists(self, name):
            return True

    monkeypatch.setattr(minio_module, "Minio", FakeMinioClient)
    monkeypatch.chdir(tmp_path)  # no data/metrics.csv here -> early "File not found" return

    runpy.run_path(upload_to_minio.__file__, run_name="__main__")
    assert "File not found" in capsys.readouterr().out


def test_upload_to_minio_succeeds_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pd.DataFrame([
        {"component": "cart", "latency_p95_ms": 1, "throughput_rps": 1,
         "error_rate_pct": 0, "cpu_percent": 1, "memory_percent": 1, "timestamp": "t1"},
    ]).to_csv("metrics.csv", index=False)
    mock_client = MagicMock()
    with patch("upload_to_minio.get_client", return_value=mock_client), \
         patch("upload_to_minio.ensure_bucket", return_value=True):
        assert upload_to_minio.upload_to_minio("metrics.csv") is True
    mock_client.put_object.assert_called_once()


# ---------------------------------------------------------------------------
# Layer 4: Unified Dataset - data quality
#
# These build their own representative sample of the unified-dataset schema
# rather than depending on data/metrics.csv existing from a prior manual
# collector run - that made the suite fail on a clean checkout/CI runner
# whenever no one had run metrics_collector.py locally first. Schema/range/
# null checks are validated against this fixture instead.
# ---------------------------------------------------------------------------

@pytest.fixture
def unified_dataset_df():
    rows = []
    for component, latency, throughput, error_rate in [
        ("checkout", 280.0, 0.03, 0.0),
        ("checkout", 112.0, 0.045, 99.99),  # degraded
        ("product-catalog", 50.0, 3.2, 0.0),
        ("cart", 13.0, 0.85, 0.0),
        ("cart", 9.0, 0.9, 0.0),  # recovering
    ]:
        rows.append({
            "timestamp": "2026-09-16T10:57:35.415354",
            "component": component,
            "scenario": "degraded" if error_rate > 0 else "normal",
            "latency_p95_ms": latency,
            "throughput_rps": throughput,
            "error_rate_pct": error_rate,
            "cpu_percent": 1.5,
            "memory_percent": 20.0,
        })
    rows[-1]["scenario"] = "recovering"
    return pd.DataFrame(rows)


def test_csv_roundtrip_preserves_row_count(tmp_path, unified_dataset_df):
    out = tmp_path / "metrics.csv"
    unified_dataset_df.to_csv(out, index=False)
    assert out.exists()
    assert len(pd.read_csv(out)) == len(unified_dataset_df)


def test_csv_has_all_four_signal_columns(unified_dataset_df):
    for column in ("latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"):
        assert column in unified_dataset_df.columns


def test_all_three_components_present(unified_dataset_df):
    components = set(unified_dataset_df["component"].unique())
    assert {"checkout", "product-catalog", "cart"}.issubset(components)


def test_scenario_column_has_only_known_labels(unified_dataset_df):
    assert "scenario" in unified_dataset_df.columns
    assert set(unified_dataset_df["scenario"].unique()).issubset({"normal", "degraded", "recovering"})


def test_no_nulls_in_signal_columns(unified_dataset_df):
    for column in ("latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"):
        assert unified_dataset_df[column].isnull().sum() == 0


def test_metric_ranges_are_realistic(unified_dataset_df):
    df = unified_dataset_df
    assert (df["latency_p95_ms"] >= 0).all()
    assert (df["throughput_rps"] >= 0).all()
    assert (df["error_rate_pct"] >= 0).all() and (df["error_rate_pct"] <= 100).all()
    assert (df["cpu_percent"] >= 0).all()
    assert (df["memory_percent"] >= 0).all() and (df["memory_percent"] <= 100).all()


def test_parquet_round_trip_matches_csv_row_count(tmp_path, unified_dataset_df):
    csv_path = tmp_path / "metrics.csv"
    parquet_path = tmp_path / "metrics.parquet"
    unified_dataset_df.to_csv(csv_path, index=False)
    unified_dataset_df.to_parquet(parquet_path, index=False, engine="pyarrow")

    csv_df = pd.read_csv(csv_path)
    parquet_df = pd.read_parquet(parquet_path)
    assert len(csv_df) == len(parquet_df)
