"""Configurable multi-source evidence correlation for the research prototype."""

import json
from pathlib import Path
from models.schemas import ThreatInput

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "engine_config.json"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def clamp(value: float) -> float:
    return max(0.0, min(100.0, round(value, 1)))


def correlate_evidence(data: ThreatInput) -> dict:
    config = load_config()
    weights = config["source_weights"]

    rf_risk = clamp(
        (max(0, 20 - data.snr_db) * 2.2)
        + (max(0, data.noise_level_dbm + 90) * 2.0)
        + (35 if data.threat_type == "Jamming" else 12 if data.threat_type != "Normal" else 0)
    )
    ai_risk = clamp(data.threat_confidence * 100)
    communication_risk = clamp(
        data.packet_loss_pct * 2
        + min(data.latency_ms / 4, 25)
        + (25 if data.authentication_status.upper() != "VALID" else 0)
        + (20 if data.controller_trust_status.upper() != "TRUSTED" else 0)
        + (15 if data.communication_status.upper() != "STABLE" else 0)
    )
    history_risk = clamp(data.previous_threat_score)
    raw_sources = {
        "rf": rf_risk,
        "ai": ai_risk,
        "communication": communication_risk,
        "history": history_risk,
    }
    contributions = [
        {
            "source": source.upper(),
            "raw_score": score,
            "weight": weights[source],
            "weighted_points": round(score * weights[source], 1),
        }
        for source, score in raw_sources.items()
    ]

    gap = max(raw_sources.values()) - min(raw_sources.values())
    conflict = data.force_evidence_conflict or gap >= config["conflict"]["minimum_source_gap"]
    details = []
    if conflict:
        strongest = max(raw_sources, key=raw_sources.get)
        weakest = min(raw_sources, key=raw_sources.get)
        details.append(
            f"{strongest.upper()} evidence ({raw_sources[strongest]}) disagrees with "
            f"{weakest.upper()} evidence ({raw_sources[weakest]})"
        )
        details.append("Decision confidence reduced; operator verification recommended")

    normalized = {
        "uav_id": data.uav_id,
        "threat_type": data.threat_type,
        "rf_risk": rf_risk,
        "ai_confidence": data.threat_confidence,
        "snr_db": data.snr_db,
        "packet_loss_pct": data.packet_loss_pct,
        "communication_status": data.communication_status,
        "authentication_status": data.authentication_status,
        "controller_trust": data.controller_trust_status,
    }
    return {
        "contributions": contributions,
        "correlated_score": clamp(sum(item["weighted_points"] for item in contributions)),
        "normalized": normalized,
        "conflict": conflict,
        "conflict_details": details,
        "decision_confidence": "LOW" if conflict else "HIGH" if data.threat_confidence >= 0.7 else "MEDIUM",
    }
