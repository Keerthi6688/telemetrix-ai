# TelemetrixAI - Phase 1 Implementation Report

## Architecture Implemented

### Layer 1: Instrumentation
- OpenTelemetry Demo (Astronomy Shop) deployed with its full microservice set on Docker
- 3 platform components instrumented per approved proposal:
  - checkout (transaction-processing, latency-sensitive)
  - product-catalog (read-heavy, throughput-sensitive)
  - cart + Redis/Valkey cache (stateful, cache-dependent)

### Layer 2: Telemetry Collection
- OTel Collector receiving traces, metrics, and logs via OTLP
- Collector's observability config layer enabled, exporting to Jaeger (traces) and Prometheus (metrics via native OTLP receiver)
- All 3 components confirmed emitting via the `traces_span_metrics_*` metric family (span_metrics connector) and `container_*` resource metrics

### Layer 3: Historical Storage
- MinIO S3-compatible storage deployed (`telemetry-raw` bucket)
- Parquet file format for archival
- Data partitioned by component/date: `<component>/<date>/metrics.parquet` (one object per component per collection run)

### Layer 4: Data Processing
- Python data pipeline (`metrics_collector.py`) queries Prometheus and builds the unified dataset
- 4 signal types collected (RFP minimum):
  - `latency_p95_ms` — p95 request latency (SPAN_KIND_SERVER only)
  - `throughput_rps` — requests per second
  - `error_rate_pct` — % of requests with an error span status
  - `cpu_percent`, `memory_percent` — container resource usage

## Data Collected

**Dataset Statistics (latest collection):**
- Total Records: 36
- Components Monitored: 3 (checkout, product-catalog, cart)
- Signal Types: 4 (latency_p95_ms, throughput_rps, error_rate_pct, cpu_percent, memory_percent)
- Data Format: CSV + Parquet, archived to MinIO partitioned by component/date
- Scenario: Normal baseline (avg latency 266ms, 0% errors — see note below)

**Note on baseline data quality:** an earlier collection run showed checkout/product-catalog p95 latency pegged near 15,000ms even at idle. Root cause: the OTel Demo's default compose config caps both containers at 20MB memory, and product-catalog was genuinely thrashing (92% mem, 212% CPU) under that limit. Raised to 200MB via `infra/compose.override.yaml` — this is a real infrastructure fix, not a data-cleaning shortcut, and is disclosed as a deviation in the final submission.

## Testing & Validation

**Quality Assurance (measured, not estimated):**
- 22 automated tests, all passing (`pytest tests/ --cov=. --cov-report=html`)
- Measured coverage: 83% overall (`metrics_collector.py` 68%, `upload_to_minio.py` 76%, tests 100%) — see `htmlcov/index.html`
- Unit tests mock Prometheus/MinIO so they run without live infra; data-quality tests run against the real collected dataset
- Covers: signal-extraction logic, null checks, value-range checks, component coverage, bucket partitioning logic

## Technology Stack

- Docker / Docker Compose - Containerization and orchestration
- OpenTelemetry Demo + OTel Collector - Instrumentation and telemetry pipeline
- Jaeger - Distributed trace visualization
- Prometheus - Metrics collection (native OTLP receiver)
- MinIO - S3-compatible historical storage
- Python, Pandas, PyArrow - Data processing & pipeline
- pytest, pytest-cov - Testing framework and measured coverage
- Git/GitHub - Version control

## Files Delivered

- `metrics_collector.py` - Layer 2-4 collection module (4 signal types)
- `upload_to_minio.py` - Layer 3 storage module (partitioned by component/date)
- `infra/compose.override.yaml` - Docker Compose override raising checkout/product-catalog memory limits
- `tests/test_layers.py` - QA test suite (22 tests)
- `requirements.txt` - Pinned Python dependencies
- `data/metrics.csv`, `data/metrics.parquet` - Unified dataset

## Current Status

**Phase 1 (Layers 1-4 + QA foundation): Complete and verified against live infrastructure.**

**Next (Phase 2):**
- Layer 5: ML anomaly detection (scikit-learn Isolation Forest + MLflow)
- Layer 6: AI-annotated reports (Gemini 2.5 Flash + Ollama offline fallback)
- Layer 7: Power BI dashboard
- Scenario simulation: Normal / Degraded / Recovering via OTel Demo feature flags

---
**Last updated: 2026-09-16**
