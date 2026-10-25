"""Module 4 — Scoring Weights Configuration.

IMPORTANT: These weights are initial configurable prototype values
pending experimental calibration through controlled test scenarios.

They represent the research team's initial engineering judgement
for PP1 demonstration purposes only. They should NOT be treated as
validated scientific thresholds until calibrated through:
  - Controlled RF jamming experiments
  - Communication security test scenarios
  - Comparative baseline evaluation

To change weights: edit this file only.
Do NOT bury scoring constants inside service logic.
"""

# ─── THREAT CLASSIFICATION BASE POINTS (from Module 2) ───────────────────────
# Contribution of Module 2 classification to risk score.
# "Unknown Anomaly" is intentionally LOWER than Jamming — it must not be
# treated as a confirmed attack.
CLASSIFICATION_POINTS: dict[str, float] = {
    "Normal": 0.0,
    "Unknown Anomaly": 20.0,
    "Jamming": 35.0,
}

# ─── THREAT SEVERITY ADDITIONAL POINTS (from Module 2) ───────────────────────
# Added on top of classification points when severity is known.
SEVERITY_POINTS: dict[str | None, float] = {
    None: 0.0,
    "Low": 10.0,
    "Medium": 20.0,
    "High": 30.0,
}

# ─── COMMUNICATION LINK STATE POINTS (from Module 3) ─────────────────────────
LINK_STATE_POINTS: dict[str, float] = {
    "TRUSTED": 0.0,
    "DEGRADED": 15.0,
    "SUSPICIOUS": 25.0,
    "UNTRUSTED": 35.0,
}

# ─── MESSAGE FRESHNESS POINTS (from Module 3) ────────────────────────────────
FRESHNESS_POINTS: dict[str, float] = {
    "FRESH": 0.0,
    "STALE": 10.0,
    "REPLAY": 25.0,
}

# ─── AUTHENTICATION STATE POINTS (from Module 3) ─────────────────────────────
AUTH_POINTS: dict[str, float] = {
    "VALID": 0.0,
    "SUSPICIOUS": 10.0,
    "INVALID": 25.0,
}

# ─── INTEGRITY STATE POINTS (from Module 3) ──────────────────────────────────
INTEGRITY_POINTS: dict[str, float] = {
    "VALID": 0.0,
    "SUSPICIOUS": 10.0,
    "INVALID": 25.0,
}

# ─── RISK LEVEL THRESHOLDS ───────────────────────────────────────────────────
RISK_LEVELS: list[tuple[float, float, str]] = [
    (0.0, 24.9, "LOW"),
    (25.0, 49.9, "MEDIUM"),
    (50.0, 74.9, "HIGH"),
    (75.0, 100.0, "CRITICAL"),
]

# ─── RISK SCORE CAP ──────────────────────────────────────────────────────────
RISK_SCORE_MAX: float = 100.0
