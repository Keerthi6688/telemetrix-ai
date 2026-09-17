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
| D-09 | Layer 7: Power BI interactive dashboard (2 pages, 9 visuals: latency trend, throughput trend, anomaly count, error-rate matrix, root-cause detail table, AI narrative panel, scenario/component slicers) | Phase 2 | N | Done | EV-07 |
| D-10 | GitHub version control with incremental, documented commits | Mid-term | Y | Done | EV-01 |

*(Renumber to match your actual Mid-Term D-IDs if different - keep the sequence continuing from Mid-Term as the template requires.)*

**Note on D-10:** during this Final-Term prep session, work happened in a Windows-side working copy of the project (kept separately because Power BI Desktop needs native Windows filesystem access for the dashboard) that had no `.git` history of its own. That copy was mistakenly `git init`-ed from scratch mid-session before the canonical repository was located. The real, semester-spanning repository - with genuine incremental commits from 2026-07-15 (Phase 1) through today, and an already-configured GitHub remote (`https://github.com/Keerthi6688/telemetrix-ai`) - lives at `~/telemetrix-ai` inside this machine's WSL2 environment, which is also where the live Docker/OTel Demo stack runs. All Final-Term work (new tests, dashboard files, bug fixes, CI config) has been merged into that real repository and committed there; the stray Windows-side git history was not treated as canonical.

### 3.1 Overall Final Self-Assessment

- **RFP-defined final checkpoint:** All 7 layers operational end-to-end on live infrastructure; anomaly detection validated against at least one seeded degradation scenario; AI-generated plain-language reporting; interactive dashboard.
- **% of overall project completed:** ~90-95% - all 7 layers are implemented and produce real, measured output end-to-end, including a built (not just prepared) Power BI dashboard, a 100%-passing QA suite, and genuine CI/version control. The remaining gap is entirely data-collection, not missing functionality: only 1 of 3 components has validated Degraded-scenario data, and no component yet has a captured Recovering-scenario window (see Section 10) - the live stack was found unstable (load-generator returning 503s, zero live telemetry) when a real capture was attempted during this session, so this needs to be redone once the stack is confirmed healthy.
- **% reported at Mid-Term:** [fill in from your Mid-Term Section 3.1]
- **Demonstrable live, end-to-end:** Yes (all 7 layers live, including the Power BI dashboard), contingent on the OTel Demo stack being healthy at demo time - verify with `curl http://localhost:9090/api/v1/query?query=up` and Locust's own dashboard before the live session.

---

## Section 6. QA Progress

| Test Type | Tests written/run | Layer(s) | Evidence |
|---|---|---|---|
| Unit tests (mocked Prometheus/MinIO/flagd/Gemini/Ollama) | 38 | L1, L2, L3, L6 | EV-03 |
| Integration/data-quality tests (unified-dataset schema, CSV/Parquet round-trip) | 6 | L3, L4 | EV-03 |
| ML model-accuracy tests (Isolation Forest precision/recall on seeded anomalies, dataset loading, insufficient-data handling) | 6 | L5 | EV-03 |
| AI evaluation tests (scenario classification, severity thresholds, provider fallback, end-to-end report generation) | 13 | L6 | EV-03 |
| CLI entry-point tests (in-process via `runpy`, so every script's actual command-line invocation path is exercised, not just its library functions) | 10 | L1-L6 | EV-03 |
| **Total** | **73, all passing** | L1-L6 | EV-03 |

**Coverage: 100%** across all 5 core pipeline modules (`pytest tests/ --cov=metrics_collector --cov=upload_to_minio --cov=anomaly_detection --cov=ai_annotation --cov=scenario_control --cov-report=html`) - `ai_annotation.py`, `anomaly_detection.py`, `metrics_collector.py`, `scenario_control.py`, and `upload_to_minio.py` are all fully covered, including their CLI (`__main__`) entry points. Tool-measured and reproduced independently in two separate environments (Windows/Python 3.11 and the real WSL2 pipeline environment/Python 3.14) with identical results. HTML report committed at `htmlcov/index.html`.

Layers 5 (ML anomaly detection) and 6 (AI annotation) previously had **zero** automated test coverage despite being the two layers the RFP calls out by name for model-accuracy and AI-evaluation testing (Section 10.2) - this was a real gap identified during Final-Term self-review and closed in this session, not carried over as already-done from Mid-Term.

Layer 7 (Power BI dashboard) remains outside the automated suite by nature (a GUI report file, not code) - verified manually per `POWERBI_SETUP.md`. `scenario_control.py`'s flag-toggling logic is now unit-tested against a temp config file (6 tests); the live flagd/Docker integration itself is still verified manually.

---

## Section 7. Tool & Budget Reconciliation

| Tool (approved) | Approved tier & cost | Used? | Actual cost | Reason if changed |
|---|---|---|---|---|
| OpenTelemetry Demo + Collector | Free/OSS | Yes | Rs 0 | - |
| Prometheus | Free/OSS | Yes | Rs 0 | - |
| Jaeger | Free/OSS | Yes | Rs 0 | - |
| MinIO | Free/OSS | Yes | Rs 0 | - |
| Databricks Free Edition / PySpark | Free/OSS | **Yes (PySpark, local fallback)** | Rs 0 | `spark_processing.py`: a real local PySpark job (Spark 4.x, `master="local[*]"`, per the proposal's own "PySpark locally as fallback" language) that unions raw collector CSVs into the unified dataset, writes it as Parquet, and computes a genuine p50/p95/p99 + mean signal profile per component x scenario. Databricks Free Edition itself was not used (no cloud account provisioned), but the named local fallback is real and tested, not a pandas substitution. Metrics collection and ML scoring (Layers 1-2, 5) still use pandas, which was never part of this specific promise. |
| Azure Monitor Free Tier | Free tier | **No (deliberate)** | Rs 0 | Proposed as a second cloud-based metric sink alongside Prometheus (Layer 2); consciously not pursued - it needs an actual provisioned Azure resource (Log Analytics Workspace + connection string), not just a credential, and Prometheus (local) + Jaeger (traces) already fully cover the demo's telemetry needs without adding a cloud account dependency. No budget impact since it was never provisioned. |
| Great Expectations | Free/OSS | **No** | Rs 0 | Data validation (schema completeness, null checks, range checks) is implemented as plain pytest assertions in `tests/test_layers.py` instead of a dedicated data-validation framework - same checks the RFP specifies, different tool. |
| Python / pandas / pyarrow | Free/OSS | Yes | Rs 0 | - |
| scikit-learn | Free/OSS | Yes | Rs 0 | - |
| MLflow | Free/OSS | Yes | Rs 0 | - |
| PyCaret | Free/OSS | **No** | Rs 0 | Incompatible with Python 3.14 (its dependency `cgi` module was removed from the stdlib); scikit-learn's IsolationForest alone was sufficient for the anomaly-detection scope, so PyCaret's model-comparison layer was dropped rather than downgrading Python. |
| Google Gemini 2.5 Flash API | Free tier | **No (deliberate)** | Rs 0 | Code path implemented and unit-tested (`ai_annotation.py`), but a conscious decision was made not to provision a key for this submission - Ollama (below) is genuinely working and already satisfies the RFP's "AI must be a core component" requirement, so a second AI provider was judged not worth the additional setup for this timeline. Swapping in a `GOOGLE_API_KEY` env var activates it with no code change, if desired later. |
| Ollama (local LLM) | Free/OSS | **Yes** | Rs 0 | Genuinely working as of this session: pulled `llama3.2:1b` (the RFP's named Llama 4 Scout 8B was not pulled - smaller model chosen for practicality on this machine) and verified `try_ollama()` returns a real generated narrative end-to-end. Also fixed a real bug found in the process: the request timeout was hardcoded to 8s, too short for local-LLM cold-start inference, causing every real call to fail silently into the deterministic fallback - now a configurable 60s default. Output quality from this small model is rougher than Gemini 2.5 Flash would produce (occasional internal contradictions), but the integration itself is real and functional, not just code-path-tested. |
| Power BI Desktop | Free | Yes | Rs 0 | 2-page interactive report (`TelemetrixAI_Dashboard.pbip`) built against `anomaly_results.csv`: latency/throughput trend charts, anomaly-count chart, error-rate matrix, root-cause detail table, AI narrative panel, scenario/component slicers. |
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
| Layer 4 processing engine | Databricks Free Edition | Local PySpark (the proposal's own named fallback) | No Databricks account was provisioned; the local PySpark fallback the proposal itself specified was implemented for real instead - see `spark_processing.py` and Section 7. |
| Layer 2 cloud metric sink | Azure Monitor Free Tier (alongside Prometheus) | Prometheus (local) + Jaeger only | Not provisioned - local Prometheus + Jaeger fully covered telemetry needs for this single-developer demo without adding a cloud account dependency. |
| Data validation tooling | Great Expectations | Plain pytest assertions (`tests/test_layers.py`) | Same validation checks (schema completeness, nulls, ranges) implemented directly in the existing pytest suite rather than a separate framework. |
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
| Gemini live generation in the submitted run | No `GOOGLE_API_KEY` provisioned - this is a credential only the account owner can supply, not something fixable in code | N | Provision a Gemini API key via `.env` (code path already implemented and tested) |
| Recovering-scenario data collection, and re-validating Degraded-cart | Attempted for real in this session using the live OTel Demo stack (it was found running - see below) - `scenario_control.py degrade-cart` correctly toggled `cartFailure` via flagd, but the capture returned all-zero signals because the stack's containers had only just restarted (2 min uptime) and the Locust load-generator was returning `503`s to the backend services, so there was no real traffic to measure. The attempt was cleaned up (flags restored to off, the zero-signal capture discarded) rather than shipped as real data. | N | Before the next attempt: confirm the stack has been up and serving traffic for several minutes (`curl http://localhost:9090/api/v1/query?query=up`, check Locust's own UI for a non-zero RPS), *then* run `scenario_control.py degrade-cart` -> `metrics_collector.py --scenario degraded --out-prefix data/metrics_degraded_cart`, and separately `scenario_control.py restore` -> wait ~10 min -> `metrics_collector.py --scenario recovering` |
| Multi-week real historical data | Real capture window is a single ~30-minute session (2026-09-16); genuinely collecting weeks of data was out of scope for this timeline | N | The dashboard's multi-week trend view (2026-07-20 -> 2026-09-16) is currently populated with **synthetic backfill data** (see `POWERBI_SETUP.md` "Data provenance"), generated from the real session's own operating-range statistics and scored by the same Isolation Forest pipeline, purely to demonstrate the trend-view capability the RFP describes. Replace it with genuine data by running `metrics_collector.py` daily/weekly over time and re-running `anomaly_detection.py` - no dashboard changes needed. |

---

## Section 11. Risks & Blockers - Final Status

| Risk / Blocker | Final Status | Mitigation taken | Final impact |
|---|---|---|---|
| Coverage reported without tool evidence (Mid-Term feedback) | Mitigated | Rewrote test suite with real mocked/fixture-based tests across all 5 core pipeline modules, including every CLI entry point (73 tests); measured **100%** via `pytest --cov`, reproduced independently on both Windows and the real WSL2 pipeline environment, HTML report committed at `htmlcov/` | None - fully resolved, and reproducible: re-running the exact command in Section 6 gives the same number |
| Document format/naming inconsistency (Mid-Term feedback) | Mitigated | Adopted the official Final-Term template for this submission; standardized repo doc naming (`README.md`, `PROJECT_PHASE1_REPORT.md`) | None |
| Incomplete tool reconciliation table (Mid-Term feedback) | Mitigated | Section 7 above lists every approved tool including PyCaret, Databricks/PySpark, Azure Monitor, Great Expectations (all dropped) and partial-use items (Gemini, Ollama, Power BI), each with an explicit reason | None |
| CI missing despite real git history existing (found, then resolved, during Final-Term self-review) | Mitigated | A separate Windows-side working copy (kept for Power BI Desktop access) was mistakenly found to have no git history and briefly, incorrectly, treated as evidence that D-10 had regressed - the real repository (with its full incremental history since 2026-07-15, already pushed to GitHub) was located inside WSL2 and confirmed intact. Added `.github/workflows/ci.yml` (100% coverage gate on every push) to that real repository. | None - D-10's incremental history was never actually lost, see corrected note in Section 3 |
| Layers 5-6 (ML anomaly detection, AI annotation) had zero automated tests (found during Final-Term self-review) | Mitigated | Added `tests/test_anomaly_detection.py` and `tests/test_ai_annotation.py` - model-accuracy tests against seeded anomalies, scenario-classification tests, and Gemini/Ollama provider-fallback tests with both success and failure paths mocked | None |
| Live OTel Demo stack found unhealthy when a real Degraded-cart/Recovering capture was attempted (new, Final-Term prep) | Open | Diagnosed as a warm-up/traffic issue (containers had just restarted, Locust load-generator returning 503s) rather than a config regression; cleaned up (flags restored, zero-signal capture discarded) rather than shipping unusable data | Real capture for cart-Degraded and Recovering scenarios still needs to be re-run once the stack is confirmed serving live traffic - see Section 10 |
| Host machine ran out of disk space mid-Phase-2 (new, Week 2 of Phase 2), crashing Docker/WSL2 | Realised, then mitigated | Diagnosed root cause (0 bytes free on C:), user freed space, WSL2 VM restarted cleanly, all containers recovered via `restart: unless-stopped` with zero data loss (git history + collected data all intact) | ~30 minutes lost to diagnosis/recovery; no data or work lost |
| `cartFailure`/`paymentFailure` flag interaction blocked cart-specific degraded data | Accepted | Documented in Sections 8 and 10; checkout degradation fully validated instead | product-catalog and cart validated only against Normal-scenario false-positive rate, not a seeded failure |
