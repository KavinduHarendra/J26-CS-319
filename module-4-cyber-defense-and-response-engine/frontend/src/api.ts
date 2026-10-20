import type { EvaluateRequest, EvaluateResponse, EvaluateScenario } from './types'

const BASE = '/api'
async function remote<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = Array.isArray(detail)
      ? detail.map((error: { loc?: string[]; msg?: string }) => `${error.loc?.slice(1).join('.')}: ${error.msg}`).join('; ')
      : typeof detail === 'string' ? detail : `Request failed (HTTP ${response.status}). Check your inputs and backend connection.`
    throw new Error(message)
  }
  return response.json()
}

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

export async function fetchRiskHistory(): Promise<{ history: Record<string, unknown>[] }> {
  return remote('/evaluate/risk-history')
}

export async function fetchModule4Status(): Promise<Record<string, unknown>> {
  return remote('/evaluate/status')
}

export async function resetEvaluate(): Promise<Record<string, unknown>> {
  return remote('/evaluate/reset', { method: 'POST' })
}
