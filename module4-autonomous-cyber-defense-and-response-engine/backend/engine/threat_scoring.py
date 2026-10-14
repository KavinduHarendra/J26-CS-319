"""Explainable rule-based threat scoring for research prototype."""

from models.schemas import ThreatInput, ThreatAnalysisResult, ScoreFactor
from engine.correlation import correlate_evidence

THREAT_TYPE_BASE = {
    "Normal": 0,
    "Jamming": 35,
    "Spoofing": 30,
    "Unauthorized Transmission": 28,
    "Suspicious Command": 25,
    "Replay Attempt": 22,
    "Unknown Anomaly": 20,
}

SEVERITY_RANGES = [
    (0, 24, "LOW"),
    (25, 49, "MEDIUM"),
    (50, 74, "HIGH"),
    (75, 100, "CRITICAL"),
]


def severity_from_score(score: float) -> str:
    clamped = max(0, min(100, score))
    for low, high, label in SEVERITY_RANGES:
        if low <= clamped <= high:
            return label
    return "CRITICAL"


def affected_communication(threat_type: str, comm_status: str, packet_loss: float) -> str:
    if threat_type == "Normal" and packet_loss < 5:
        return "NORMAL"
    if packet_loss >= 15 or comm_status in ("DEGRADED", "DISRUPTED"):
        return "DEGRADED"
    if threat_type in ("Jamming", "Spoofing", "Unauthorized Transmission"):
        return "COMPROMISED"
    return "AT RISK"


def analyze_threat(data: ThreatInput) -> ThreatAnalysisResult:
    correlation = correlate_evidence(data)
    factors: list[ScoreFactor] = []
    score = float(THREAT_TYPE_BASE.get(data.threat_type, 15))

    if data.threat_type != "Normal":
        factors.append(ScoreFactor(label=f"Threat type: {data.threat_type}", points=THREAT_TYPE_BASE.get(data.threat_type, 15)))

    if data.snr_db < 10:
        pts = 20
        factors.append(ScoreFactor(label="Low SNR (below 10 dB)", points=pts))
        score += pts
    elif data.snr_db < 18:
        pts = 12
        factors.append(ScoreFactor(label="Reduced SNR (below 18 dB)", points=pts))
        score += pts

    if data.noise_level_dbm > -75:
        pts = 15
        factors.append(ScoreFactor(label="High interference / noise", points=pts))
        score += pts
    elif data.noise_level_dbm > -85:
        pts = 8
        factors.append(ScoreFactor(label="Elevated noise level", points=pts))
        score += pts

    if data.packet_loss_pct >= 20:
        pts = 18
        factors.append(ScoreFactor(label="High packet loss (≥20%)", points=pts))
        score += pts
    elif data.packet_loss_pct >= 8:
        pts = 10
        factors.append(ScoreFactor(label="Increased packet loss", points=pts))
        score += pts

    if data.latency_ms >= 150:
        pts = 10
        factors.append(ScoreFactor(label="High communication latency", points=pts))
        score += pts

    if data.authentication_status.upper() in ("FAILED", "INVALID", "COMPROMISED"):
        pts = 20
        factors.append(ScoreFactor(label="Authentication failure", points=pts))
        score += pts

    if data.controller_trust_status.upper() in ("UNTRUSTED", "SUSPICIOUS", "UNKNOWN"):
        pts = 15
        factors.append(ScoreFactor(label="Untrusted controller", points=pts))
        score += pts

    if data.communication_status.upper() in ("DEGRADED", "DISRUPTED", "LOST"):
        pts = 12
        factors.append(ScoreFactor(label="Communication reliability degraded", points=pts))
        score += pts

    if data.previous_threat_score >= 40 and data.threat_type != "Normal":
        pts = 12
        factors.append(ScoreFactor(label="Repeated / escalating anomaly", points=pts))
        score += pts

    if data.threat_confidence >= 0.7:
        pts = 8
        factors.append(ScoreFactor(label="High threat confidence from detection modules", points=pts))
        score += pts
    elif data.threat_confidence >= 0.4:
        pts = 4
        factors.append(ScoreFactor(label="Moderate threat confidence", points=pts))
        score += pts

    # Blend transparent rule scoring with configurable multi-source correlation.
    score = max(0, min(100, round((score * 0.55) + (correlation["correlated_score"] * 0.45), 1)))
    severity = severity_from_score(score)
    confidence = min(1.0, max(data.threat_confidence, score / 100))

    return ThreatAnalysisResult(
        threat_type=data.threat_type,
        threat_score=score,
        severity=severity,
        confidence=round(confidence, 2),
        affected_communication=affected_communication(data.threat_type, data.communication_status, data.packet_loss_pct),
        risk_factors=factors,
        score_breakdown_total=score,
        source_contributions=correlation["contributions"],
        normalized_evidence=correlation["normalized"],
        evidence_conflict=correlation["conflict"],
        conflict_details=correlation["conflict_details"],
        decision_confidence=correlation["decision_confidence"],
    )
