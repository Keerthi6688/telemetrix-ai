# Final-Term Submission - Content Draft (copy into the official .docx template)

This is a copy-paste source for the sections that are pure text/tables. Screenshots (Section 4 Evidence Blocks) and the Power BI visuals must be captured by you directly from your running system - see POWERBI_SETUP.md for that last step. Adjust D-IDs/EV-IDs to match whatever you used at Mid-Term.

---

## Section 2. Approved Proposal Recap

**2.1 Problem Statement (as approved)**
Platform engineering teams operating microservice architectures lack a unified, AI-annotated observability layer: metrics, traces, and logs live in separate tools, correlating a performance regression to its root cause is manual and slow, and there is no automated anomaly detection or plain-language incident summarization. TelemetrixAI addresses this for a representative 3-component microservice platform.

**2.2 Proposed Solution Summary (as approved)**
A 7-layer pipeline: (1) Instrumentation of 3 platform components (checkout, product-catalog, cart) via OpenTelemetry SDKs; (2) Telemetry Collection through an OTel Collector fanning out to Prometheus (metrics) and Jaeger (traces); (3) Historical Storage of unified telemetry as partitioned Parquet in MinIO; (4) Data Processing into a unified 4-signal dataset (latency, throughput, error rate, resource usage) per component; (5) ML Anomaly Detection via a per-component Isolation Forest trained on Normal-scenario data, tracked in MLflow; (6) AI-Annotated Reporting that turns anomaly output into a plain-language Normal/Degraded/Recovering assessment with root cause and severity, using Gemini 2.5 Flash as primary and Ollama as an offline/secondary backend; (7) an interactive Power BI dashboard for live exploration.

**2.3 Core Tools & AI Components (as approved)**
OpenTelemetry Demo, OpenTelemetry Collector, Prometheus, Jaeger, MinIO, Python (pandas, pyarrow), scikit-learn, MLflow, Google Gemini 2.5 Flash API, Ollama (local LLM), Power BI Desktop, pytest/pytest-cov, Docker Compose, Git/GitHub.

---

## Section 3. Progress Against Approved Plan

| ID | Planned Deliverable | Planned Window | Carried? | Status | Evidence |
|---|---|---|---|---|---|
| D-01 | Instrument 3 platform components with OpenTelemetry (Layer 1) | Mid-term | Y | Done | EV-01 |
| D-02 | Telemetry collection pipeline: OTel Collector -> Prometheus + Jaeger (Layer 2) | Mid-term | Y | Done | EV-01 |
| D-03 | Historical storage: MinIO + Parquet, partitioned by component/date (Layer 3) | Mid-term | N (reworked in Phase 2 - see Sec 8) | Done | EV-02 |
| D-04 | Unified 4-signal dataset: latency, throughput, error rate, resource usage (Layer 4) | Mid-term | N (2 signals at Mid-term, completed in Phase 2) | Done | EV-02 |
| D-05 | QA suite with measured coverage via pytest-cov | Mid-term | N (was estimated ~90% at Mid-term, now measured) | Done | EV-03 |
| D-06 | Scenario simulation: Normal / Degraded / Recovering via feature-flag injection | Phase 2 | N | Partial | EV-04 |
| D-07 | Layer 5: ML anomaly detection (Isolation Forest per component + MLflow tracking) | Phase 2 | N | Done | EV-05 |
| D-08 | Layer 6: AI-annotated report (Gemini primary / Ollama fallback) | Phase 2 | N | Done | EV-06 |
| D-09 | Layer 7: Power BI interactive dashboard | Phase 2 | N | Partial | EV-07 |
| D-10 | GitHub version control with incremental, documented commits | Mid-term | Y | Done | EV-01 |

*(Renumber to match your actual Mid-Term D-IDs if different - keep the sequence continuing from Mid-Term as the template requires.)*

### 3.1 Overall Final Self-Assessment

- **RFP-defined final checkpoint:** All 7 layers operational end-to-end on live infrastructure; anomaly detection validated against at least one seeded degradation scenario; AI-generated plain-language reporting; interactive dashboard.
- **% of overall project completed:** ~85-90% - all 7 layers are implemented and produce real, measured output end-to-end; the two partial items are (a) only 1 of 3 components has validated Degraded-scenario data (see Section 10), and (b) the Power BI report needs its visuals built in the Desktop GUI from the prepared dataset (data ready, .pbix not yet saved as of this document).
- **% reported at Mid-Term:** [fill in from your Mid-Term Section 3.1]
- **Demonstrable live, end-to-end:** Yes, partially (Layers 1-6 fully live; Layer 7 dashboard pending the GUI build step).

---

## Section 6. QA Progress

| Test Type | Tests written/run | Coverage (measured) | Target | Evidence |
|---|---|---|---|---|
| Unit tests (mocked Prometheus/MinIO) | 16 | - | - | EV-03 |
| Integration/data-quality tests (real collected data) | 6 | - | - | EV-03 |
| **Total** | **22, all passing** | **83% (`pytest --cov`, HTML report in `htmlcov/`)** | >=80% | EV-03 |

Coverage is a tool-measured figure (`pytest tests/ --cov=. --cov-report=html`), not an estimate - this directly resolves the Mid-Term feedback that coverage was reported as "~90%" without evidence. Breakdown: `metrics_collector.py` 68%, `upload_to_minio.py` 76%, `tests/test_layers.py` 100%.

---

## Section 7. Tool & Budget Reconciliation

| Tool (approved) | Approved tier & cost | Used? | Actual cost | Reason if changed |
|---|---|---|---|---|
| OpenTelemetry Demo + Collector | Free/OSS | Yes | Rs 0 | - |
| Prometheus | Free/OSS | Yes | Rs 0 | - |
| Jaeger | Free/OSS | Yes | Rs 0 | - |
| MinIO | Free/OSS | Yes | Rs 0 | - |
| Python / pandas / pyarrow | Free/OSS | Yes | Rs 0 | - |
| scikit-learn | Free/OSS | Yes | Rs 0 | - |
| MLflow | Free/OSS | Yes | Rs 0 | - |
| PyCaret | Free/OSS | **No** | Rs 0 | Incompatible with Python 3.14 (its dependency `cgi` module was removed from the stdlib); scikit-learn's IsolationForest alone was sufficient for the anomaly-detection scope, so PyCaret's model-comparison layer was dropped rather than downgrading Python. |
| Google Gemini 2.5 Flash API | Free tier | Partial | Rs 0 | Code path implemented and tested (`ai_annotation.py`); no API key was provisioned in time for this submission, so the deterministic fallback path generated the shipped report instead. Swapping in a `GOOGLE_API_KEY` env var activates it with no code change. |
| Ollama (local LLM) | Free/OSS | Partial | Rs 0 | Installed on the Windows host; not reachable from inside the WSL2 environment the pipeline runs in at submission time, so the same deterministic fallback served this run. |
| Power BI Desktop | Free | Partial | Rs 0 | Dataset prepared and export-ready (`data/anomaly_results.csv`); visuals to be built in the Desktop GUI (see Section 10). |
| Docker / Docker Compose | Free | Yes | Rs 0 | - |
| Git / GitHub | Free | Yes | Rs 0 | - |
| pytest / pytest-cov | Free/OSS | Yes | Rs 0 | - |

### 7.1 Budget Summary

| | |
|---|---|
| Approved budget ceiling | Rs 2,500 |
| Actual spend till Mid-Term | Rs 0 |
| Actual spend, Mid-Term to Final | Rs 0 |
| **Total actual spend** | **Rs 0** |
| Buffer remaining | Rs 2,500 |

---

## Section 8. Deviations from Approved Proposal

| Item | Approved plan | Actual implementation | Reason |
|---|---|---|---|
| Metric family for latency/throughput | `rpc_server_duration_*` (gRPC server metrics) | `traces_span_metrics_*` (span-metrics connector output), filtered to `span_kind="SPAN_KIND_SERVER"` | The demo version deployed does not emit `rpc_server_duration_*` at all - discovered by direct Prometheus inspection. The span-metrics connector output is the metric family actually populated for these 3 services and carries the same semantic meaning (per-RPC latency/count). |
| Feature-flag names for scenario injection | `cartServiceFailure`, `recommendationServiceCacheFailure` (as named in the proposal) | `cartFailure`, `paymentFailure` (as actually shipped in this OTel Demo version's `flagd` config) | The proposal's flag names don't exist in the deployed demo version; the closest equivalent flags that exist were used instead, confirmed via `flagd`'s own OFREP evaluation API. |
| PyCaret (Layer 5) | Rapid model comparison during development | Dropped; scikit-learn `IsolationForest` used directly | Python 3.14 removed the `cgi` stdlib module PyCaret depends on. Carried from Mid-Term - still stands. |
| checkout/product-catalog memory limit | Not specified in proposal (used demo defaults) | Raised from 20MB to 200MB via `infra/compose.override.yaml` | The demo's default 20MB cap caused genuine resource thrashing (92% mem, 212% CPU, 15s+ p95 latency at idle) that made "Normal" baseline data indistinguishable from a degraded scenario. This is an infrastructure correction, not a data-cleaning shortcut. |
| Degraded-scenario coverage | All 3 components exercised under seeded failure | Only checkout validated with real degraded telemetry within this submission's timeframe | `cartFailure` only triggers inside `CartService.EmptyCart`, called by checkout only after a *successful* payment - an interaction discovered empirically. product-catalog has no reliable failure-injection flag in this demo version (`productCatalogFailure`'s targeting rule is scoped to one hardcoded product ID). See Section 10 for the completion plan. |

---

## Section 9. Enhancements & Additional Value-Adds

| ID | Enhancement | Why / value | Status | Cost | Evidence |
|---|---|---|---|---|---|
| EN-01 | `scenario_control.py` - scripted, reproducible feature-flag scenario injection (vs. manual UI clicking) | Makes Normal/Degraded/Recovering transitions reproducible and documented, not a one-off manual demo | Done | Rs 0 | EV-04 |
| EN-02 | Root-cause signal attribution per anomaly (z-score against per-component normal baseline), not just a binary anomaly flag | Goes beyond "is this anomalous" to "which signal, by how much" - directly useful for an SRE, and feeds Layer 6's root-cause narrative | Done | Rs 0 | EV-05 |
| EN-03 | 3-tier AI backend fallback chain (Gemini -> Ollama -> deterministic template) in Layer 6 | Guarantees Layer 6 always produces a report regardless of API key/network availability at demo time, while keeping both RFP-specified backends as the primary path | Done | Rs 0 | EV-06 |
| EN-04 | Per-component (rather than global) Isolation Forest models | Each component has a very different normal operating range (cart ~8ms p95 vs checkout ~150-500ms); a single global model would mostly separate "which component" rather than genuine anomalies | Done | Rs 0 | EV-05 |

---

## Section 10. What Is NOT Completed + Future Scope

| Pending item | Why not completed | Flagged at Mid-Term? | Recommended future scope |
|---|---|---|---|
| Degraded-scenario validation for product-catalog and cart | `cartFailure` requires a successful checkout to reach `EmptyCart` (discovered empirically, not enough remaining time to build the direct-gRPC test client this would need); product-catalog has no reliable failure-injection flag in this demo version | N (discovered in Phase 2) | Build a small gRPC test client that calls `CartService.EmptyCart` directly to exercise `cartFailure` independent of the full checkout flow; for product-catalog, inject load/latency via a sidecar proxy (e.g., Toxiproxy) instead of relying on the demo's own flags |
| Gemini/Ollama live generation in the submitted run | No `GOOGLE_API_KEY` provisioned in time; Ollama installed on the Windows host but not reachable from the WSL2 environment the pipeline runs in | N | Provision a Gemini API key via `.env` (code path already implemented and tested); either run Ollama inside WSL2 directly or point `ai_annotation.py`'s Ollama host at the Windows host IP from WSL2 |
| Power BI `.pbix` file with built visuals | Requires interactive GUI work in Power BI Desktop; data export and exact build steps are ready (`data/anomaly_results.csv`, `POWERBI_SETUP.md`) but the file itself is not yet saved | N | Complete the 5-minute build per `POWERBI_SETUP.md` and screenshot each visual for the evidence pack |
| Recovering-scenario data collection | Time-boxed out of this session (a full Degraded -> flags-off -> stabilization -> Recovering capture needs ~10-15 minutes of wall-clock waiting) | N | Run `python scenario_control.py restore` after a Degraded capture, wait ~10 min, then `python metrics_collector.py --scenario recovering` |

---

## Section 11. Risks & Blockers - Final Status

| Risk / Blocker | Final Status | Mitigation taken | Final impact |
|---|---|---|---|
| Coverage reported without tool evidence (Mid-Term feedback) | Mitigated | Rewrote test suite with real mocked unit tests; measured 83% via `pytest --cov`, HTML report committed | None - fully resolved |
| Document format/naming inconsistency (Mid-Term feedback) | Mitigated | Adopted the official Final-Term template for this submission; standardized repo doc naming (`README.md`, `PROJECT_PHASE1_REPORT.md`) | None |
| Incomplete tool reconciliation table (Mid-Term feedback) | Mitigated | Section 7 above lists every approved tool including PyCaret (dropped) and partial-use items (Gemini, Ollama, Power BI), each with an explicit reason | None |
| Host machine ran out of disk space mid-Phase-2 (new, Week 2 of Phase 2), crashing Docker/WSL2 | Realised, then mitigated | Diagnosed root cause (0 bytes free on C:), user freed space, WSL2 VM restarted cleanly, all containers recovered via `restart: unless-stopped` with zero data loss (git history + collected data all intact) | ~30 minutes lost to diagnosis/recovery; no data or work lost |
| `cartFailure`/`paymentFailure` flag interaction blocked cart-specific degraded data | Accepted | Documented in Sections 8 and 10; checkout degradation fully validated instead | product-catalog and cart validated only against Normal-scenario false-positive rate, not a seeded failure |
