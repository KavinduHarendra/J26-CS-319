from pydantic import BaseModel, Field
from typing import Optional


class ThreatInput(BaseModel):
    uav_id: str = "UAV-01"
    frequency_mhz: float = 2400.0
    signal_strength_dbm: float = -65.0
    noise_level_dbm: float = -90.0
    snr_db: float = 25.0
    bandwidth_mhz: float = 20.0
    packet_loss_pct: float = 0.0
    latency_ms: float = 30.0
    authentication_status: str = "VALID"
    controller_trust_status: str = "TRUSTED"
    communication_status: str = "STABLE"
    threat_type: str = "Normal"
    threat_confidence: float = 0.0
    previous_threat_score: float = 0.0
    force_evidence_conflict: bool = False
    simulated_response_outcome: str = "AUTO"


class ScoreFactor(BaseModel):
    label: str
    points: float


class ThreatAnalysisResult(BaseModel):
    threat_type: str
    threat_score: float
    severity: str
    confidence: float
    affected_communication: str
    risk_factors: list[ScoreFactor]
    score_breakdown_total: float
    source_contributions: list[dict] = Field(default_factory=list)
    normalized_evidence: dict = Field(default_factory=dict)
    evidence_conflict: bool = False
    conflict_details: list[str] = Field(default_factory=list)
    decision_confidence: str = "HIGH"


class ForecastPoint(BaseModel):
    label: str
    minutes_ahead: int
    score: float


class ForecastResult(BaseModel):
    historical: list[dict]
    current_score: float
    forecast_points: list[ForecastPoint]
    trend: str
    trend_slope: float
    method: str = "Linear Regression (Prototype)"
    confidence: str = "MEDIUM"


class DecisionResult(BaseModel):
    reactive_response: str
    reactive_actions: list[str]
    forecast_aware_response: str
    forecast_aware_actions: list[str]
    primary_response: str
    primary_actions: list[str]
    decision_mode: str
    reasons: list[str]
    forecast_influenced: bool


class FullAnalysisResult(BaseModel):
    input: ThreatInput
    analysis: ThreatAnalysisResult
    forecast: ForecastResult
    decision: DecisionResult
    uav_status: dict


class SimulateResponseRequest(BaseModel):
    uav_id: str = "UAV-01"
    threat_type: str
    threat_score: float
    severity: str
    forecast_trend: str
    primary_response: str
    primary_actions: list[str]
    before_evidence: dict = Field(default_factory=dict)
    simulated_response_outcome: str = "AUTO"


class IncidentRecord(BaseModel):
    incident_id: str
    timestamp: str
    uav_id: str
    threat: str
    severity: str
    score: float
    forecast: str
    decision: str
    response: str
    status: str
    effectiveness: str = "NOT EVALUATED"
    before_evidence: dict = Field(default_factory=dict)
    after_evidence: dict = Field(default_factory=dict)
    audit_trail: list[dict] = Field(default_factory=list)


class MultiThreatRequest(BaseModel):
    threats: list[ThreatInput]


class UAVStatus(BaseModel):
    uav_id: str = "UAV-01"
    mission_status: str = "SURVEILLANCE"
    communication: str = "PRIMARY CHANNEL"
    primary_channel: str = "ACTIVE"
    backup_channel: str = "STANDBY"
    gps_status: str = "LOCKED"
    telemetry_status: str = "STABLE"
    current_mode: str = "NORMAL OPERATION"
    security_status: str = "PROTECTED"
    current_threat: str = "NONE"
    threat_severity: str = "LOW"
    threat_score: float = 0.0
    forecast: str = "STABLE"
    recommended_response: str = "Continue Monitoring"
