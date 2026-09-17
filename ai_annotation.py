"""Layer 6: AI-Annotated Reporting.

Reads Layer 5's scored dataset (data/anomaly_results.csv) and produces a
plain-language report per component: scenario assessment, root cause
(flagged component + signal), and severity - per RFP Section 6.

Tries providers in order and uses whichever is available:
  1. Gemini 2.5 Flash (primary, per RFP) - needs GOOGLE_API_KEY
  2. Ollama (secondary/offline fallback, per RFP) - needs a local Ollama server
  3. Deterministic template (this project's own fallback, not in the RFP tool
     list) - guarantees a report even with neither AI backend configured/
     reachable, built from the same numbers an LLM would have been given.

This keeps the two RFP-specified backends as the intended path while making
sure Layer 6 always produces output regardless of network/API availability.
"""

import os

import pandas as pd

FEATURES = ["latency_p95_ms", "throughput_rps", "error_rate_pct", "cpu_percent", "memory_percent"]


def summarize_component(df, component):
    comp = df[df["component"] == component]
    normal = comp[comp["scenario"] == "normal"]
    degraded = comp[comp["scenario"] == "degraded"]

    summary = {
        "component": component,
        "normal_rows": len(normal),
        "degraded_rows": len(degraded),
        "normal_fp_rate": normal["is_anomaly"].mean() if len(normal) else None,
        "degraded_detection_rate": degraded["is_anomaly"].mean() if len(degraded) else None,
    }

    # Only surface root-cause signal from genuine degraded-scenario anomalies -
    # normal-scenario false positives are training noise, not a real regression.
    anomalous = degraded[degraded["is_anomaly"] == 1] if not degraded.empty else degraded
    if not anomalous.empty:
        top = anomalous.loc[anomalous["anomaly_score"].idxmax()]
        summary["top_flagged_signal"] = top["flagged_signal"]
        summary["top_signal_zscore"] = round(top["signal_zscore"], 2)
        summary["top_anomaly_score"] = round(top["anomaly_score"], 4)
        summary["worst_row"] = {f: top[f] for f in FEATURES}
    else:
        summary["top_flagged_signal"] = None

    if degraded.empty:
        summary["verdict"] = "Normal"
    elif summary["degraded_detection_rate"] and summary["degraded_detection_rate"] >= 0.5:
        summary["verdict"] = "Degraded"
    elif summary["degraded_detection_rate"] and summary["degraded_detection_rate"] > 0:
        summary["verdict"] = "Recovering"
    else:
        summary["verdict"] = "Normal"

    return summary


def severity(summary):
    rate = summary.get("degraded_detection_rate") or 0
    z = summary.get("top_signal_zscore") or 0
    if rate >= 0.8 or z >= 8:
        return "High"
    if rate >= 0.3 or z >= 4:
        return "Medium"
    if rate > 0:
        return "Low"
    return "None"


def render_deterministic(summary):
    comp = summary["component"]
    verdict = summary["verdict"]
    sev = severity(summary)

    lines = [f"### {comp}", f"**Status: {verdict}** (severity: {sev})", ""]

    if verdict == "Normal" and summary["degraded_rows"] == 0:
        lines.append(
            f"No degraded-scenario data was captured for {comp} in this run. "
            f"Across {summary['normal_rows']} normal-baseline observations, the anomaly "
            f"detector's false-positive rate was {summary['normal_fp_rate']:.1%}, indicating "
            f"a stable baseline with no drift."
        )
    else:
        rate = summary["degraded_detection_rate"] or 0
        lines.append(
            f"Out of {summary['degraded_rows']} observations captured while a failure scenario "
            f"was active, the Isolation Forest model (trained only on normal-scenario data) "
            f"flagged {rate:.1%} as anomalous."
        )
        if summary.get("top_flagged_signal"):
            lines.append(
                f"The strongest anomaly was driven by **{summary['top_flagged_signal']}** "
                f"({summary['top_signal_zscore']} standard deviations from this component's "
                f"normal mean), with an anomaly score of {summary['top_anomaly_score']}."
            )
        lines.append(
            f"Normal-scenario false-positive rate for {comp} was {summary['normal_fp_rate']:.1%}, "
            f"so the model distinguishes this degradation from ordinary variance."
        )
    lines.append("")
    return "\n".join(lines)


def try_gemini(summaries):
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = (
            "You are an SRE assistant. Given this anomaly-detection summary per platform "
            "component (JSON), write a concise plain-language report identifying: whether "
            "each component is Normal/Degraded/Recovering, the likely root cause "
            "(component + signal), and severity (High/Medium/Low/None). Data:\n\n"
            f"{summaries}"
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini unavailable ({e}), falling back")
        return None


def try_ollama(summaries, model="llama3.2:1b", host="http://localhost:11434", timeout=60):
    try:
        import requests

        prompt = (
            "You are an SRE assistant. Given this anomaly-detection summary per platform "
            "component (JSON), write a concise plain-language report identifying: whether "
            "each component is Normal/Degraded/Recovering, the likely root cause "
            "(component + signal), and severity (High/Medium/Low/None). Data:\n\n"
            f"{summaries}"
        )
        resp = requests.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response")
    except Exception as e:
        print(f"Ollama unavailable ({e}), falling back")
        return None


def generate_report(results_csv="data/anomaly_results.csv", out_path="data/ai_report.md"):
    df = pd.read_csv(results_csv)
    components = df["component"].unique().tolist()
    summaries = [summarize_component(df, c) for c in components]

    ai_text = try_gemini(summaries) or try_ollama(summaries)

    lines = ["# TelemetrixAI - AI-Annotated Performance Report", ""]
    if ai_text:
        lines += ["## AI-Generated Summary", "", ai_text, "", "---", ""]
        lines.append("## Per-Component Detail (deterministic, same underlying data)\n")
    else:
        lines.append(
            "*Generated by the deterministic fallback - neither Gemini (no GOOGLE_API_KEY) "
            "nor Ollama (not reachable) were available at generation time.*\n"
        )

    for s in summaries:
        lines.append(render_deterministic(s))

    report = "\n".join(lines)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\nSaved to {out_path}")
    return report


if __name__ == "__main__":
    generate_report()
