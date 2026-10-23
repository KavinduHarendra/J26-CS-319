import hashlib
import json
from typing import Any

import streamlit as st

st.set_page_config(
    page_title="Secure UAV Communication",
    page_icon="🛡️",
    layout="wide",
)

def normalize_records(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return payload
    if payload == []:
        raise ValueError("JSON list is empty.")
    raise ValueError("JSON must contain one JSON object or a list of JSON objects.")

def first_present(record: dict, *keys: str, default=None):
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return default

def display_value(value: Any, unit: str = "") -> str:
    if value is None or value == "":
        return "--"
    if isinstance(value, (int, float)) and unit:
        return f"{value:g} {unit}"
    return str(value)

def validate_record(record: dict, index: int) -> list[str]:
    errors = []
    classification = str(record.get("classification", "")).strip().lower()
    severity = record.get("severity")
    if classification not in {"jamming", "normal", "abnormal"}:
        errors.append(
            f"Record {index}: classification must be 'jamming', 'normal', or 'abnormal'. "
            f"Found: {record.get('classification', '(missing)')!r}"
        )
    if "severity" not in record:
        errors.append(f"Record {index}: missing 'severity' field. Use null if unknown.")
    elif severity is not None and str(severity).strip().lower() not in {"high", "medium", "low"}:
        errors.append(f"Record {index}: severity must be high, medium, low, or null.")
    return errors

def get_rf(record: dict) -> dict:
    return {
        "SNR": first_present(record, "snr_db", "snr", "SNR", "signal_to_noise_db"),
        "RSSI": first_present(record, "rssi_dbm", "rssi", "RSSI"),
        "Noise Floor": first_present(record, "noise_floor_dbm", "noise_floor", "noise_floor_db"),
        "RF Trend": first_present(record, "rf_trend", "trend", "rfTrend"),
    }

def threat_status(record: dict) -> tuple[str, str]:
    classification = str(record.get("classification", "")).strip().lower()
    if classification == "jamming":
        return "DETECTED", "Uploaded record is labelled as jamming."
    if classification == "abnormal":
        return "ABNORMAL", "Uploaded record is labelled as abnormal."
    if classification == "normal":
        return "NORMAL", "Uploaded record is labelled as normal."
    return "PENDING", "Classification is not available."

def response_decision(record: dict) -> tuple[str, str, str]:
    classification = str(record.get("classification", "")).strip().lower()
    severity = str(record.get("severity") or "").strip().lower()
    if classification == "jamming" and severity == "high":
        return ("HIGH-PRIORITY RESPONSE RECOMMENDED",
                "The uploaded record indicates high-severity jamming. Validate source data before taking action.", "error")
    if classification == "jamming" and severity == "medium":
        return ("REVIEW LINK CONDITIONS",
                "The uploaded record indicates medium-severity jamming. Review available measurements and evidence.", "warning")
    if classification == "jamming" and severity == "low":
        return ("MONITOR",
                "The uploaded record indicates low-severity jamming. Validate with more observations.", "warning")
    if classification == "normal":
        return ("NO THREAT RESPONSE INDICATED",
                "The uploaded record is labelled normal; this does not guarantee that a real link is safe.", "success")
    if classification == "abnormal":
        return ("INVESTIGATE ANOMALY",
                "The record is abnormal, but the supplied fields do not establish a specific response.", "warning")
    return ("AWAITING CLASSIFICATION", "No response decision can be made.", "info")

st.title("🛡️ Secure UAV Communication Dashboard")
st.caption("Jamming-aware monitoring · JSON analysis prototype")
st.info(
    "Upload your JSON file and click **Scan Uploaded Data**. Results are calculated from the uploaded data. "
    "This button does not scan live RF signals."
)

uploaded_file = st.file_uploader("Upload Threat Intelligence JSON", type=["json"])

if uploaded_file is None:
    st.info("Upload a .json file to begin.")
    st.subheader("Dashboard preview")
    c1, c2 = st.columns(2)
    c1.metric("Current Threat Status", "PENDING")
    c2.metric("Secure Communication", "PENDING")
    st.subheader("RF Measurements")
    cols = st.columns(4)
    for col, label, unit in zip(cols, ["SNR", "RSSI", "Noise Floor", "RF Trend"], ["dB", "dBm", "dBm", ""]):
        col.metric(label, f"-- {unit}".strip())
    st.stop()

file_bytes = uploaded_file.getvalue()
file_hash = hashlib.sha256(file_bytes).hexdigest()

# Reset the previous scan result if a different file is selected.
if st.session_state.get("scanned_file_hash") != file_hash:
    st.session_state.pop("scanned_records", None)
    st.session_state.pop("scanned_file_hash", None)

scan_clicked = st.button("🔎 Scan Uploaded Data", type="primary", use_container_width=True)

if scan_clicked:
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
        records = normalize_records(payload)
        errors = []
        for i, rec in enumerate(records, start=1):
            errors.extend(validate_record(rec, i))
        if errors:
            st.session_state.pop("scanned_records", None)
            st.error("The JSON file was read, but its fields need fixing:")
            for err in errors:
                st.write(f"- {err}")
        else:
            st.session_state["scanned_records"] = records
            st.session_state["scanned_file_hash"] = file_hash
            st.success(f"Scan complete: JSON parsed and validated. {len(records)} record(s) found.")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        st.session_state.pop("scanned_records", None)
        st.error(f"Could not scan this file: {exc}")

records = st.session_state.get("scanned_records")
if not records or st.session_state.get("scanned_file_hash") != file_hash:
    st.warning("File uploaded. Click **Scan Uploaded Data** to show its results below.")
    st.stop()

record = records[-1]
classification = str(record.get("classification", "")).strip().lower()
severity = record.get("severity")
status, status_note = threat_status(record)

st.success(f"JSON scanned successfully · {len(records)} record(s) found")
st.caption("Summary below uses the last record in the JSON file.")

st.subheader("Current status")
c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Current Threat Status")
    if status == "DETECTED":
        st.error(status)
    elif status == "ABNORMAL":
        st.warning(status)
    elif status == "NORMAL":
        st.success(status)
    else:
        st.info(status)
    st.write(status_note)
    st.caption(f"Classification: {classification or '--'} · Severity: {severity if severity is not None else '--'}")
with c2:
    st.markdown("#### Secure Communication")
    handshake = first_present(record, "secure_link_status", "handshake_status")
    if str(handshake).strip().lower() in {"established", "verified", "success"}:
        st.success("ESTABLISHED")
        st.caption("Status supplied by the uploaded record; verify the trusted source.")
    else:
        st.warning("PENDING")
        st.caption("No verified secure-link handshake was supplied. This prototype cannot establish a link.")

st.subheader("RF Measurements")
rf = get_rf(record)
cols = st.columns(4)
units = {"SNR": "dB", "RSSI": "dBm", "Noise Floor": "dBm", "RF Trend": ""}
for col, label in zip(cols, rf):
    col.metric(label, display_value(rf[label], units[label]))

st.subheader("Threat Intelligence Details")
details = [
    ("Observation ID", first_present(record, "observation_id", "id")),
    ("Timestamp", record.get("timestamp")),
    ("Triggered Rule", record.get("triggered_rule")),
    ("Statistical Deviation", record.get("statistical_deviation")),
]
cols = st.columns(4)
for col, (label, value) in zip(cols, details):
    with col:
        st.markdown(f"**{label}**")
        st.write(display_value(value))

with st.expander("Evidence and abnormal features", expanded=True):
    st.markdown("**Evidence**")
    st.write(first_present(record, "evidence", default="--"))
    st.markdown("**Abnormal features**")
    st.write(first_present(record, "abnormal_features", default="--"))

st.subheader("Adaptive Response Decision")
decision, reason, kind = response_decision(record)
if kind == "error":
    st.error(decision)
elif kind == "warning":
    st.warning(decision)
elif kind == "success":
    st.success(decision)
else:
    st.info(decision)
st.write(reason)

if classification == "jamming" and str(severity).strip().lower() == "high":
    st.button(
        "Build the communication",
        disabled=True,
        help="Disabled until compatible secure-link radio hardware and protocol are integrated.",
    )
    st.caption("This button remains disabled: this app does not transmit or establish a secure link.")

with st.expander("View all uploaded JSON records"):
    st.json(records)

st.caption(
    "Prototype limitation: labels and RF measurements are read from uploaded JSON. "
    "This app does not independently detect jamming or scan live RF signals."
)
