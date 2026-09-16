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


# ---------------------------------------------------------------------------
# Layer 4: Unified Dataset - data quality (integration tests on real collected data)
# ---------------------------------------------------------------------------

def test_csv_exists():
    assert os.path.exists("data/metrics.csv")


def test_csv_has_all_four_signal_columns():
    df = pd.read_csv("data/metrics.csv")
    assert len(df) > 0
    for column in ("latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"):
        assert column in df.columns


def test_all_three_components_present():
    df = pd.read_csv("data/metrics.csv")
    components = set(df["component"].unique())
    assert {"checkout", "product-catalog", "cart"}.issubset(components)


def test_scenario_column_has_only_known_labels():
    df = pd.read_csv("data/metrics.csv")
    assert "scenario" in df.columns
    assert set(df["scenario"].unique()).issubset({"normal", "degraded", "recovering"})


def test_no_nulls_in_signal_columns():
    df = pd.read_csv("data/metrics.csv")
    for column in ("latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"):
        assert df[column].isnull().sum() == 0


def test_metric_ranges_are_realistic():
    df = pd.read_csv("data/metrics.csv")
    assert (df["latency_p95_ms"] >= 0).all()
    assert (df["throughput_rps"] >= 0).all()
    assert (df["error_rate_pct"] >= 0).all() and (df["error_rate_pct"] <= 100).all()
    assert (df["cpu_percent"] >= 0).all()
    assert (df["memory_percent"] >= 0).all() and (df["memory_percent"] <= 100).all()


def test_parquet_exists_and_matches_csv_row_count():
    assert os.path.exists("data/metrics.parquet")
    csv_df = pd.read_csv("data/metrics.csv")
    parquet_df = pd.read_parquet("data/metrics.parquet")
    assert len(csv_df) == len(parquet_df)
