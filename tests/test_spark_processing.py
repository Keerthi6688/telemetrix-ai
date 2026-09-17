"""Layer 4: PySpark unified-dataset build - the RFP's named Databricks/
PySpark fallback, actually implemented (previously plain pandas only).
Session-scoped Spark fixture since JVM/context startup is slow (~60-90s).
"""

import pytest

import spark_processing as sp


@pytest.fixture(scope="module")
def spark():
    session = sp.get_spark(app_name="test-spark-processing")
    yield session
    session.stop()


@pytest.fixture
def raw_csvs(tmp_path):
    normal = tmp_path / "metrics.csv"
    degraded = tmp_path / "metrics_degraded.csv"
    normal.write_text(
        "timestamp,component,scenario,latency_p95_ms,throughput_rps,error_rate_pct,cpu_percent,memory_percent\n"
        "2026-01-01T00:00:00,cart,normal,13.0,0.85,0.0,3.3,48.8\n"
        "2026-01-01T00:00:10,cart,normal,14.0,0.90,0.0,3.4,49.0\n"
    )
    degraded.write_text(
        "timestamp,component,scenario,latency_p95_ms,throughput_rps,error_rate_pct,cpu_percent,memory_percent\n"
        "2026-01-01T01:00:00,checkout,degraded,112.0,0.046,99.99,0.45,7.86\n"
    )
    return [str(normal), str(degraded)]


def test_build_unified_dataset_unions_all_csvs(spark, raw_csvs, tmp_path):
    out_dir = str(tmp_path / "unified")
    df = sp.build_unified_dataset(spark, raw_csvs, out_dir=out_dir)
    assert df.count() == 3
    assert set(r["component"] for r in df.select("component").distinct().collect()) == {"cart", "checkout"}


def test_build_unified_dataset_raises_when_no_files_exist(spark, tmp_path):
    with pytest.raises(FileNotFoundError):
        sp.build_unified_dataset(spark, [str(tmp_path / "nope.csv")])


def test_build_component_scenario_profile_computes_percentiles(spark, raw_csvs, tmp_path):
    df = sp.build_unified_dataset(spark, raw_csvs, out_dir=str(tmp_path / "unified2"))
    profile = sp.build_component_scenario_profile(df)
    rows = {r["component"] + "/" + r["scenario"]: r for r in profile.collect()}
    assert "cart/normal" in rows
    assert "checkout/degraded" in rows
    assert rows["cart/normal"]["row_count"] == 2
    assert rows["cart/normal"]["latency_p95_ms_mean"] == pytest.approx(13.5)
