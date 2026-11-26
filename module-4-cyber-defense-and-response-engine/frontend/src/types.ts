export interface RFContext {
  observation_id?: string
  timestamp?: string
  rssi?: number
  snr?: number
  noise_floor?: number
  packet_rate?: number
  frequency_mhz?: number
  bandwidth_mhz?: number
  packet_loss_pct?: number
  latency_ms?: number
}

export interface StatisticalDeviation {
  rssi?: number
  snr?: number
  noise_floor?: number
  packet_rate?: number
}

export interface ThreatIntelligenceInput {
  threat_confidence?: number | null
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

export type ResponseMode = 'RULE_BASED' | 'SHADOW' | 'MACHINE_LEARNING'

export interface Module4Status {
  response_selection_mode?: ResponseMode
}

export interface ResponseSelectionMetadata {
  configured_mode: 'SHADOW' | 'MACHINE_LEARNING'
  effective_mode?: 'RULE_BASED' | 'MACHINE_LEARNING'
  response_source?: 'RULE_BASED' | 'MACHINE_LEARNING' | 'SAFETY_POLICY'
    | 'SCREENED_RULE_FALLBACK' | 'SAFETY_POLICY_FALLBACK' | 'EVIDENCE_FALLBACK'
  rule_based_response?: string | null
  ml_status?: 'SUCCEEDED' | 'FAILED' | null
  ml_error_code?: string | null
  ml_raw_response?: string | null
  ml_screened_response?: string | null
  ml_screening_reason?: string | null
  ml_prediction_confidence?: number | null
  ml_model_version?: string | null
  ml_inference_latency_ms?: number | null
  rule_based_disagreement?: boolean | null
  safety_override?: boolean | null
  safety_override_reason?: string | null
  fallback_used?: boolean | null
  fallback_reason?: string | null
}

export interface IncidentDetail {
  incident_id: string
  observation_id?: string | null
  timestamp: string
  risk_score: number
  risk_level: string
  decision_confidence?: string | null
  recommended_response: string
  response_rationale?: string | null
  full_response?: string | null
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


  decision_confidence: string
  confidence_rationale: string

  recommended_response: string
  response_selection?: ResponseSelectionMetadata | null
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
