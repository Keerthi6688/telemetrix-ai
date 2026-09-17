"""Layer 4: Unified Dataset build via PySpark.

RFP Part B named "Databricks Free Edition (or PySpark locally as fallback)"
for this layer; the pipeline had been using plain pandas instead (disclosed
deviation). This is the PySpark fallback actually implemented: reads one or
more raw collector CSVs, unions them into a single unified dataset, and
computes the per-component/per-scenario aggregate signal profile (mirroring
"Jobs aggregate raw signals into unified performance dataset... Time-series
history table built and stored" from the proposal).

Local Spark (master="local[*]") - no cluster/Databricks account needed, per
the proposal's own fallback language.
"""

import glob
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

FEATURES = ["latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"]


def get_spark(app_name="TelemetrixAI-Layer4"):
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.driver.memory", "1g")
        .getOrCreate()
    )


def build_unified_dataset(spark, input_csvs, out_dir="unified_dataset"):
    """Union raw collector CSVs into one Spark DataFrame - the 'unified
    performance dataset' - and write it out as the canonical time-series
    history table.
    """
    existing = [p for p in input_csvs if os.path.exists(p)]
    if not existing:
        raise FileNotFoundError(f"None of {input_csvs} exist")

    df = spark.read.option("header", True).option("inferSchema", True).csv(existing[0])
    for p in existing[1:]:
        next_df = spark.read.option("header", True).option("inferSchema", True).csv(p)
        df = df.unionByName(next_df)

    df = df.withColumn("timestamp", F.to_timestamp("timestamp"))
    os.makedirs(out_dir, exist_ok=True)
    df.write.mode("overwrite").parquet(out_dir)
    return df


def build_component_scenario_profile(df):
    """p50/p95/p99-style aggregate signal profile per component x scenario -
    the queryable 'unified performance dataset' the RFP describes, distinct
    from the raw per-sample rows.
    """
    agg_exprs = []
    for f in FEATURES:
        agg_exprs += [
            F.expr(f"percentile_approx({f}, 0.5)").alias(f"{f}_p50"),
            F.expr(f"percentile_approx({f}, 0.95)").alias(f"{f}_p95"),
            F.expr(f"percentile_approx({f}, 0.99)").alias(f"{f}_p99"),
            F.avg(f).alias(f"{f}_mean"),
        ]
    agg_exprs += [F.count("*").alias("row_count"), F.sum("is_anomaly").alias("anomaly_count")] \
        if "is_anomaly" in df.columns else [F.count("*").alias("row_count")]

    return df.groupBy("component", "scenario").agg(*agg_exprs).orderBy("component", "scenario")


if __name__ == "__main__":
    spark = get_spark()
    try:
        candidates = sorted(glob.glob("data/metrics*.csv")) or sorted(glob.glob("*metrics*.csv"))
        if not candidates:
            candidates = ["anomaly_results.csv"] if os.path.exists("anomaly_results.csv") else []
        print(f"Building unified dataset from: {candidates}")
        df = build_unified_dataset(spark, candidates)
        print(f"Unified dataset: {df.count()} rows, written to unified_dataset/ (Parquet)")

        profile = build_component_scenario_profile(df)
        print("\nComponent x Scenario signal profile:")
        profile.show(truncate=False)
        profile.coalesce(1).write.mode("overwrite").option("header", True).csv("unified_dataset_profile")
    finally:
        spark.stop()
