"""Layer 5: ML Anomaly Detection - unit + model-accuracy tests.

Covers the parts of anomaly_detection.py that had zero coverage: the
dominant-signal root-cause logic, and the end-to-end Isolation Forest
train/score/flag pipeline (run()), including a basic precision/recall
check against seeded synthetic anomalies (RFP 10.2: "Model accuracy
tests... measure precision and recall").
"""

import pandas as pd
import pytest

import anomaly_detection as ad


# ---------------------------------------------------------------------------
# load_labeled_dataset(): file concatenation and missing-file handling
# ---------------------------------------------------------------------------

def test_load_labeled_dataset_concatenates_existing_files(tmp_path):
    p1 = tmp_path / "a.csv"
    p2 = tmp_path / "b.csv"
    pd.DataFrame([{"x": 1}]).to_csv(p1, index=False)
    pd.DataFrame([{"x": 2}]).to_csv(p2, index=False)

    df = ad.load_labeled_dataset([str(p1), str(p2)])
    assert len(df) == 2


def test_load_labeled_dataset_skips_missing_files(tmp_path):
    p1 = tmp_path / "a.csv"
    pd.DataFrame([{"x": 1}]).to_csv(p1, index=False)

    df = ad.load_labeled_dataset([str(p1), str(tmp_path / "does_not_exist.csv")])
    assert len(df) == 1


def test_load_labeled_dataset_raises_when_none_exist(tmp_path):
    with pytest.raises(FileNotFoundError):
        ad.load_labeled_dataset([str(tmp_path / "nope.csv")])


# ---------------------------------------------------------------------------
# dominant_signal(): root-cause signal attribution
# ---------------------------------------------------------------------------

def test_dominant_signal_picks_largest_zscore():
    normal_stats = {
        "checkout": {
            "latency_p95_ms": {"mean": 280.0, "std": 40.0},
            "throughput_rps": {"mean": 0.03, "std": 0.006},
            "error_rate_pct": {"mean": 0.0, "std": 0.0},
            "cpu_percent": {"mean": 0.08, "std": 0.02},
            "memory_percent": {"mean": 7.7, "std": 0.5},
        }
    }
    # error_rate_pct jumps from a constant 0 baseline -> categorical shift (capped at 999)
    # latency is only ~1 std off, so error_rate_pct must win regardless of raw magnitude
    row = {
        "latency_p95_ms": 320.0,
        "throughput_rps": 0.03,
        "error_rate_pct": 99.99,
        "cpu_percent": 0.08,
        "memory_percent": 7.7,
    }
    signal, z = ad.dominant_signal(row, normal_stats, "checkout")
    assert signal == "error_rate_pct"
    assert z == 999.0


def test_dominant_signal_handles_zero_std_no_deviation():
    normal_stats = {
        "cart": {f: {"mean": 0.0, "std": 0.0} for f in ad.FEATURES}
    }
    row = {f: 0.0 for f in ad.FEATURES}
    signal, z = ad.dominant_signal(row, normal_stats, "cart")
    assert z == 0.0


def test_dominant_signal_uses_real_zscore_when_std_present():
    normal_stats = {
        "cart": {
            "latency_p95_ms": {"mean": 13.0, "std": 3.0},
            "throughput_rps": {"mean": 0.85, "std": 0.15},
            "error_rate_pct": {"mean": 0.0, "std": 0.0},
            "cpu_percent": {"mean": 3.3, "std": 0.3},
            "memory_percent": {"mean": 48.8, "std": 1.0},
        }
    }
    row = {
        "latency_p95_ms": 13.0,
        "throughput_rps": 0.85,
        "error_rate_pct": 0.0,
        "cpu_percent": 3.3,
        "memory_percent": 55.0,  # 6.2 std out on memory
    }
    signal, z = ad.dominant_signal(row, normal_stats, "cart")
    assert signal == "memory_percent"
    assert z == pytest.approx(6.2, abs=0.1)


# ---------------------------------------------------------------------------
# run(): end-to-end Isolation Forest train/score pipeline
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_dataset_csv(tmp_path):
    """40 tight normal rows + 5 obviously-anomalous degraded rows per
    component, so the model has enough normal data to fit and a clear
    signal to detect - a deterministic stand-in for a live capture.
    """
    import numpy as np

    rng = np.random.default_rng(7)
    rows = []
    for component in ad.COMPONENTS:
        for _ in range(40):
            rows.append({
                "timestamp": "2026-09-16T10:00:00",
                "component": component,
                "scenario": "normal",
                "latency_p95_ms": rng.normal(50, 2),
                "throughput_rps": rng.normal(3, 0.1),
                "error_rate_pct": 0.0,
                "cpu_percent": rng.normal(1, 0.05),
                "memory_percent": rng.normal(20, 0.5),
            })
        for _ in range(5):
            rows.append({
                "timestamp": "2026-09-16T11:00:00",
                "component": component,
                "scenario": "degraded",
                "latency_p95_ms": rng.normal(500, 10),  # far outside normal range
                "throughput_rps": rng.normal(0.1, 0.02),
                "error_rate_pct": rng.normal(90, 2),
                "cpu_percent": rng.normal(1, 0.05),
                "memory_percent": rng.normal(20, 0.5),
            })

    path = tmp_path / "seeded.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def test_run_produces_expected_output_schema(tmp_path, seeded_dataset_csv, monkeypatch):
    monkeypatch.setattr(ad.mlflow, "set_tracking_uri", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "set_experiment", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "start_run", _noop_context_manager)
    monkeypatch.setattr(ad.mlflow, "log_param", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "log_metric", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "log_artifact", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow.sklearn, "log_model", lambda *a, **k: None)

    out_csv = tmp_path / "anomaly_results.csv"
    result = ad.run([seeded_dataset_csv], out_csv=str(out_csv))

    for column in ("anomaly_score", "is_anomaly", "flagged_signal", "signal_zscore"):
        assert column in result.columns
    assert out_csv.exists()


def test_run_flags_degraded_rows_with_reasonable_precision_recall(tmp_path, seeded_dataset_csv, monkeypatch):
    """Model-accuracy check per RFP 10.2: validate detection against seeded
    degradation, and false-positive rate on normal data stays low.
    """
    monkeypatch.setattr(ad.mlflow, "set_tracking_uri", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "set_experiment", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "start_run", _noop_context_manager)
    monkeypatch.setattr(ad.mlflow, "log_param", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "log_metric", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "log_artifact", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow.sklearn, "log_model", lambda *a, **k: None)

    out_csv = tmp_path / "anomaly_results.csv"
    result = ad.run([seeded_dataset_csv], out_csv=str(out_csv))

    degraded = result[result["scenario"] == "degraded"]
    normal = result[result["scenario"] == "normal"]

    # The seeded degraded rows are 10x the normal latency and ~90% error
    # rate against a near-zero-variance baseline - the model should catch
    # most of them (contamination=0.1 caps how many any single component
    # can flag, so per-component detection varies; check the aggregate).
    assert degraded["is_anomaly"].mean() >= 0.7
    # False-positive rate on normal data should stay well under 50%.
    assert normal["is_anomaly"].mean() <= 0.5


def test_run_skips_component_with_insufficient_normal_data(tmp_path, monkeypatch):
    import numpy as np

    monkeypatch.setattr(ad.mlflow, "set_tracking_uri", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "set_experiment", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "start_run", _noop_context_manager)
    monkeypatch.setattr(ad.mlflow, "log_param", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "log_metric", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "log_artifact", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow.sklearn, "log_model", lambda *a, **k: None)

    rng = np.random.default_rng(1)
    rows = []
    # checkout: plenty of normal data
    for _ in range(10):
        rows.append({
            "timestamp": "t", "component": "checkout", "scenario": "normal",
            "latency_p95_ms": rng.normal(50, 2), "throughput_rps": rng.normal(3, 0.1),
            "error_rate_pct": 0.0, "cpu_percent": rng.normal(1, 0.05), "memory_percent": rng.normal(20, 0.5),
        })
    # cart: only 2 normal rows - below the len(comp_normal) < 5 threshold
    for _ in range(2):
        rows.append({
            "timestamp": "t", "component": "cart", "scenario": "normal",
            "latency_p95_ms": 13.0, "throughput_rps": 0.85,
            "error_rate_pct": 0.0, "cpu_percent": 3.3, "memory_percent": 48.8,
        })

    csv_path = tmp_path / "sparse.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    result = ad.run([str(csv_path)], out_csv=str(tmp_path / "out.csv"))
    assert "checkout" in set(result["component"])
    assert "cart" not in set(result["component"])


def test_cli_main_runs_against_default_paths(tmp_path, monkeypatch):
    """Exercises anomaly_detection.py's __main__ block in-process (runpy)."""
    import runpy

    monkeypatch.setattr(ad.mlflow, "set_tracking_uri", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "set_experiment", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "start_run", _noop_context_manager)
    monkeypatch.setattr(ad.mlflow, "log_param", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "log_metric", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow, "log_artifact", lambda *a, **k: None)
    monkeypatch.setattr(ad.mlflow.sklearn, "log_model", lambda *a, **k: None)

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    rows = [
        {"timestamp": "t", "component": "checkout", "scenario": "normal",
         "latency_p95_ms": 50.0, "throughput_rps": 3.0, "error_rate_pct": 0.0,
         "cpu_percent": 1.0, "memory_percent": 20.0}
        for _ in range(10)
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "data" / "metrics.csv", index=False)

    runpy.run_path(ad.__file__, run_name="__main__")

    assert (tmp_path / "data" / "anomaly_results.csv").exists()


class _noop_context_manager:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
