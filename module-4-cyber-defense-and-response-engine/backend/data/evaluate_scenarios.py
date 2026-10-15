"""PP1 Demo scenarios in EvaluateRequest format.

9 scenarios for Progress Presentation 1 demonstration, matching the
specification's scenario requirements. Each scenario has a preset
EvaluateRequest payload plus expected outcome labels for verification.

These are SIMULATED / MOCK inputs — no real RF hardware.
"""

from models.defense import EvaluateRequest
from models.module1 import RFContext
from models.module2 import ThreatIntelligence, StatisticalDeviation
from models.module3 import SecureCommunication

EVALUATE_SCENARIOS: dict[str, dict] = {

    "s1_normal_operation": {
        "label": "Scenario 1: Normal Operation",
        "description": "All modules report healthy state. Expected: LOW risk, MONITOR.",
        "expected_risk_level": "LOW",
        "expected_response": "MONITOR",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S1-001",
                "timestamp": "2026-09-26T14:00:00",
                "rssi": -62.0, "snr": 33.0, "noise_floor": -95.0, "packet_rate": 99.0,
                "frequency_mhz": 2400.0,
            },
            "threat_intelligence": {
                "classification": "Normal",
                "severity": None,
                "triggered_rule": None,
                "evidence": ["All RF features within normal range"],
            },
            "secure_communication": {
                "link_state": "TRUSTED",
                "freshness_state": "FRESH",
                "auth_state": "VALID",
                "integrity_state": "VALID",
                "replay_detected": False,
                "comm_decision": "MAINTAIN",
                "link_evidence": ["All communication states nominal"],
            },
        },
    },

    "s2_low_jamming": {
        "label": "Scenario 2: Low Jamming",
        "description": "Module 2 detects low-severity jamming. Link remains trusted. Expected: MEDIUM risk.",
        "expected_risk_level": "MEDIUM",
        "expected_response": "CONTINUE_MONITORING",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S2-001",
                "timestamp": "2026-09-26T14:05:00",
                "rssi": -68.0, "snr": 22.0, "noise_floor": -88.0, "packet_rate": 95.0,
            },
            "threat_intelligence": {
                "classification": "Jamming",
                "severity": "Low",
                "triggered_rule": "J03",
                "evidence": ["Moderate SNR reduction detected", "Noise floor marginally elevated"],
                "statistical_deviation": {"snr": -2.1, "noise_floor": 1.8},
            },
            "secure_communication": {
                "link_state": "TRUSTED",
                "freshness_state": "FRESH",
                "auth_state": "VALID",
                "integrity_state": "VALID",
                "replay_detected": False,
                "comm_decision": "MAINTAIN",
                "link_evidence": ["Link remains authenticated and stable"],
            },
        },
    },

    "s3_critical_jamming": {
        "label": "Scenario 3: Critical Jamming",
        "description": "High-severity jamming + DEGRADED link. Expected: HIGH/CRITICAL, PREPARE_BACKUP_CHANNEL.",
        "expected_risk_level": "CRITICAL",
        "expected_response": "PREPARE_BACKUP_CHANNEL",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S3-001",
                "timestamp": "2026-09-26T14:10:00",
                "rssi": -74.0, "snr": 8.0, "noise_floor": -72.0, "packet_rate": 62.0,
            },
            "threat_intelligence": {
                "classification": "Jamming",
                "severity": "High",
                "triggered_rule": "J01",
                "evidence": [
                    "Significant SNR drop combined with noise floor increase",
                    "Packet rate severely degraded",
                ],
                "statistical_deviation": {"rssi": -1.2, "snr": -6.8, "noise_floor": 5.1, "packet_rate": -0.4},
            },
            "secure_communication": {
                "link_state": "DEGRADED",
                "freshness_state": "FRESH",
                "auth_state": "VALID",
                "integrity_state": "VALID",
                "replay_detected": False,
                "comm_decision": "BACKUP",
                "link_evidence": [
                    "Packet delivery degraded",
                    "Link remains authenticated despite degradation",
                ],
            },
        },
    },

    "s4_comm_compromise": {
        "label": "Scenario 4: Communication Compromise",
        "description": "High-severity jamming + UNTRUSTED link. Expected: CRITICAL, SECURE_HOLD.",
        "expected_risk_level": "CRITICAL",
        "expected_response": "SECURE_HOLD",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S4-001",
                "timestamp": "2026-09-26T14:15:00",
                "rssi": -78.0, "snr": 5.0, "noise_floor": -68.0, "packet_rate": 40.0,
            },
            "threat_intelligence": {
                "classification": "Jamming",
                "severity": "High",
                "triggered_rule": "J01",
                "evidence": ["Wideband noise jamming signature detected", "SNR critically low"],
                "statistical_deviation": {"snr": -9.2, "noise_floor": 7.3},
            },
            "secure_communication": {
                "link_state": "UNTRUSTED",
                "freshness_state": "STALE",
                "auth_state": "INVALID",
                "integrity_state": "SUSPICIOUS",
                "replay_detected": False,
                "comm_decision": "SECURE_HOLD",
                "link_evidence": [
                    "Controller authentication failed",
                    "Message integrity check failed",
                    "Link classified as UNTRUSTED",
                ],
            },
        },
    },

    "s5_unknown_anomaly_trusted": {
        "label": "Scenario 5: Unknown RF Anomaly (Trusted Link)",
        "description": "Unexpected RF behavior but comms trusted. Expected: conservative INCREASE_MONITORING.",
        "expected_risk_level": "MEDIUM",
        "expected_response": "INCREASE_MONITORING",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S5-001",
                "timestamp": "2026-09-26T14:20:00",
                "rssi": -69.0, "snr": 19.0, "noise_floor": -85.0, "packet_rate": 87.0,
            },
            "threat_intelligence": {
                "classification": "Unknown Anomaly",
                "severity": "Medium",
                "triggered_rule": None,
                "evidence": [
                    "RF behavior is abnormal but does not match known jamming patterns",
                    "Possible environmental interference or legitimate RF change",
                ],
                "abnormal_features": ["snr", "noise_floor"],
            },
            "secure_communication": {
                "link_state": "TRUSTED",
                "freshness_state": "FRESH",
                "auth_state": "VALID",
                "integrity_state": "VALID",
                "replay_detected": False,
                "comm_decision": "MAINTAIN",
                "link_evidence": ["Communication link is stable and authenticated"],
            },
        },
    },

    "s6_unknown_suspicious": {
        "label": "Scenario 6: Unknown Anomaly + Suspicious Link",
        "description": "Unclassified anomaly + suspicious comms. Expected: higher risk, OPERATOR_ESCALATION.",
        "expected_risk_level": "HIGH",
        "expected_response": "OPERATOR_ESCALATION",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S6-001",
                "timestamp": "2026-09-26T14:25:00",
                "rssi": -71.0, "snr": 16.0, "noise_floor": -83.0, "packet_rate": 80.0,
            },
            "threat_intelligence": {
                "classification": "Unknown Anomaly",
                "severity": "Medium",
                "triggered_rule": None,
                "evidence": ["Anomalous RF pattern detected — no rule match", "Spectral characteristics unusual"],
                "abnormal_features": ["rssi", "snr"],
            },
            "secure_communication": {
                "link_state": "SUSPICIOUS",
                "freshness_state": "STALE",
                "auth_state": "SUSPICIOUS",
                "integrity_state": "VALID",
                "replay_detected": False,
                "comm_decision": "SWITCH",
                "link_evidence": ["Session freshness degraded", "Controller authentication is suspicious"],
            },
        },
    },

    "s7_conflicting_evidence": {
        "label": "Scenario 7: Conflicting Evidence",
        "description": "Normal RF + UNTRUSTED link = conflict. Expected: conflict flag, LOW confidence, OPERATOR_ESCALATION.",
        "expected_risk_level": "HIGH",
        "expected_response": "OPERATOR_ESCALATION",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S7-001",
                "timestamp": "2026-09-26T14:30:00",
                "rssi": -63.0, "snr": 30.0, "noise_floor": -94.0, "packet_rate": 98.0,
            },
            "threat_intelligence": {
                "classification": "Normal",
                "severity": None,
                "triggered_rule": None,
                "evidence": ["RF features within expected range — no anomaly detected"],
            },
            "secure_communication": {
                "link_state": "UNTRUSTED",
                "freshness_state": "FRESH",
                "auth_state": "INVALID",
                "integrity_state": "VALID",
                "replay_detected": False,
                "comm_decision": "SECURE_HOLD",
                "link_evidence": [
                    "Controller authentication failed",
                    "Link classified as UNTRUSTED despite clean RF",
                ],
            },
        },
    },

    "s8_replay_attempt": {
        "label": "Scenario 8: Replay Attempt",
        "description": "Module 3 detects replay. Expected: SECURE_HOLD regardless of RF classification.",
        "expected_risk_level": "CRITICAL",
        "expected_response": "SECURE_HOLD",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S8-001",
                "timestamp": "2026-09-26T14:35:00",
                "rssi": -65.0, "snr": 25.0, "noise_floor": -91.0, "packet_rate": 96.0,
            },
            "threat_intelligence": {
                "classification": "Normal",
                "severity": None,
                "triggered_rule": None,
                "evidence": ["RF appears normal — no jamming signature detected"],
            },
            "secure_communication": {
                "link_state": "SUSPICIOUS",
                "freshness_state": "REPLAY",
                "auth_state": "VALID",
                "integrity_state": "VALID",
                "replay_detected": True,
                "comm_decision": "SECURE_HOLD",
                "link_evidence": [
                    "Replay attack detected on command channel",
                    "Duplicate sequence number detected",
                    "Message timestamp outside acceptable window",
                ],
            },
        },
    },

    "s9_escalating_attack": {
        "label": "Scenario 9: Escalating Attack (Final Stage)",
        "description": "Simulates third step of escalating attack sequence. Expected: CRITICAL, ESCALATING trend, OPERATOR_ESCALATION.",
        "expected_risk_level": "CRITICAL",
        "expected_response": "OPERATOR_ESCALATION",
        "payload": {
            "rf_context": {
                "observation_id": "OBS-S9-003",
                "timestamp": "2026-09-26T14:42:00",
                "rssi": -76.0, "snr": 7.0, "noise_floor": -71.0, "packet_rate": 55.0,
            },
            "threat_intelligence": {
                "classification": "Jamming",
                "severity": "High",
                "triggered_rule": "J01",
                "evidence": [
                    "Severe SNR degradation",
                    "Noise floor critically elevated",
                    "Jamming intensity increasing",
                ],
                "statistical_deviation": {"snr": -8.5, "noise_floor": 6.2, "packet_rate": -0.6},
            },
            "secure_communication": {
                "link_state": "SUSPICIOUS",
                "freshness_state": "STALE",
                "auth_state": "SUSPICIOUS",
                "integrity_state": "VALID",
                "replay_detected": False,
                "comm_decision": "SWITCH",
                "link_evidence": [
                    "Link quality declining progressively",
                    "Authentication becoming unreliable",
                ],
            },
        },
    },
}

# Escalating attack sequence — 3 steps showing progressive degradation
ESCALATION_SEQUENCE = [
    {
        "step": 1,
        "label": "Escalation Step 1: Low Jamming / Trusted",
        "payload": {
            "rf_context": {"observation_id": "OBS-ESC-001", "timestamp": "2026-09-26T14:38:00",
                           "rssi": -66.0, "snr": 24.0, "noise_floor": -87.0, "packet_rate": 93.0},
            "threat_intelligence": {
                "classification": "Jamming", "severity": "Low", "triggered_rule": "J03",
                "evidence": ["Mild SNR reduction — early jamming signature"],
            },
            "secure_communication": {
                "link_state": "TRUSTED", "freshness_state": "FRESH",
                "auth_state": "VALID", "integrity_state": "VALID",
                "replay_detected": False, "comm_decision": "MAINTAIN",
                "link_evidence": ["Link fully operational"],
            },
        },
    },
    {
        "step": 2,
        "label": "Escalation Step 2: Medium Jamming / Degraded",
        "payload": {
            "rf_context": {"observation_id": "OBS-ESC-002", "timestamp": "2026-09-26T14:40:00",
                           "rssi": -71.0, "snr": 14.0, "noise_floor": -80.0, "packet_rate": 74.0},
            "threat_intelligence": {
                "classification": "Jamming", "severity": "Medium", "triggered_rule": "J02",
                "evidence": ["Moderate jamming — SNR degradation progressing", "Noise floor rising"],
                "statistical_deviation": {"snr": -4.2, "noise_floor": 3.6},
            },
            "secure_communication": {
                "link_state": "DEGRADED", "freshness_state": "FRESH",
                "auth_state": "VALID", "integrity_state": "VALID",
                "replay_detected": False, "comm_decision": "BACKUP",
                "link_evidence": ["Packet delivery rate declining", "Link authenticated but degraded"],
            },
        },
    },
    {
        "step": 3,
        "label": "Escalation Step 3: High Jamming / Suspicious",
        "payload": EVALUATE_SCENARIOS["s9_escalating_attack"]["payload"],
    },
]
