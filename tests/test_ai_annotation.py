"""Layer 6: AI Annotation & Report Generation - unit + AI-evaluation tests.

Covers ai_annotation.py, which had zero coverage: scenario classification
logic (summarize_component/severity), the deterministic report renderer,
the Gemini/Ollama provider fallback chain, and end-to-end report generation.
Satisfies RFP 10.2 "AI Evaluation Tests... AI report correctly classifies
scenario" at the unit level, since no live Gemini/Ollama backend is
reachable in this environment (see FINAL_TERM_CONTENT_DRAFT.md Section 10).
"""

import sys

import pandas as pd
import pytest

import ai_annotation as aa


def _df(rows):
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# summarize_component(): scenario classification against ground truth
# ---------------------------------------------------------------------------

def test_summarize_classifies_normal_when_no_degraded_data():
    df = _df([
        {"component": "cart", "scenario": "normal", "is_anomaly": 0, "anomaly_score": 0.0,
         "flagged_signal": None, "signal_zscore": 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for _ in range(10)
    ])
    summary = aa.summarize_component(df, "cart")
    assert summary["verdict"] == "Normal"
    assert summary["degraded_rows"] == 0


def test_summarize_classifies_degraded_on_high_detection_rate():
    normal_rows = [
        {"component": "checkout", "scenario": "normal", "is_anomaly": 0, "anomaly_score": 0.0,
         "flagged_signal": None, "signal_zscore": 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for _ in range(10)
    ]
    degraded_rows = [
        {"component": "checkout", "scenario": "degraded", "is_anomaly": 1, "anomaly_score": 0.5,
         "flagged_signal": "error_rate_pct", "signal_zscore": 999.0, **{f: 1.0 for f in aa.FEATURES}}
        for _ in range(8)
    ]
    df = _df(normal_rows + degraded_rows)
    summary = aa.summarize_component(df, "checkout")
    assert summary["verdict"] == "Degraded"
    assert summary["top_flagged_signal"] == "error_rate_pct"


def test_summarize_falls_back_to_normal_when_degraded_rows_all_missed():
    normal_rows = [
        {"component": "cart", "scenario": "normal", "is_anomaly": 0, "anomaly_score": 0.0,
         "flagged_signal": None, "signal_zscore": 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for _ in range(10)
    ]
    # Degraded rows exist, but the model caught none of them (detection_rate == 0).
    degraded_rows = [
        {"component": "cart", "scenario": "degraded", "is_anomaly": 0, "anomaly_score": 0.0,
         "flagged_signal": None, "signal_zscore": 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for _ in range(5)
    ]
    df = _df(normal_rows + degraded_rows)
    summary = aa.summarize_component(df, "cart")
    assert summary["verdict"] == "Normal"
    assert summary["degraded_rows"] == 5


def test_summarize_classifies_recovering_on_partial_detection_rate():
    normal_rows = [
        {"component": "checkout", "scenario": "normal", "is_anomaly": 0, "anomaly_score": 0.0,
         "flagged_signal": None, "signal_zscore": 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for _ in range(10)
    ]
    # 2 of 10 degraded rows still flagged -> partial detection -> Recovering
    degraded_rows = [
        {"component": "checkout", "scenario": "degraded", "is_anomaly": 1 if i < 2 else 0,
         "anomaly_score": 0.1, "flagged_signal": "latency_p95_ms" if i < 2 else None,
         "signal_zscore": 5.0 if i < 2 else 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for i in range(10)
    ]
    df = _df(normal_rows + degraded_rows)
    summary = aa.summarize_component(df, "checkout")
    assert summary["verdict"] == "Recovering"


# ---------------------------------------------------------------------------
# severity(): thresholds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rate,z,expected", [
    (0.0, 0.0, "None"),
    (0.2, 1.0, "Low"),
    (0.5, 5.0, "Medium"),
    (0.9, 10.0, "High"),
])
def test_severity_thresholds(rate, z, expected):
    summary = {"degraded_detection_rate": rate, "top_signal_zscore": z}
    assert aa.severity(summary) == expected


# ---------------------------------------------------------------------------
# render_deterministic(): report content reflects the classified scenario
# ---------------------------------------------------------------------------

def test_render_deterministic_normal_mentions_stable_baseline():
    summary = {
        "component": "cart", "verdict": "Normal", "degraded_rows": 0,
        "normal_rows": 30, "normal_fp_rate": 0.1, "degraded_detection_rate": None,
        "top_flagged_signal": None,
    }
    text = aa.render_deterministic(summary)
    assert "cart" in text
    assert "Normal" in text
    assert "stable baseline" in text


def test_render_deterministic_degraded_names_root_cause_signal():
    summary = {
        "component": "checkout", "verdict": "Degraded", "degraded_rows": 20,
        "normal_rows": 60, "normal_fp_rate": 0.1, "degraded_detection_rate": 0.81,
        "top_flagged_signal": "error_rate_pct", "top_signal_zscore": 999.0,
        "top_anomaly_score": 0.1072,
    }
    text = aa.render_deterministic(summary)
    assert "checkout" in text
    assert "error_rate_pct" in text
    assert "81.0%" in text


# ---------------------------------------------------------------------------
# Provider fallback chain
# ---------------------------------------------------------------------------

def test_try_gemini_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert aa.try_gemini([{"component": "cart"}]) is None


def test_try_ollama_returns_none_on_connection_failure(monkeypatch):
    import requests

    def raise_conn_error(*a, **k):
        raise requests.exceptions.ConnectionError("no server")

    monkeypatch.setattr(requests, "post", raise_conn_error)
    assert aa.try_ollama([{"component": "cart"}]) is None


def test_try_ollama_returns_response_text_on_success(monkeypatch):
    import requests

    mock_response = MagicMockLike()
    mock_response.json_data = {"response": "cart is Normal, checkout is Degraded"}

    def fake_post(*a, **k):
        return mock_response

    monkeypatch.setattr(requests, "post", fake_post)
    result = aa.try_ollama([{"component": "cart"}])
    assert result == "cart is Normal, checkout is Degraded"


def test_try_ollama_returns_none_on_http_error(monkeypatch):
    import requests

    class RaisingResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("model not found")

    monkeypatch.setattr(requests, "post", lambda *a, **k: RaisingResponse())
    assert aa.try_ollama([{"component": "cart"}]) is None


def test_try_gemini_returns_none_on_provider_exception(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key-for-test")

    class RaisingGenAI:
        def configure(self, **k):
            raise RuntimeError("bad key")

    monkeypatch.setitem(sys.modules, "google.generativeai", RaisingGenAI())
    assert aa.try_gemini([{"component": "cart"}]) is None


def test_try_gemini_returns_text_on_success(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key-for-test")

    class FakeResponse:
        text = "checkout is Degraded due to error_rate_pct"

    class FakeModel:
        def __init__(self, name):
            pass

        def generate_content(self, prompt):
            return FakeResponse()

    class FakeGenAI:
        GenerativeModel = FakeModel

        def configure(self, **k):
            pass

    monkeypatch.setitem(sys.modules, "google.generativeai", FakeGenAI())
    result = aa.try_gemini([{"component": "checkout"}])
    assert result == "checkout is Degraded due to error_rate_pct"


class MagicMockLike:
    """Minimal stand-in for requests.Response, avoiding a MagicMock import here."""
    json_data = {}

    def raise_for_status(self):
        return None

    def json(self):
        return self.json_data


# ---------------------------------------------------------------------------
# generate_report(): end-to-end with providers forced to the deterministic
# fallback path (mirrors this project's actual runtime environment).
# ---------------------------------------------------------------------------

def test_generate_report_end_to_end_uses_deterministic_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(aa, "try_gemini", lambda summaries: None)
    monkeypatch.setattr(aa, "try_ollama", lambda summaries: None)

    df = _df([
        {"component": c, "scenario": "normal", "is_anomaly": 0, "anomaly_score": 0.0,
         "flagged_signal": None, "signal_zscore": 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for c in ("checkout", "product-catalog", "cart")
        for _ in range(10)
    ])
    csv_path = tmp_path / "anomaly_results.csv"
    df.to_csv(csv_path, index=False)
    out_path = tmp_path / "ai_report.md"

    report = aa.generate_report(results_csv=str(csv_path), out_path=str(out_path))

    assert out_path.exists()
    for component in ("checkout", "product-catalog", "cart"):
        assert component in report
    assert "deterministic fallback" in report


def test_cli_main_generates_default_report(tmp_path, monkeypatch):
    """Exercises ai_annotation.py's __main__ block in-process (runpy).

    runpy re-executes the file fresh, so only truly global singletons
    (env vars, the `requests` module itself) reach code running inside
    that execution - not patches on the already-imported ai_annotation
    module's functions.
    """
    import runpy

    import requests as requests_module

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def raise_conn_error(*a, **k):
        raise requests_module.exceptions.ConnectionError("no server")

    monkeypatch.setattr(requests_module, "post", raise_conn_error)

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    df = _df([
        {"component": "cart", "scenario": "normal", "is_anomaly": 0, "anomaly_score": 0.0,
         "flagged_signal": None, "signal_zscore": 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for _ in range(10)
    ])
    df.to_csv(tmp_path / "data" / "anomaly_results.csv", index=False)

    runpy.run_path(aa.__file__, run_name="__main__")

    assert (tmp_path / "data" / "ai_report.md").exists()


def test_generate_report_includes_ai_summary_when_provider_available(tmp_path, monkeypatch):
    monkeypatch.setattr(aa, "try_gemini", lambda summaries: "AI-written summary text")
    monkeypatch.setattr(aa, "try_ollama", lambda summaries: None)

    df = _df([
        {"component": "cart", "scenario": "normal", "is_anomaly": 0, "anomaly_score": 0.0,
         "flagged_signal": None, "signal_zscore": 0.0, **{f: 1.0 for f in aa.FEATURES}}
        for _ in range(10)
    ])
    csv_path = tmp_path / "anomaly_results.csv"
    df.to_csv(csv_path, index=False)
    out_path = tmp_path / "ai_report.md"

    report = aa.generate_report(results_csv=str(csv_path), out_path=str(out_path))

    assert "AI-Generated Summary" in report
    assert "AI-written summary text" in report
    assert "deterministic fallback" not in report
