# Layer 7: Power BI Dashboard - Setup Steps

Power BI Desktop is a Windows GUI application, so this final step needs to be done by hand (takes ~5 minutes). The data is already prepared and Power-BI-ready.

**Data file:** `data/anomaly_results.csv` (90 rows: 3 components x Normal+Degraded scenarios, all 4 signals + Layer 5's anomaly_score, is_anomaly, flagged_signal columns)

## Steps

1. Open **Power BI Desktop** > **Get Data** > **Text/CSV** > select `data/anomaly_results.csv` > **Load**.
2. Build these 3-4 visuals on a new report page:
   - **Line chart**: X = `timestamp`, Y = `latency_p95_ms`, Legend = `component` — shows latency over time per component.
   - **Bar chart**: X = `component`, Y = count of `is_anomaly` (filtered to `is_anomaly = 1`) — anomaly count per component.
   - **Table**: columns `component`, `scenario`, `flagged_signal`, `anomaly_score`, `error_rate_pct` filtered to `is_anomaly = 1` — the root-cause detail view.
   - **Card**: average `error_rate_pct` or `latency_p95_ms`, sliced by `scenario` — quick Normal vs Degraded comparison.
3. Add a slicer on `scenario` (Normal/Degraded) and one on `component` so the panel can filter live during the walkthrough.
4. **File > Save As** > `TelemetrixAI_Dashboard.pbix` in the repo root.
5. Screenshot each visual for the Final-Term doc's Evidence section (EV-ID for Layer 7 / D-ID for the dashboard deliverable).

## Re-running with fresh data

Re-run the pipeline any time and hit **Refresh** in Power BI to pull new numbers:
```bash
python metrics_collector.py --scenario normal --duration 2
python anomaly_detection.py
```
