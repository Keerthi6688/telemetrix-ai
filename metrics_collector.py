import os
import time
from datetime import datetime

import pandas as pd
import requests

PROMETHEUS_URL = "http://localhost:9090"
COMPONENTS = ["checkout", "product-catalog", "cart"]


class MetricsCollector:
    """Collects all 4 RFP-required signal types (latency, throughput, error rate,
    resource usage) from Prometheus for the 3 instrumented platform components
    (Layer 2-4: Telemetry Collection -> Data Processing).
    """

    def __init__(self, prometheus_url=PROMETHEUS_URL):
        self.prometheus_url = prometheus_url
        self.data = []

    def query_prometheus(self, query):
        """Run an instant PromQL query against Prometheus's HTTP API."""
        endpoint = f"{self.prometheus_url}/api/v1/query"
        try:
            response = requests.get(endpoint, params={"query": query}, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def _first_value(result):
        """Extract the first scalar sample from a Prometheus vector result.

        Returns None if the query failed or returned no series, so callers
        can tell "no data yet" apart from a genuine value of 0.
        """
        if not result or result.get("status") != "success":
            return None
        series = result.get("data", {}).get("result", [])
        if not series:
            return None
        try:
            return float(series[0]["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    def get_latency_p95_ms(self, component):
        """Signal 1/4: p95 request latency for incoming requests (SPAN_KIND_SERVER only,
        so internal/background spans and downstream client calls don't skew it).
        """
        query = (
            "histogram_quantile(0.95, sum(rate("
            f'traces_span_metrics_duration_milliseconds_bucket{{service_name="{component}",span_kind="SPAN_KIND_SERVER"}}[5m]'
            ")) by (le))"
        )
        value = self._first_value(self.query_prometheus(query))
        return value if value is not None else 0.0

    def get_throughput_rps(self, component):
        """Signal 2/4: incoming request throughput, from span-metrics call count.
        Uses a 5m window to match the collector's ~60s metric export interval -
        a 1m window can under-sample and misreport a live service as 0 RPS.
        """
        query = (
            "sum(rate(traces_span_metrics_calls_total"
            f'{{service_name="{component}",span_kind="SPAN_KIND_SERVER"}}[5m]))'
        )
        value = self._first_value(self.query_prometheus(query))
        return value if value is not None else 0.0

    def get_error_rate_pct(self, component):
        """Signal 3/4: % of incoming requests with an error span status, over the last 5 minutes."""
        total_query = (
            "sum(rate(traces_span_metrics_calls_total"
            f'{{service_name="{component}",span_kind="SPAN_KIND_SERVER"}}[5m]))'
        )
        error_query = (
            "sum(rate(traces_span_metrics_calls_total"
            f'{{service_name="{component}",span_kind="SPAN_KIND_SERVER",status_code="STATUS_CODE_ERROR"}}[5m]))'
        )
        total = self._first_value(self.query_prometheus(total_query)) or 0.0
        errors = self._first_value(self.query_prometheus(error_query)) or 0.0
        if total <= 0:
            return 0.0
        # rate() over sparse, low-volume counters can overshoot 100% by a
        # fraction of a percent when a burst of errors lands inside the
        # window slightly unevenly - clamp to a valid percentage.
        return min(100.0, max(0.0, (errors / total) * 100))

    def get_cpu_percent(self, component):
        """Signal 4/4 (a): container CPU utilization for the component."""
        query = f'container_cpu_utilization_ratio{{container_name="{component}"}}'
        value = self._first_value(self.query_prometheus(query))
        return value if value is not None else 0.0

    def get_memory_percent(self, component):
        """Signal 4/4 (b): container memory utilization for the component."""
        query = f'container_memory_percent_ratio{{container_name="{component}"}}'
        value = self._first_value(self.query_prometheus(query))
        return value if value is not None else 0.0

    def get_metrics_for_component(self, component, scenario="normal"):
        """Collect one data point covering all 4 required signal types for a component.

        `scenario` labels the point as normal/degraded/recovering (RFP Section 6)
        so Layer 5 can train on normal data and validate against the others.
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "scenario": scenario,
            "latency_p95_ms": round(self.get_latency_p95_ms(component), 2),
            "throughput_rps": round(self.get_throughput_rps(component), 4),
            "error_rate_pct": round(self.get_error_rate_pct(component), 4),
            "cpu_percent": round(self.get_cpu_percent(component), 4),
            "memory_percent": round(self.get_memory_percent(component), 4),
        }

    def collect_from_all_components(self, duration_minutes=2, interval_seconds=10, components=None, scenario="normal"):
        """Collect metrics from all 3 components repeatedly for the given duration."""
        components = components or COMPONENTS
        print(f"Collecting metrics for {duration_minutes} minute(s)... [scenario={scenario}]\n")

        end_time = time.time() + (duration_minutes * 60)
        collection_count = 0

        while time.time() < end_time:
            for component in components:
                metrics = self.get_metrics_for_component(component, scenario=scenario)
                self.data.append(metrics)
                collection_count += 1

                print(f"[{metrics['timestamp']}] {component}")
                print(f"  latency_p95_ms={metrics['latency_p95_ms']}")
                print(f"  throughput_rps={metrics['throughput_rps']}")
                print(f"  error_rate_pct={metrics['error_rate_pct']}")
                print(f"  cpu_percent={metrics['cpu_percent']}")
                print(f"  memory_percent={metrics['memory_percent']}\n")

            time.sleep(interval_seconds)

        print(f"\nCollection complete: {collection_count} data points")
        return self.data

    def save_to_csv(self, filepath):
        """Save collected data to CSV (Layer 4 - unified dataset)."""
        df = pd.DataFrame(self.data)
        df.to_csv(filepath, index=False)

        print(f"Saved {len(df)} records to {filepath}")
        print("\nDataset Summary:")
        print(f"  Components: {df['component'].unique().tolist()}")
        print(f"  Records: {len(df)}")
        print(f"  Avg Latency: {df['latency_p95_ms'].mean():.2f} ms")
        print(f"  Avg Throughput: {df['throughput_rps'].mean():.2f} RPS")
        print(f"  Avg Error Rate: {df['error_rate_pct'].mean():.4f} %")
        print(f"  Avg CPU: {df['cpu_percent'].mean():.2f} %")
        print(f"  Avg Memory: {df['memory_percent'].mean():.2f} %")

        return df

    def save_to_parquet(self, filepath):
        """Save collected data to Parquet (Layer 3 - MinIO historical archive)."""
        df = pd.DataFrame(self.data)
        df.to_parquet(filepath, index=False, engine="pyarrow")

        print(f"Saved {len(df)} records to {filepath} (Parquet)")
        return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collect TelemetrixAI metrics from Prometheus")
    parser.add_argument("--scenario", default="normal", choices=["normal", "degraded", "recovering"])
    parser.add_argument("--duration", type=float, default=2.0, help="collection duration in minutes")
    parser.add_argument("--interval", type=int, default=10, help="seconds between samples")
    parser.add_argument("--out-prefix", default="data/metrics", help="output path prefix (no extension)")
    args = parser.parse_args()

    collector = MetricsCollector()
    collector.collect_from_all_components(
        duration_minutes=args.duration, interval_seconds=args.interval, scenario=args.scenario
    )

    os.makedirs("data", exist_ok=True)
    collector.save_to_csv(f"{args.out_prefix}.csv")
    collector.save_to_parquet(f"{args.out_prefix}.parquet")

    print(f"\nLayers 2-4: Metrics collected (4 signal types, scenario={args.scenario}) and stored!")
