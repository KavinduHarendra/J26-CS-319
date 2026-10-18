// Extended TypeScript types for Module 4 Evaluate API

export interface ThreatInput {
  uav_id: string
  frequency_mhz: number
  signal_strength_dbm: number
  noise_level_dbm: number
  snr_db: number
  bandwidth_mhz: number
  packet_loss_pct: number
  latency_ms: number
  authentication_status: string
  controller_trust_status: string
  communication_status: string
  threat_type: string
  threat_confidence: number
  previous_threat_score: number
  force_evidence_conflict?: boolean
  simulated_response_outcome?: string
}

export interface ScoreFactor {
  label: string
  points: number
}

export interface ThreatAnalysis {
  threat_type: string
  threat_score: number
  severity: string
  confidence: number
  affected_communication: string
  risk_factors: ScoreFactor[]
  score_breakdown_total: number
  source_contributions: { source: string; raw_score: number; weight: number; weighted_points: number }[]
  normalized_evidence: Record<string, string | number>
  evidence_conflict: boolean
  conflict_details: string[]
  decision_confidence: string
}

export interface ForecastPoint {
  label: string
  minutes_ahead: number
  score: number
}

export interface Forecast {
  historical: { time: string; score: number; type: string }[]
  current_score: number
  forecast_points: ForecastPoint[]
  trend: string
  trend_slope: number
  method: string
  confidence: string
}

export interface Decision {
  reactive_response: string
  reactive_actions: string[]
  forecast_aware_response: string
  forecast_aware_actions: string[]
  primary_response: string
  primary_actions: string[]
  decision_mode: string
  reasons: string[]
  forecast_influenced: boolean
}

export interface UAVStatus {
  uav_id: string
  mission_status: string
  communication: string
  primary_channel: string
  backup_channel: string
  gps_status: string
  telemetry_status: string
  current_mode: string
  security_status: string
  current_threat: string
  threat_severity: string
  threat_score: number
  forecast: string
  recommended_response: string
}

export interface FullAnalysis {
  input: ThreatInput
  analysis: ThreatAnalysis
  forecast: Forecast
  decision: Decision
  uav_status: UAVStatus
}

export interface Incident {
  incident_id: string
  timestamp: string
  uav_id: string
  threat: string
  severity: string
  score: number
  forecast: string
  decision: string
  response: string
  status: string
  effectiveness: string
  before_evidence: Record<string, number | string>
  after_evidence: Record<string, number | string>
  audit_trail: { timestamp: string; stage: string }[]
}

export interface SimulateResult {
  steps: string[]
  uav_status: UAVStatus
  incident: Incident
  disclaimer: string
  effectiveness: {
    classification: string
    before: Record<string, number | string>
    after: Record<string, number | string>
    explanation: string
  }
}

// ─── Module 4 Evaluate API Types ─────────────────────────────────────────────

export interface RFContext {
  observation_id?: string
  timestamp?: string
  rssi?: number
  snr?: number
  noise_floor?: number
  packet_rate?: number
  frequency_mhz?: number
  bandwidth_mhz?: number
}

export interface StatisticalDeviation {
  rssi?: number
  snr?: number
  noise_floor?: number
  packet_rate?: number
}

export interface ThreatIntelligenceInput {
  classification: 'Normal' | 'Jamming' | 'Unknown Anomaly'
  severity?: 'Low' | 'Medium' | 'High' | null
  triggered_rule?: string | null
  abnormal_features?: string[]
  statistical_deviation?: StatisticalDeviation
  evidence?: string[]
}

export interface SecureCommunicationInput {
  link_state: 'TRUSTED' | 'DEGRADED' | 'SUSPICIOUS' | 'UNTRUSTED'
  freshness_state: 'FRESH' | 'STALE' | 'REPLAY'
  auth_state: 'VALID' | 'SUSPICIOUS' | 'INVALID'
  integrity_state: 'VALID' | 'SUSPICIOUS' | 'INVALID'
  replay_detected: boolean
  comm_decision?: 'MAINTAIN' | 'SWITCH' | 'BACKUP' | 'SECURE_HOLD' | null
  link_evidence?: string[]
}

export interface EvaluateRequest {
  rf_context: RFContext
  threat_intelligence: ThreatIntelligenceInput
  secure_communication: SecureCommunicationInput
}

export interface RiskScoreComponent {
  label: string
  source: string
  points: number
  weight_note: string
}

export interface RiskBreakdown {
  classification_points: number
  severity_points: number
  link_state_points: number
  freshness_points: number
  auth_points: number
  integrity_points: number
  components: RiskScoreComponent[]
  raw_total: number
  capped_score: number
}

export interface SourceContribution {
  source: string
  evidence: string[]
  weight: number
  normalized_score: number
}

export interface CorrelationResult {
  module2_classification: string
  module2_severity: string | null
  module3_link_state: string
  module3_replay: boolean
  source_contributions: SourceContribution[]
  correlated_risk_boost: number
  correlation_note: string
}

export interface TrendWindow {
  scores: number[]
  trend: string
  slope: number
  window_size: number
  method: string
}

export interface EvaluateResponse {
  incident_id: string
  observation_id: string
  timestamp: string

  risk_score: number
  risk_level: string
  risk_breakdown: RiskBreakdown

  correlation: CorrelationResult

  evidence_conflict: boolean
  conflict_reason?: string

  trend: string
  trend_window: TrendWindow

  decision_confidence: string
  confidence_rationale: string

  recommended_response: string
  response_status: string
  response_rationale: string

  reasons: string[]
  pipeline_stages: string[]

  baseline_response: string
  baseline_vs_proposed: string

  module1_context: Record<string, string | number | null>
  module2_context: Record<string, unknown>
  module3_context: Record<string, unknown>
  integration_status?: string
  input_sources?: Record<string, string>
  match_method?: string
}

export interface EvaluateScenario {
  id: string
  label: string
  description: string
  expected_risk_level?: string
  expected_response?: string
}
