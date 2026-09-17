# TelemetrixAI

AI-powered platform performance monitoring, built for pSiddhi 3.0 (S3-P-03) on top of the official [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) (Astronomy Shop) as a stand-in for production microservices.

**3 instrumented components:** checkout (transaction processing) · product-catalog (read-heavy) · cart + Redis/Valkey (stateful/cache-dependent)
**4 signal types:** latency (p95), throughput (RPS), error rate (%), resource usage (CPU/memory %)

## Architecture

| Layer | What it does | Tool |
|---|---|---|
| 1. Instrumentation | 3 components emit traces/metrics/logs | OpenTelemetry Demo + OTel SDKs |
| 2. Telemetry Collection | Receives OTLP, routes to Prometheus + Jaeger | OTel Collector |
| 3. Historical Storage | Archives Parquet, partitioned by component/date | MinIO (S3-compatible) |
| 4. Data Processing | Builds the unified 4-signal dataset | Python (`metrics_collector.py`) |
| 5. ML Anomaly Detection | Flags degradation vs. seeded scenarios | scikit-learn + MLflow |
| 6. AI Annotation | Plain-language Normal/Degraded/Recovering reports | Gemini 2.5 Flash + Ollama (offline/QA) |
| 7. Reporting | Interactive dashboard | Power BI Desktop |

## Setup

**Prerequisites:** Docker + Docker Compose, Python 3.11+, a clone of `opentelemetry-demo` alongside this repo.

```bash
# 1. Bring up the OTel Demo with the observability stack (Jaeger, Prometheus) and
#    the memory-limit fix (see infra/compose.override.yaml for why it's needed)
cd ~/opentelemetry-demo
docker compose -f compose.yaml -f compose.observability.yaml -f ~/telemetrix-ai/infra/compose.override.yaml up -d

# 2. Start MinIO (not bundled with the demo)
docker run -d --name minio -p 9000:9000 -p 9001:9001 -v minio-data:/data \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  quay.io/minio/minio server /data --console-address ':9001'
# Note: pull from quay.io/minio/minio, not minio/minio - Docker Hub no longer
# serves anonymous pulls of the official image.

# 3. Set up the Python environment
cd ~/telemetrix-ai
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
# Collect a fresh 2-minute dataset (all 4 signals, all 3 components)
python metrics_collector.py

# Archive it to MinIO, partitioned by component/date
python upload_to_minio.py

# Run the QA suite with measured coverage (scoped to the 5 core pipeline
# modules - `--cov=.` also counts one-off scratch_*.py utility scripts and
# drags the number down without reflecting real pipeline coverage)
python -m pytest tests/ \
  --cov=metrics_collector --cov=upload_to_minio --cov=anomaly_detection \
  --cov=ai_annotation --cov=scenario_control \
  --cov-report=term --cov-report=html
```

**UIs:** Jaeger `localhost:16686` · Prometheus `localhost:9090` · MinIO console `localhost:9001` · Astronomy Shop frontend `localhost:8080`

## Known infra notes

- `checkout` and `product-catalog` ship with a 20MB memory cap in the demo's default compose config, which is tight enough to cause genuine thrashing (not a metrics bug) and 15s+ p95 latency even at idle. `infra/compose.override.yaml` raises this to 200MB so baseline ("Normal" scenario) data is representative.
- Latency/throughput/error-rate are all derived from the `traces_span_metrics_*` metric family (the collector's `span_metrics` connector), filtered to `span_kind="SPAN_KIND_SERVER"` — this is what's actually populated for these 3 services in this demo version (the more obvious `rpc_server_duration_*` metric name does not exist here).
