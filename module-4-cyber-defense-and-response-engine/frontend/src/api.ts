import type {
  FullAnalysis, Incident, SimulateResult, ThreatInput, UAVStatus,
  EvaluateRequest, EvaluateResponse, EvaluateScenario,
} from './types'
import * as demo from './demoEngine'

const BASE = '/api'

async function remote<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

// ─── Legacy API (ThreatSimulation page) ───────────────────────────────────────

export const fetchScenarios = () => remote('/scenarios')

export async function fetchScenario(id: string): Promise<{ scenario: ThreatInput }> {
  try { return await remote(`/scenarios/${id}`) } catch { return demo.scenario(id) }
}

export async function analyzeThreat(data: ThreatInput): Promise<FullAnalysis> {
  try {
    return await remote('/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
  } catch { return demo.analyze(data) }
}

type ResponsePayload = {
  uav_id: string; threat_type: string; threat_score: number; severity: string
  forecast_trend: string; primary_response: string; primary_actions: string[]
  before_evidence: Record<string, number | string>; simulated_response_outcome?: string
}

export async function simulateResponse(p: ResponsePayload): Promise<SimulateResult> {
  try {
    return await remote('/simulate-response', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) })
  } catch { return demo.simulate(p) }
}

export async function fetchUAVStatus(): Promise<{ status: UAVStatus }> {
  try { return await remote('/uav-status') } catch { return demo.status() }
}

export async function fetchIncidents(): Promise<{ incidents: Incident[] }> {
  try { return await remote('/incidents') } catch { return demo.logs() }
}

export async function resetSimulation() {
  try { return await remote('/reset', { method: 'POST' }) } catch { return demo.reset() }
}

type PriorityResult = {
  primary_threat: { uav_id: string; threat_type: string; score: number; severity: string }
  secondary_threats: { uav_id: string; threat_type: string; score: number; severity: string }[]
  reason: string
}

export async function prioritizeThreats(threats: ThreatInput[]): Promise<PriorityResult> {
  try {
    return await remote<PriorityResult>('/prioritize-threats', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ threats }) })
  } catch { return demo.prioritize(threats) }
}

// ─── Module 4 Evaluate API ────────────────────────────────────────────────────

export async function evaluateThreat(request: EvaluateRequest): Promise<EvaluateResponse> {
  return remote('/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
}

export async function evaluateFiles(module2File: File, module3File: File): Promise<EvaluateResponse & {
  integration_status?: string
  error_code?: string
  message?: string
  field?: string
}> {
  const form = new FormData()
  form.append('module2_file', module2File)
  form.append('module3_file', module3File)
  return remote('/evaluate-files', { method: 'POST', body: form })
}

export async function fetchEvaluateScenarios(): Promise<{ scenarios: EvaluateScenario[] }> {
  return remote('/evaluate/scenarios')
}

export async function fetchEvaluateScenario(id: string): Promise<{ id: string; label: string; payload: EvaluateRequest }> {
  return remote(`/evaluate/scenarios/${id}`)
}

export async function fetchEscalationStep(step: number): Promise<{ step: number; label: string; payload: EvaluateRequest }> {
  return remote(`/evaluate/escalation/${step}`)
}

export async function fetchEvaluateIncidents(limit = 50): Promise<{ incidents: Record<string, unknown>[] }> {
  return remote(`/evaluate/incidents?limit=${limit}`)
}

export async function fetchRiskHistory(): Promise<{ history: Record<string, unknown>[]; current_window: number[] }> {
  return remote('/evaluate/risk-history')
}

export async function fetchModule4Status(): Promise<Record<string, unknown>> {
  return remote('/evaluate/status')
}

export async function resetEvaluate(): Promise<Record<string, unknown>> {
  return remote('/evaluate/reset', { method: 'POST' })
}
