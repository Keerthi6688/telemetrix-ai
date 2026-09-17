"""Layer 5: ML Anomaly Detection.

Trains one Isolation Forest per component (checkout, product-catalog, cart)
on Normal-scenario data only, then scores Normal + Degraded data to validate
detection. Per-component models are used deliberately: each component has a
very different normal operating range (cart p95 ~8ms vs checkout ~150-500ms),
so a single global model would mostly split on "which component" rather than
genuine anomalies within a component.

Logs each run to MLflow (params, metrics, the model itself) per RFP Layer 5.
"""

import os

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = ["latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"]
COMPONENTS = ["checkout", "product-catalog", "cart"]


def load_labeled_dataset(paths):
    """Concatenate one or more collector output CSVs into a single labeled dataset."""
    frames = [pd.read_csv(p) for p in paths if os.path.exists(p)]
    if not frames:
        raise FileNotFoundError(f"None of {paths} exist")
    return pd.concat(frames, ignore_index=True)


def dominant_signal(row, normal_stats, component):
    """For an anomalous row, name the signal furthest (in z-score) from that
    component's normal mean - this is the 'flagged signal type' the RFP asks
    the anomaly output to carry alongside the flagged component.
    """
    stats = normal_stats[component]
    best_signal, best_z = None, -1
    for f in FEATURES:
        mean, std = stats[f]["mean"], stats[f]["std"]
        if not std or std < 1e-6:
            # Normal baseline was a constant (e.g. error_rate_pct always 0) -
            # any deviation at all is a categorical shift, not a statistical
            # z-score. Cap it instead of dividing by ~0 and reporting nonsense.
            z = 999.0 if abs(row[f] - mean) > 1e-6 else 0.0
        else:
            z = min(999.0, abs((row[f] - mean) / std))
        if z > best_z:
            best_signal, best_z = f, z
    return best_signal, round(best_z, 2)


def run(dataset_paths, contamination=0.1, out_csv="data/anomaly_results.csv"):
    df = load_labeled_dataset(dataset_paths)
    normal_df = df[df["scenario"] == "normal"]

    mlflow.set_experiment("telemetrixai-anomaly-detection")

    all_results = []
    normal_stats = {}

    with mlflow.start_run(run_name="isolation_forest_per_component"):
        mlflow.log_param("contamination", contamination)
        mlflow.log_param("features", FEATURES)
        mlflow.log_param("training_scenario", "normal")
        mlflow.log_param("total_rows", len(df))
        mlflow.log_param("normal_rows", len(normal_df))

        for component in COMPONENTS:
            comp_normal = normal_df[normal_df["component"] == component]
            comp_all = df[df["component"] == component].copy()
            if len(comp_normal) < 5 or comp_all.empty:
                print(f"Skipping {component}: insufficient normal data ({len(comp_normal)} rows)")
                continue

            normal_stats[component] = {
                f: {"mean": comp_normal[f].mean(), "std": comp_normal[f].std()} for f in FEATURES
            }

            model = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
            model.fit(comp_normal[FEATURES])

            comp_all["anomaly_score"] = -model.decision_function(comp_all[FEATURES])
            comp_all["is_anomaly"] = (model.predict(comp_all[FEATURES]) == -1).astype(int)

            flagged = comp_all.apply(
                lambda r: dominant_signal(r, normal_stats, component) if r["is_anomaly"] else (None, 0.0),
                axis=1,
            )
            comp_all["flagged_signal"] = [f[0] for f in flagged]
            comp_all["signal_zscore"] = [f[1] for f in flagged]

            mlflow.sklearn.log_model(
                model, f"model_{component}", skops_trusted_types=["sklearn.tree._tree.Tree"]
            )

            detection_rate = None
            degraded_rows = comp_all[comp_all["scenario"] == "degraded"]
            if len(degraded_rows) > 0:
                detection_rate = degraded_rows["is_anomaly"].mean()
                mlflow.log_metric(f"{component}_degraded_detection_rate", detection_rate)

            false_positive_rate = comp_all[comp_all["scenario"] == "normal"]["is_anomaly"].mean()
            mlflow.log_metric(f"{component}_normal_false_positive_rate", false_positive_rate)

            print(f"\n=== {component} ===")
            print(f"  Trained on {len(comp_normal)} normal rows")
            if detection_rate is not None:
                print(f"  Degraded detection rate: {detection_rate:.1%} ({len(degraded_rows)} degraded rows)")
            print(f"  Normal false-positive rate: {false_positive_rate:.1%}")

            all_results.append(comp_all)

        result_df = pd.concat(all_results, ignore_index=True)
        os.makedirs("data", exist_ok=True)
        result_df.to_csv(out_csv, index=False)
        mlflow.log_artifact(out_csv)
        print(f"\nSaved {len(result_df)} scored rows to {out_csv}")

    return result_df


if __name__ == "__main__":
    paths = [
        "data/metrics.csv",
        "data/metrics_degraded_checkout.csv",
        "data/metrics_degraded_cart.csv",
        "data/metrics_recovering.csv",
    ]
    run(paths)
