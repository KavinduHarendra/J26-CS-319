import io
import json
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Secure UAV Communication — Staging",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Secure UAV Communication")
st.caption("Staging prototype · JSON observations → one-minute analysis → rule-based recommendation")

st.info(
    "This prototype analyzes uploaded Module 2 JSON observations. It does not scan live RF signals "
    "or physically switch a radio/communication link. The communication state shown here is a "
    "software recommendation for testing."
)


# -----------------------------
# Parsing and validation helpers
# -----------------------------
def normalize_payload(payload: Any) -> list[dict]:
    """Accept a single JSON object or a list of JSON objects."""
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        if not payload:
            raise ValueError("JSON list is empty.")
        return payload
    raise ValueError("JSON must contain one JSON object or a list of JSON objects.")


def parse_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        # Normalize timezone-aware timestamps to naive UTC so timestamps can be grouped consistently.
        if parsed.tzinfo is not None:
            from datetime import timezone
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError, OverflowError):
        return None


def canonical_classification(value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "NORMAL": "NORMAL",
        "JAMMING": "JAMMING",
        "JAMMING_DETECTED": "JAMMING",
        "UNKNOWN_ANOMALY": "UNKNOWN_ANOMALY",
        "UNKNOWN": "UNKNOWN_ANOMALY",
        "ABNORMAL": "UNKNOWN_ANOMALY",
        "ANOMALY": "UNKNOWN_ANOMALY",
    }
    return aliases.get(raw, raw or "UNCLASSIFIED")


def canonical_severity(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip().upper()
    return raw if raw in {"HIGH", "MEDIUM", "LOW"} else "UNRECOGNIZED"


def parse_json_bytes(raw_bytes: bytes, source_name: str) -> list[dict]:
    try:
        payload = json.loads(raw_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{source_name}: unable to read JSON ({exc}).") from exc
    records = normalize_payload(payload)
    for record in records:
        record["_source_file"] = source_name
    return records


def read_uploaded_files(uploaded_files) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    for uploaded in uploaded_files:
        name = uploaded.name
        raw = uploaded.getvalue()
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    json_names = [
                        member for member in archive.namelist()
                        if member.lower().endswith(".json") and not member.endswith("/")
                    ]
                    if not json_names:
                        errors.append(f"{name}: ZIP contains no JSON files.")
                    for member in json_names:
                        try:
                            records.extend(parse_json_bytes(archive.read(member), f"{name} :: {member}"))
                        except (ValueError, KeyError, RuntimeError) as exc:
                            errors.append(str(exc))
            except zipfile.BadZipFile:
                errors.append(f"{name}: this ZIP file is invalid or damaged.")
        else:
            try:
                records.extend(parse_json_bytes(raw, name))
            except ValueError as exc:
                errors.append(str(exc))
    return records, errors


def validate_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    valid: list[dict] = []
    rejected: list[dict] = []
    for original in records:
        record = dict(original)
        classification = canonical_classification(record.get("classification"))
        severity = canonical_severity(record.get("severity"))
        timestamp = parse_timestamp(record.get("timestamp"))
        issues = []
        if classification == "UNCLASSIFIED":
            issues.append("missing classification")
        elif classification not in {"NORMAL", "JAMMING", "UNKNOWN_ANOMALY"}:
            issues.append(f"unsupported classification: {record.get('classification')!r}")
        if "severity" not in record:
            issues.append("missing severity field")
        elif severity == "UNRECOGNIZED":
            issues.append(f"unsupported severity: {record.get('severity')!r}")
        if timestamp is None:
            issues.append("missing or invalid timestamp")

        record["_classification"] = classification
        record["_severity"] = severity
        record["_parsed_timestamp"] = timestamp
        record["_validation_issues"] = issues
        if issues:
            rejected.append(record)
        else:
            valid.append(record)
    return valid, rejected


# -----------------------------
# One-minute decision engine
# -----------------------------
def decide_window(counts: Counter, high_unknown_count: int) -> tuple[str, str, str]:
    """Return decision, explanation, level. Rules are provisional project rules."""
    jam_high = counts[("JAMMING", "HIGH")]
    jam_medium = counts[("JAMMING", "MEDIUM")]
    jam_low = counts[("JAMMING", "LOW")]

    if jam_high:
        return (
            "SECURE COMMUNICATION MUST",
            f"{jam_high} HIGH-severity jamming observation(s) detected in this minute.",
            "must",
        )

    if high_unknown_count and jam_medium:
        return (
            "SECURE COMMUNICATION MUST",
            "HIGH unknown anomaly and MEDIUM jamming occur in the same minute.",
            "must",
        )
    if high_unknown_count and jam_low:
        return (
            "SECURE COMMUNICATION REQUIRED",
            "HIGH unknown anomaly and LOW jamming occur in the same minute.",
            "required",
        )

    if jam_medium:
        return (
            "SECURE COMMUNICATION REQUIRED",
            f"{jam_medium} MEDIUM-severity jamming observation(s) detected in this minute.",
            "required",
        )
    if jam_low:
        return (
            "SECURE COMMUNICATION RECOMMENDED",
            f"{jam_low} LOW-severity jamming observation(s) detected in this minute.",
            "recommended",
        )
    if high_unknown_count:
        return (
            "FURTHER CHECKING FIRST",
            "HIGH unknown anomaly detected without a jamming observation that resolves the decision.",
            "check",
        )

    unknown_count = sum(counts[("UNKNOWN_ANOMALY", sev)] for sev in ("HIGH", "MEDIUM", "LOW", None))
    if unknown_count:
        return (
            "FURTHER CHECKING FIRST",
            f"{unknown_count} unknown-anomaly observation(s) need additional evidence; do not assume they are jamming.",
            "check",
        )

    normal_count = counts[("NORMAL", None)] + sum(
        counts[("NORMAL", sev)] for sev in ("HIGH", "MEDIUM", "LOW")
    )
    if normal_count:
        return (
            "CONTINUE NORMAL COMMUNICATION",
            "Only NORMAL observations were found in this minute; continue monitoring.",
            "normal",
        )

    return ("FURTHER CHECKING FIRST", "No recognized threat/normal observations were available.", "check")


def build_minute_summary(records: list[dict], normal_minutes_required: int) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    timed = [r for r in records if r.get("_parsed_timestamp") is not None]
    if not timed:
        return pd.DataFrame()

    for record in timed:
        timestamp = record["_parsed_timestamp"]
        record["_minute"] = timestamp.replace(second=0, microsecond=0)

    grouped: dict[datetime, list[dict]] = {}
    for record in timed:
        grouped.setdefault(record["_minute"], []).append(record)

    first_minute = min(grouped)
    last_minute = max(grouped)
    rows = []
    active_state = "NORMAL_MONITORING"
    consecutive_normal = 0
    minute = first_minute

    while minute <= last_minute:
        window_records = grouped.get(minute, [])
        if not window_records:
            consecutive_normal = 0
            rows.append({
                "Minute window": f"{minute:%Y-%m-%d %H:%M}",
                "Records": 0,
                "NORMAL": 0,
                "JAMMING HIGH": 0,
                "JAMMING MEDIUM": 0,
                "JAMMING LOW": 0,
                "UNKNOWN HIGH": 0,
                "UNKNOWN MEDIUM": 0,
                "UNKNOWN LOW": 0,
                "Decision": "NO DATA — HOLD STATE",
                "Reason": "No observations in this minute. Missing data is not treated as NORMAL.",
                "Recommended state": active_state,
                "Normal streak": f"0 / {normal_minutes_required}",
                "_decision_level": "gap",
            })
            minute += timedelta(minutes=1)
            continue

        counts = Counter()
        for record in window_records:
            counts[(record["_classification"], record["_severity"])] += 1

        unknown_high = counts[("UNKNOWN_ANOMALY", "HIGH")]
        decision, reason, level = decide_window(counts, unknown_high)

        if level in {"must", "required", "recommended"}:
            active_state = "SECURE_RECOMMENDED"
            consecutive_normal = 0
        elif level == "normal":
            consecutive_normal += 1
            if active_state == "SECURE_RECOMMENDED":
                if consecutive_normal >= normal_minutes_required:
                    active_state = "NORMAL_MONITORING"
                    reason += (
                        f" {consecutive_normal} consecutive observed NORMAL minute(s) reached "
                        "the configured release threshold; normal communication may be restored."
                    )
                else:
                    decision = "KEEP SECURE — RECHECK NEXT MINUTE"
                    reason += (
                        f" Secure recommendation is retained until {normal_minutes_required} "
                        "consecutive observed NORMAL minute(s) are reached."
                    )
            else:
                active_state = "NORMAL_MONITORING"
        else:
            consecutive_normal = 0
            if active_state == "SECURE_RECOMMENDED":
                decision = "KEEP SECURE — FURTHER CHECKING"
                reason += " Existing secure recommendation is retained while this anomaly is investigated."

        rows.append({
            "Minute window": f"{minute:%Y-%m-%d %H:%M}",
            "Records": len(window_records),
            "NORMAL": counts[("NORMAL", None)] + sum(
                counts[("NORMAL", sev)] for sev in ("HIGH", "MEDIUM", "LOW")
            ),
            "JAMMING HIGH": counts[("JAMMING", "HIGH")],
            "JAMMING MEDIUM": counts[("JAMMING", "MEDIUM")],
            "JAMMING LOW": counts[("JAMMING", "LOW")],
            "UNKNOWN HIGH": counts[("UNKNOWN_ANOMALY", "HIGH")],
            "UNKNOWN MEDIUM": counts[("UNKNOWN_ANOMALY", "MEDIUM")],
            "UNKNOWN LOW": counts[("UNKNOWN_ANOMALY", "LOW")],
            "Decision": decision,
            "Reason": reason,
            "Recommended state": active_state,
            "Normal streak": f"{consecutive_normal} / {normal_minutes_required}",
            "_decision_level": level,
        })
        minute += timedelta(minutes=1)

    return pd.DataFrame(rows)


with st.sidebar:
    st.header("Decision settings")
    normal_minutes_required = st.number_input(
        "Consecutive NORMAL minutes before release",
        min_value=1,
        max_value=30,
        value=3,
        step=1,
        help="A secure recommendation is retained until this many consecutive observed NORMAL minute windows are present.",
    )
    st.caption(
        "The rules are provisional project rules. Confirm them against the dataset and project requirements before operational use."
    )

uploaded_files = st.file_uploader(
    "Upload JSON files or a ZIP containing JSON files",
    type=["json", "zip"],
    accept_multiple_files=True,
    help="You can upload individual JSON files, multiple JSON files, or a ZIP archive containing JSON records.",
)

if not uploaded_files:
    st.subheader("How to use this staging prototype")
    st.markdown(
        "1. Upload one or more `.json` files, or a `.zip` containing JSON files.\n"
        "2. Click **Analyze uploaded observations**.\n"
        "3. Review minute-by-minute threat counts, decisions, and the recommended state."
    )
    st.warning("No data has been analyzed yet.")
    st.stop()

if st.button("🔎 Analyze uploaded observations", type="primary", use_container_width=True):
    raw_records, parse_errors = read_uploaded_files(uploaded_files)
    valid_records, rejected_records = validate_records(raw_records)

    st.session_state["staging_records"] = valid_records
    st.session_state["staging_rejected"] = rejected_records
    st.session_state["staging_parse_errors"] = parse_errors
    st.session_state["staging_input_names"] = [f.name for f in uploaded_files]
    st.session_state["staging_settings_normal_minutes"] = int(normal_minutes_required)

records = st.session_state.get("staging_records")
if records is None:
    st.info("Files selected. Click **Analyze uploaded observations** to run the staging analysis.")
    st.stop()

rejected_records = st.session_state.get("staging_rejected", [])
parse_errors = st.session_state.get("staging_parse_errors", [])
if st.session_state.get("staging_settings_normal_minutes") != int(normal_minutes_required):
    st.session_state["staging_settings_normal_minutes"] = int(normal_minutes_required)

st.subheader("Input and validation summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Records parsed", len(records) + len(rejected_records))
c2.metric("Valid records", len(records))
c3.metric("Rejected records", len(rejected_records))
c4.metric("Input files", len(st.session_state.get("staging_input_names", [])))

if parse_errors:
    with st.expander(f"File parsing issues ({len(parse_errors)})"):
        for issue in parse_errors:
            st.write(f"- {issue}")

if rejected_records:
    with st.expander(f"Rejected records ({len(rejected_records)})"):
        st.warning("These records were excluded from minute aggregation because required fields were missing or invalid.")
        rejected_view = []
        for r in rejected_records:
            rejected_view.append({
                "Source": r.get("_source_file", "--"),
                "Observation ID": r.get("observation_id", "--"),
                "Timestamp": r.get("timestamp", "--"),
                "Classification": r.get("classification", "--"),
                "Issues": "; ".join(r.get("_validation_issues", [])),
            })
        st.dataframe(pd.DataFrame(rejected_view), use_container_width=True, hide_index=True)

if not records:
    st.error("No valid records available for analysis. Check the JSON schema and timestamps.")
    st.stop()

class_counts = Counter(r["_classification"] for r in records)
severity_counts = Counter(r["_severity"] for r in records)

st.subheader("Overall threat summary")
m1, m2, m3, m4 = st.columns(4)
m1.metric("NORMAL", class_counts["NORMAL"])
m2.metric("JAMMING", class_counts["JAMMING"])
m3.metric("UNKNOWN_ANOMALY", class_counts["UNKNOWN_ANOMALY"])
m4.metric("HIGH severity", severity_counts["HIGH"])

st.caption(
    f"Severity totals among valid records: HIGH {severity_counts['HIGH']} · "
    f"MEDIUM {severity_counts['MEDIUM']} · LOW {severity_counts['LOW']} · "
    f"missing/other {severity_counts[None] + severity_counts['UNRECOGNIZED']}"
)

summary = build_minute_summary(records, int(normal_minutes_required))
if summary.empty:
    st.error("Could not create minute windows because no valid timestamps were found.")
    st.stop()

st.subheader("Minute-by-minute decision timeline")
visible_columns = [
    "Minute window", "Records", "NORMAL", "JAMMING HIGH", "JAMMING MEDIUM",
    "JAMMING LOW", "UNKNOWN HIGH", "UNKNOWN MEDIUM", "UNKNOWN LOW",
    "Decision", "Recommended state", "Normal streak",
]
st.dataframe(summary[visible_columns], use_container_width=True, hide_index=True)

st.subheader("Decision explanations")
for _, row in summary.iterrows():
    title = f"{row['Minute window']} · {row['Decision']}"
    with st.expander(title):
        st.write(row["Reason"])
        st.write(f"**Recommended state:** `{row['Recommended state']}`")
        st.write(f"**Observations in window:** {row['Records']}")

last_row = summary.iloc[-1]
st.subheader("Latest analyzed state")
latest1, latest2 = st.columns(2)
latest1.metric("Latest minute decision", str(last_row["Decision"]))
latest2.metric("Recommended communication state", str(last_row["Recommended state"]))
st.write(str(last_row["Reason"]))

st.subheader("Observation details")
detail_rows = []
for record in records:
    detail_rows.append({
        "Observation ID": record.get("observation_id", record.get("id", "--")),
        "Timestamp": record.get("timestamp", "--"),
        "Classification": record["_classification"],
        "Severity": record["_severity"] or "--",
        "Triggered rule": record.get("triggered_rule", "--"),
        "Source file": record.get("_source_file", "--"),
    })
st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

with st.expander("View full valid JSON records"):
    st.json([
        {k: v for k, v in record.items() if not k.startswith("_")}
        for record in records
    ])

csv_bytes = summary.drop(columns=["_decision_level"], errors="ignore").to_csv(index=False).encode("utf-8")
st.download_button(
    "Download minute-by-minute analysis (CSV)",
    data=csv_bytes,
    file_name="secure_uav_minute_analysis.csv",
    mime="text/csv",
)

st.caption(
    "Prototype limitation: this app recommends a communication state from uploaded labels and timestamps. "
    "It does not independently detect jamming, scan live RF, establish encryption, or switch a physical link."
)
