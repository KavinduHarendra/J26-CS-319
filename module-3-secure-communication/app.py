import json
import time
from datetime import datetime, timezone

import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Secure UAV Communication", page_icon="🛡️", layout="wide")
st.title("🛡️ Secure UAV Communication")
st.caption("Jamming-aware response prototype · Upload → Scan → Generate proposed configuration")

def normalize_json(payload):
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list) and payload and all(isinstance(x, dict) for x in payload):
        return payload[-1]
    raise ValueError("Upload a JSON object or a non-empty list of JSON objects.")

def pick(data, *names):
    for name in names:
        value = data.get(name)
        if value is not None and value != "":
            return value
    return None

def valid_record(data):
    errors = []
    classification = str(data.get("classification", "")).strip().lower()
    severity = data.get("severity")
    if classification not in {"jamming", "normal", "abnormal"}:
        errors.append("classification must be jamming, normal, or abnormal.")
    if "severity" not in data:
        errors.append("severity field is required (use null if unavailable).")
    elif severity is not None and str(severity).lower() not in {"high", "medium", "low"}:
        errors.append("severity must be high, medium, low, or null.")
    return errors

def make_response(data, rf):
    classification = str(data.get("classification", "")).lower()
    severity = str(data.get("severity") or "null").lower()
    if classification != "jamming" or severity != "high":
        return {
            "response_required": False,
            "response_mode": "no_new_configuration",
            "reason": f"Current policy generates a new configuration only for jamming + high severity (received {classification} + {severity}).",
            "observation_id": data.get("observation_id"),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    snr, rssi, noise, trend = rf["snr_db"], rf["rssi_dbm"], rf["noise_floor_dbm"], rf["trend"]
    degraded = (str(trend or "").lower() == "degrading") or (snr is not None and snr < 8) or (
        rssi is not None and noise is not None and rssi < -85 and noise > -95
    )
    return {
        "response_required": True,
        "response_mode": "high_risk_adaptive_link",
        "observation_id": data.get("observation_id"),
        "source_timestamp": data.get("timestamp"),
        "security": {"encryption": "maintain_enabled", "authentication": "maintain_enabled"},
        "link_adaptation": {
            "error_correction": "increased_if_supported" if degraded else "standard_or_adaptive",
            "data_rate": "reduced_if_supported" if degraded else "maintain_or_adapt",
            "backup_link": "use_if_available_and_validated",
        },
        "rf_context": rf,
        "reason": "Threat Intelligence reports high-severity jamming; RF fields tailor the proposed response where available.",
        "execution_status": "proposed_only_not_applied_to_radio",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

def val(value, unit=""):
    if value is None or value == "":
        return "--"
    if isinstance(value, (int, float)) and unit:
        return f"{value:g} {unit}"
    return str(value)

st.subheader("1. Upload Threat Intelligence JSON")
uploaded = st.file_uploader("Choose a JSON file", type=["json"])

if uploaded is None:
    for key in ["uploaded_bytes", "scan_record", "response", "rf", "build_deadline", "build_done", "scan_error"]:
        st.session_state.pop(key, None)
    st.info("Upload a JSON file to begin. Threat details and RF measurements remain -- until you scan it.")
    left, right = st.columns(2)
    with left:
        st.markdown("### Current Threat Status")
        st.warning("PENDING")
        st.caption("Waiting for a JSON record.")
    with right:
        st.markdown("### Secure Communication")
        st.warning("PENDING")
        st.caption("No verified secure-link handshake yet.")
    st.markdown("### RF Measurements")
    cols = st.columns(4)
    for c, label, unit in zip(cols, ["SNR", "RSSI", "Noise Floor", "RF Trend"], ["dB", "dBm", "dBm", ""]):
        c.metric(label, "--" if not unit else f"-- {unit}")
    st.markdown("### Adaptive Response Decision")
    st.info("Awaiting JSON upload.")
    st.stop()

file_bytes = uploaded.getvalue()
if st.session_state.get("uploaded_bytes") != file_bytes:
    st.session_state["uploaded_bytes"] = file_bytes
    for key in ["scan_record", "response", "rf", "build_deadline", "build_done", "scan_error"]:
        st.session_state.pop(key, None)

st.success(f"File selected: {uploaded.name}")
if st.button("🔎 Scan Uploaded Data", type="primary", use_container_width=True):
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
        record = normalize_json(payload)
        errors = valid_record(record)
        if errors:
            st.session_state["scan_error"] = errors
            st.session_state.pop("scan_record", None)
        else:
            st.session_state["scan_record"] = record
            st.session_state.pop("scan_error", None)
            rf = {
                "snr_db": pick(record, "snr_db", "snr", "SNR", "signal_to_noise_db"),
                "rssi_dbm": pick(record, "rssi_dbm", "rssi", "RSSI"),
                "noise_floor_dbm": pick(record, "noise_floor_dbm", "noise_floor", "noise_floor_db", "noiseFloor"),
                "trend": pick(record, "rf_trend", "trend", "rfTrend"),
            }
            st.session_state["rf"] = rf
            response = make_response(record, rf)
            st.session_state["response"] = response
            st.session_state.pop("build_done", None)
            if response["response_required"]:
                st.session_state["build_deadline"] = time.time() + 15
            else:
                st.session_state.pop("build_deadline", None)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        st.session_state["scan_error"] = [str(exc)]
        st.session_state.pop("scan_record", None)

if st.session_state.get("scan_error"):
    st.error("JSON validation failed.")
    for error in st.session_state["scan_error"]:
        st.write(f"- {error}")
    st.stop()

record = st.session_state.get("scan_record")
if record is None:
    st.info("File uploaded. Click Scan Uploaded Data to validate and show the fields.")
    st.stop()

rf = st.session_state["rf"]
response = st.session_state["response"]
classification = str(record.get("classification", "")).lower()
severity = str(record.get("severity") or "null").lower()

st.success("JSON scanned and validated.")
st.caption(f"Observation ID: {record.get('observation_id', '--')} · Timestamp: {record.get('timestamp', '--')}")

left, right = st.columns(2)
with left:
    st.markdown("### Current Threat Status")
    if classification == "jamming":
        st.error(f"DETECTED · {severity.upper()} SEVERITY JAMMING")
    elif classification == "abnormal":
        st.warning("ABNORMAL")
    else:
        st.success("NORMAL")
    st.caption(f"Triggered rule: {record.get('triggered_rule', '--')}")
with right:
    st.markdown("### Secure Communication")
    handshake = str(record.get("secure_link_status", record.get("handshake_status", "pending"))).lower()
    if handshake in {"established", "verified", "success"}:
        st.success("ESTABLISHED")
    elif handshake in {"failed", "error"}:
        st.error("FAILED")
    else:
        st.warning("PENDING")
    st.caption("ESTABLISHED is not claimed unless a verification status is supplied.")

st.markdown("### RF Measurements")
cols = st.columns(4)
for col, label, value, unit in zip(cols, ["SNR", "RSSI", "Noise Floor", "RF Trend"],
        [rf["snr_db"], rf["rssi_dbm"], rf["noise_floor_dbm"], rf["trend"]], ["dB", "dBm", "dBm", ""]):
    col.metric(label, val(value, unit))

with st.expander("Threat Intelligence details", expanded=True):
    st.json(record)

st.markdown("### Adaptive Response Decision")
if response["response_required"]:
    st.error("HIGH-SEVERITY JAMMING — SECURE-LINK CONFIGURATION REQUIRED")
    st.write(response["reason"])
    if not st.session_state.get("build_done"):
        deadline = st.session_state.get("build_deadline", time.time() + 15)
        remaining = max(0, int(deadline - time.time() + 0.999))
        clicked = st.button("🔴 Build the communication now", type="primary", use_container_width=True)
        st.caption(f"Automatic start in {remaining} seconds if not started manually.")
        if clicked or remaining <= 0:
            st.session_state["build_done"] = True
            st.session_state.pop("build_deadline", None)
            st.rerun()
        st_autorefresh(interval=1000, key="secure_link_countdown_refresh")
    else:
        st.success("Configuration build process started (software simulation).")
        st.json(response)
else:
    st.info(response["reason"])
    st.json(response)

st.download_button("Download response JSON", data=json.dumps(response, indent=2, ensure_ascii=False),
    file_name="secure_communication_response.json", mime="application/json")
st.warning("This app analyzes uploaded JSON only; it does not scan live RF or change real radio settings. The countdown launches a software-only configuration simulation.")
