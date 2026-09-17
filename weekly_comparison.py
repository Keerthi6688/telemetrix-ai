"""Layer 4: Week-over-week comparison metrics.

RFP Part B promises this explicitly ("Week-over-week comparison metrics
computed for trend detection") - it was never implemented as a discrete
feature; the dashboard's trend charts show the shape of change visually,
but no actual week-over-week delta was ever computed. This closes that
specific gap.
"""

import pandas as pd

FEATURES = ["latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"]


def compute_weekly_comparison(results_csv="anomaly_results.csv"):
    df = pd.read_csv(results_csv)
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
    df["iso_year"] = df["timestamp"].dt.isocalendar().year
    df["iso_week"] = df["timestamp"].dt.isocalendar().week
    df["week_key"] = df["iso_year"].astype(str) + "-W" + df["iso_week"].astype(str).str.zfill(2)

    weekly = (
        df.groupby(["component", "week_key"])
        .agg({**{f: "mean" for f in FEATURES}, "is_anomaly": "sum", "timestamp": "count"})
        .rename(columns={"timestamp": "row_count", "is_anomaly": "anomaly_count"})
        .reset_index()
        .sort_values(["component", "week_key"])
    )

    for f in FEATURES + ["anomaly_count"]:
        weekly[f"{f}_wow_delta"] = weekly.groupby("component")[f].diff()
        weekly[f"{f}_wow_pct_change"] = weekly.groupby("component")[f].pct_change() * 100

    return weekly


if __name__ == "__main__":
    weekly = compute_weekly_comparison()
    out = "weekly_comparison.csv"
    weekly.to_csv(out, index=False)
    print(f"{len(weekly)} component-week rows written to {out}\n")
    print(weekly[["component", "week_key", "latency_p95_ms", "latency_p95_ms_wow_pct_change",
                   "anomaly_count", "anomaly_count_wow_delta"]].to_string(index=False))
