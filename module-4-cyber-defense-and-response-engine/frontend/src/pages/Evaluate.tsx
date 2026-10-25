import { useState, useCallback, useEffect, useRef } from 'react'
import {
  Shield, AlertTriangle, CheckCircle2,
  AlertCircle, RefreshCw, Zap, Activity, FileText, Lock,
  ArrowRight, ChevronRight, BarChart3,
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { evaluateThreat, evaluateFiles, fetchEvaluateScenarios, fetchEvaluateScenario, fetchEscalationStep, fetchRiskHistory } from '../api'
import type { EvaluateRequest, EvaluateResponse, EvaluateScenario } from '../types'
import { Panel, StatRow } from '../components/Panel'
import SeverityBadge from '../components/SeverityBadge'

// ─── Default request payload ──────────────────────────────────────────────────

const DEFAULT_REQUEST: EvaluateRequest = {
  rf_context: {
    observation_id: 'OBS-DEMO-001',
    timestamp: new Date().toISOString(),
  },
  threat_intelligence: {
    classification: 'Normal',
    severity: null,
    triggered_rule: null,
    evidence: ['All RF features within normal range'],
    abnormal_features: [],
  },
  secure_communication: {
    link_state: 'TRUSTED',
    freshness_state: 'FRESH',
    auth_state: 'VALID',
    integrity_state: 'VALID',
    replay_detected: false,
    comm_decision: 'MAINTAIN',
    link_evidence: ['All communication states nominal'],
  },
}

// ─── Color helpers ────────────────────────────────────────────────────────────

function riskColor(level: string) {
  return level === 'CRITICAL' ? 'text-red-400'
    : level === 'HIGH' ? 'text-orange-400'
    : level === 'MEDIUM' ? 'text-yellow-400'
    : 'text-emerald-400'
}

function riskBg(level: string) {
  return level === 'CRITICAL' ? 'bg-red-500/15 border-red-500/40'
    : level === 'HIGH' ? 'bg-orange-500/15 border-orange-500/40'
    : level === 'MEDIUM' ? 'bg-yellow-500/15 border-yellow-500/40'
    : 'bg-emerald-500/15 border-emerald-500/40'
}

function responseBg(resp: string) {
  const r = resp.toUpperCase()
  if (r.includes('SECURE_HOLD') || r.includes('OPERATOR')) return 'bg-red-500/20 border-red-500/50 text-red-300'
  if (r.includes('SWITCH') || r.includes('BACKUP')) return 'bg-orange-500/20 border-orange-500/50 text-orange-300'
  if (r.includes('PREPARE') || r.includes('INCREASE')) return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-300'
  if (r.includes('CONTINUE')) return 'bg-blue-500/20 border-blue-500/50 text-blue-300'
  return 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
}

function confidenceColor(c: string) {
  return c === 'HIGH' ? 'text-emerald-400' : c === 'LOW' ? 'text-red-400' : 'text-yellow-400'
}

// ─── Pipeline Visualization ──────────────────────────────────────────────────

function PipelineViz({ active }: { active: boolean }) {
  const stages = [
    { label: 'MODULE 2\nThreat Intel', color: 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10', icon: Shield },
    { label: 'MODULE 3\nComm Trust', color: 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10', icon: Lock },
  ]
  return (
    <div className="bg-cyber-surface border border-cyan-400/20 rounded-xl p-4">
      <p className="text-[10px] text-white/65 uppercase tracking-wider mb-3">Decision Pipeline — Multi-Source Correlation</p>
      <div className="flex items-center gap-2 flex-wrap">
        {stages.map(({ label, color, icon: Icon }) => (
          <div key={label} className={`flex flex-col items-center px-3 py-2 rounded-lg border text-center text-[10px] font-semibold ${color}`}>
            <Icon className="w-4 h-4 mb-1" />
            {label.split('\n').map((l, i) => <span key={i}>{l}</span>)}
          </div>
        ))}
        <ChevronRight className="w-4 h-4 text-white/40" />
        <div className={`flex flex-col items-center px-3 py-2 rounded-lg border text-center text-[10px] font-semibold ${active ? 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10 animate-pulse' : 'text-white/65 border-white/20'}`}>
          <Activity className="w-4 h-4 mb-1" />
          MULTI-SOURCE{'\n'}CORRELATION
        </div>
        <ChevronRight className="w-4 h-4 text-white/40" />
        <div className={`flex flex-col items-center px-3 py-2 rounded-lg border text-center text-[10px] font-semibold ${active ? 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10' : 'text-white/65 border-white/20'}`}>
          <BarChart3 className="w-4 h-4 mb-1" />
          RISK{'\n'}SCORE
        </div>
        <ChevronRight className="w-4 h-4 text-white/40" />
        <div className={`flex flex-col items-center px-4 py-2 rounded-lg border text-center text-[10px] font-bold ${active ? 'text-cyan-400 border-cyan-400/60 bg-cyan-400/15' : 'text-white/65 border-white/20'}`}>
          <Zap className="w-4 h-4 mb-1" />
          RESPONSE{'\n'}SELECTION
        </div>
        <ChevronRight className="w-4 h-4 text-white/40" />
        <div className={`flex flex-col items-center px-4 py-2 rounded-lg border text-center text-[10px] font-bold ${active ? 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10' : 'text-white/65 border-white/20'}`}>
          <FileText className="w-4 h-4 mb-1" />
          EXPLANATION &amp;{'\n'}AUDIT LOGGING
        </div>
      </div>
    </div>
  )
}

// ─── Module Status Bar ────────────────────────────────────────────────────────

function RiskGauge({ score, level }: { score: number; level: string }) {
  const color = level === 'CRITICAL' ? '#ef4444' : level === 'HIGH' ? '#f97316' : level === 'MEDIUM' ? '#eab308' : '#10b981'
  const pct = Math.min(100, score)
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-32 h-32 flex items-center justify-center">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          <circle cx="60" cy="60" r="52" fill="none" stroke="#1f2937" strokeWidth="12" />
          <circle
            cx="60" cy="60" r="52" fill="none"
            stroke={color} strokeWidth="12"
            strokeDasharray={`${(pct / 100) * 326.7} 326.7`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute flex flex-col items-center">
          <span className="text-3xl font-bold text-white">{score}</span>
          <span className="text-xs text-gray-500">/100</span>
        </div>
      </div>
      <span className={`mt-2 text-sm font-bold ${riskColor(level)}`}>{level}</span>
    </div>
  )
}

// Recorded risk history for audit review
function HistoryChart({ history }: { history: { incident_id: string; risk_score: number; risk_level: string }[] }) {
  const data = history.map((h, i) => ({
    id: `#${i + 1}`,
    risk: h.risk_score,
    level: h.risk_level,
  }))
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="id" stroke="#6b7280" fontSize={10} />
          <YAxis domain={[0, 100]} stroke="#6b7280" fontSize={10} />
          <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }} />
          <Legend />
          <ReferenceLine y={75} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'CRITICAL', fill: '#ef4444', fontSize: 9 }} />
          <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: 'HIGH', fill: '#f59e0b', fontSize: 9 }} />
          <Line type="monotone" dataKey="risk" stroke="#06b6d4" strokeWidth={2} dot={{ r: 3 }} name="Risk Score" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── Main Evaluate Page ───────────────────────────────────────────────────────

export default function Evaluate({ mode = 'files' }: { mode?: 'files' | 'testing' }) {
  const [request, setRequest] = useState<EvaluateRequest>(DEFAULT_REQUEST)
  const [result, setResult] = useState<EvaluateResponse | null>(null)
  const [scenarios, setScenarios] = useState<EvaluateScenario[]>([])
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<Record<string, unknown>[]>([])
  const [module2File, setModule2File] = useState<File | null>(null)
  const [module3File, setModule3File] = useState<File | null>(null)
  const [integrationError, setIntegrationError] = useState<string | null>(null)
  const [evaluationError, setEvaluationError] = useState<string | null>(null)
  const [scenarioError, setScenarioError] = useState<string | null>(null)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const operationVersion = useRef(0)
  const historyVersion = useRef(0)

  const clearCurrentResult = () => {
    operationVersion.current += 1
    setResult(null)
    setLoading(false)
    setEvaluationError(null)
    setIntegrationError(null)
  }

  const loadScenarios = useCallback(async () => {
    try {
      const data = await fetchEvaluateScenarios()
      setScenarios(data.scenarios)
      setScenarioError(null)
    } catch {
      setScenarioError('Unable to load preset scenarios. Check the backend connection and reload this page.')
    }
  }, [])

  const loadHistory = useCallback(async () => {
    const version = ++historyVersion.current
    try {
      const data = await fetchRiskHistory()
      if (version !== historyVersion.current) return
      setHistory(data.history)
      setHistoryError(null)
    } catch {
      if (version === historyVersion.current) setHistoryError('Unable to refresh audit history. The displayed history may be outdated.')
    }
  }, [])

  useEffect(() => {
    if (mode === 'testing') loadScenarios()
    loadHistory()
    return () => { operationVersion.current += 1; historyVersion.current += 1 }
  }, [mode, loadScenarios, loadHistory])

  const handleEvaluate = async () => {
    const version = ++operationVersion.current
    setLoading(true)
    setEvaluationError(null)
    setResult(null)
    try {
      const res = await evaluateThreat(request)
      if (version !== operationVersion.current) return
      setResult(res)
      loadHistory()
    } catch (e) {
      if (version !== operationVersion.current) return
      setEvaluationError(e instanceof Error ? e.message : 'Evaluation failed. Check your inputs and backend connection.')
    } finally {
      if (version === operationVersion.current) setLoading(false)
    }
  }

  const handleFileEvaluate = async () => {
    const version = ++operationVersion.current
    setResult(null)
    if (!module2File || !module3File) {
      setLoading(false)
      setIntegrationError('Select both Module 2 and Module 3 JSON files.')
      return
    }
    setLoading(true)
    setIntegrationError(null)
    try {
      const res = await evaluateFiles(module2File, module3File)
      if (version !== operationVersion.current) return
      if (res.integration_status === 'FAILED') {
        setIntegrationError(`${res.error_code ?? 'INTEGRATION_ERROR'}: ${res.message ?? 'Validation failed.'}`)
        setResult(null)
      } else {
        setResult(res)
        loadHistory()
      }
    } catch (e) {
      if (version !== operationVersion.current) return
      setIntegrationError(e instanceof Error ? e.message : 'File integration failed.')
    } finally {
      if (version === operationVersion.current) setLoading(false)
    }
  }

  const downloadResult = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${result.incident_id}-module4-decision.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const loadScenario = async (id: string) => {
    clearCurrentResult()
    const version = operationVersion.current
    setLoading(true)
    try {
      const data = await fetchEvaluateScenario(id)
      if (version !== operationVersion.current) return
      setRequest(data.payload)
      setResult(null)
      setEvaluationError(null)
    } catch {
      if (version !== operationVersion.current) return
      setEvaluationError('Unable to load the scenario. Check your backend connection.')
    } finally {
      if (version === operationVersion.current) setLoading(false)
    }
  }

  const loadEscalationStep = async (step: number) => {
    clearCurrentResult()
    const version = operationVersion.current
    setLoading(true)
    try {
      const data = await fetchEscalationStep(step)
      if (version !== operationVersion.current) return
      setRequest(data.payload)
      setResult(null)
      setEvaluationError(null)
    } catch {
      if (version !== operationVersion.current) return
      setEvaluationError('Unable to load the test step. Check your backend connection.')
    } finally {
      if (version === operationVersion.current) setLoading(false)
    }
  }

  const handleReset = () => {
    clearCurrentResult()
    setRequest(DEFAULT_REQUEST)
  }

  const updateTI = (field: string, value: unknown) => {
    clearCurrentResult()
    setRequest(prev => ({
      ...prev,
      threat_intelligence: {
        ...prev.threat_intelligence, [field]: value, evidence: [], abnormal_features: [], statistical_deviation: undefined,
        ...(field === 'classification' ? { triggered_rule: null } : {}),
      },
    }))
    setResult(null)
  }

  const updateSC = (field: string, value: unknown) => {
    clearCurrentResult()
    setRequest(prev => ({
      ...prev,
      secure_communication: {
        ...prev.secure_communication, [field]: value, link_evidence: [],
        ...(field === 'freshness_state' ? { replay_detected: value === 'REPLAY' } : {}),
        ...(field === 'replay_detected' ? { freshness_state: value ? 'REPLAY' as const : prev.secure_communication.freshness_state === 'REPLAY' ? 'FRESH' as const : prev.secure_communication.freshness_state } : {}),
      },
    }))
    setResult(null)
  }

  const updateRF = (field: string, value: string | number | undefined) => {
    clearCurrentResult()
    setRequest(prev => ({
      ...prev, rf_context: { ...prev.rf_context, [field]: value },
      threat_intelligence: { ...prev.threat_intelligence, evidence: [], abnormal_features: [], statistical_deviation: undefined },
    }))
    setResult(null)
  }

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <header>
        <h1 className="text-2xl font-bold text-white">
          {mode === 'testing' ? 'Defense Testing' : 'Autonomous Cyber Defense & Response Engine'}
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          {mode === 'testing' ? 'Test the defense engine using preset scenarios or values you enter manually.' : 'Explainable RF-Aware Risk Assessment and Response Prioritization for UAV Cyber Defense'}
        </p>
      </header>


      {mode === 'files' && (<section aria-labelledby="file-integration-title" className="overflow-hidden rounded-2xl border border-cyan-400/30 bg-cyber-surface ">
        <div className="border-b border-cyan-400/20 bg-cyber-surface px-6 py-6 sm:px-8">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-cyan-400">Module 2 + Module 3 JSON</p>
          <h2 id="file-integration-title" className="text-2xl font-bold text-white sm:text-3xl">File-Based Integration</h2>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-white/65 sm:text-base">Upload threat intelligence and secure communication files to assess risk and generate a defense decision.</p>
        </div>
        <div className="space-y-6 p-6 sm:p-8">
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <label className="integration-upload integration-upload-intelligence flex min-w-0 flex-col gap-4 rounded-xl border p-6 transition">
              <span className="flex items-center gap-3 text-lg font-semibold text-white"><Shield className="h-6 w-6 shrink-0" />Module 2 threat intelligence</span>
              <span className="text-sm text-white/65">Select the threat intelligence JSON file.</span>
              <input type="file" accept=".json,application/json" onChange={e => { clearCurrentResult(); setModule2File(e.target.files?.[0] ?? null) }}
                className="w-full min-w-0 cursor-pointer text-sm text-white/80 file:mr-4 file:cursor-pointer file:rounded-lg file:border-0 file:bg-cyan-400/20 file:px-4 file:py-3 file:text-sm file:font-semibold file:text-white hover:file:bg-cyan-400/30" />
            </label>
            <label className="integration-upload integration-upload-communication flex min-w-0 flex-col gap-4 rounded-xl border p-6 transition">
              <span className="flex items-center gap-3 text-lg font-semibold text-white"><Lock className="h-6 w-6 shrink-0" />Module 3 secure communication</span>
              <span className="text-sm text-white/65">Select the secure communication JSON file.</span>
              <input type="file" accept=".json,application/json" onChange={e => { clearCurrentResult(); setModule3File(e.target.files?.[0] ?? null) }}
                className="w-full min-w-0 cursor-pointer text-sm text-white/80 file:mr-4 file:cursor-pointer file:rounded-lg file:border-0 file:bg-cyan-400/20 file:px-4 file:py-3 file:text-sm file:font-semibold file:text-white hover:file:bg-cyan-400/30" />
            </label>
          </div>
          <p className="text-sm leading-relaxed text-white/65">Files are validated independently, matched by observation ID (or timestamp fallback), then processed through the HCRDM pipeline and recorded in the audit log.</p>
          <button onClick={handleFileEvaluate} disabled={loading}
            className="integration-run mx-auto flex min-h-10 w-fit max-w-full items-center justify-center gap-2 rounded-lg border px-5 py-2 text-sm font-bold transition disabled:cursor-wait disabled:opacity-50">
            <Zap className="h-4 w-4 shrink-0" />
            {loading ? 'PROCESSING...' : 'RUN FILE INTEGRATION'}
          </button>
          {integrationError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{integrationError}</p>}
          {result?.integration_status === 'SUCCESS' && (
            <div role="status" className="flex flex-wrap items-center gap-4 rounded-lg border border-cyan-400/30 bg-cyan-400/10 p-4">
              <p className="text-sm text-cyan-400">File integration succeeded using {result.match_method} matching.</p>
              <button onClick={downloadResult} className="text-sm font-semibold text-cyan-400 underline hover:text-white">Download decision JSON</button>
            </div>
          )}
        </div>
      </section>)}

      {/* ── Scenario Selector ── */}
      {mode === 'testing' && (<>
      {scenarioError && <p role="alert" className="text-sm text-red-300">{scenarioError}</p>}
      <Panel title="PRESET TEST SCENARIOS — Select to Load">
        <div className="flex flex-wrap gap-2 mb-3">
          {scenarios.map(s => (
            <button
              key={s.id}
              onClick={() => loadScenario(s.id)}
              className="px-3 py-1.5 text-xs rounded-lg border border-gray-700 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-gray-300 transition"
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="border-t border-gray-800 pt-3">
          <p className="text-[10px] text-gray-500 mb-2">ESCALATING ATTACK SEQUENCE (3 steps)</p>
          <div className="flex gap-2">
            {[1, 2, 3].map(step => (
              <button
                key={step}
                onClick={() => loadEscalationStep(step)}
                className="px-3 py-1.5 text-xs rounded-lg border border-amber-700/50 hover:border-amber-500/60 hover:bg-amber-500/10 text-amber-300 transition"
              >
                Step {step}
              </button>
            ))}
          </div>
        </div>
      </Panel>

      {/* Two upstream module inputs; Module 2 carries optional RF context. */}
      <form onSubmit={event => { event.preventDefault(); void handleEvaluate() }} className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-200">Manual Input Configuration</h2>
      <p className="text-xs text-gray-400">Enter Module 2 threat intelligence and Module 3 secure communication data. Optional RF measurements belong to the Module 2 input; no separate Module 1 input is required.</p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Module 2 includes observation metadata and optional RF measurements. */}
        <Panel title="AI THREAT INTELLIGENCE — Module 2">
          <div className="space-y-2 text-xs">
            <label className="block">
              <span className="text-gray-500">Observation ID</span>
              <input required value={request.rf_context.observation_id ?? ''} onChange={e => updateRF('observation_id', e.target.value)}
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-cyber-bg border border-gray-700 text-cyan-300 outline-none" />
            </label>
            <details>
              <summary className="cursor-pointer py-2 text-gray-300">Optional RF context supplied with Module 2</summary>
            {([
              ['rssi', 'RSSI (dBm)'],
              ['snr', 'SNR (dB)'],
              ['noise_floor', 'Noise Floor (dBm)'],
              ['packet_rate', 'Packet Rate (pkt/s)'],
              ['frequency_mhz', 'Frequency (MHz)'],
              ['bandwidth_mhz', 'Bandwidth (MHz)'],
              ['packet_loss_pct', 'Packet Loss (%)'],
              ['latency_ms', 'Latency (ms)'],
            ] as const).map(([field, label]) => (
              <label key={field} className="block">
                <span className="text-gray-500">{label}</span>
                <input
                  type="number"
                  step="any"
                  min={['packet_rate', 'packet_loss_pct', 'latency_ms'].includes(field) ? 0 : ['frequency_mhz', 'bandwidth_mhz'].includes(field) ? 0.000001 : undefined}
                  max={field === 'packet_loss_pct' ? 100 : undefined}
                  value={request.rf_context[field] ?? ''}
                  onChange={e => updateRF(field, e.target.value === '' ? undefined : e.target.valueAsNumber)}
                  className="mt-0.5 w-full px-2 py-1.5 rounded bg-cyber-bg border border-gray-700 text-gray-200 focus:border-cyan-500/50 outline-none"
                />
              </label>
            ))}
            <p className="text-[10px] text-gray-500 pt-2">Enter measured values from Module 2 RF context only when available. These are supporting evidence; risk weights use the Module 2 and Module 3 states.</p>
            </details>
            <label className="block">
              <span className="text-gray-500">Reported Threat Confidence (0–1, optional)</span>
              <input type="number" min="0" max="1" step="any" value={request.threat_intelligence.threat_confidence ?? ''}
                onChange={e => updateTI('threat_confidence', e.target.value === '' ? null : e.target.valueAsNumber)}
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-cyber-bg border border-gray-700 text-gray-200 outline-none" />
              <span className="block mt-1 text-[10px] text-gray-500">Recorded as upstream evidence; it does not change the configured risk weights or decision confidence rules.</span>
            </label>
            <label className="block">
              <span className="text-gray-500">Classification</span>
              <select
                value={request.threat_intelligence.classification}
                onChange={e => updateTI('classification', e.target.value)}
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-cyber-bg border border-gray-700 text-gray-200 outline-none"
              >
                <option>Normal</option>
                <option>Jamming</option>
                <option>Unknown Anomaly</option>
              </select>
            </label>
            <label className="block">
              <span className="text-gray-500">Severity</span>
              <select
                value={request.threat_intelligence.severity ?? ''}
                onChange={e => updateTI('severity', e.target.value || null)}
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-cyber-bg border border-gray-700 text-gray-200 outline-none"
              >
                <option value="">None</option>
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
              </select>
            </label>
            <label className="block">
              <span className="text-gray-500">Triggered Rule (e.g. J01)</span>
              <input
                type="text"
                value={request.threat_intelligence.triggered_rule ?? ''}
                onChange={e => updateTI('triggered_rule', e.target.value || null)}
                placeholder="None"
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-cyber-bg border border-gray-700 text-gray-200 outline-none"
              />
            </label>
            <div>
              <span className="text-gray-500">Evidence</span>
              {(request.threat_intelligence.evidence ?? []).map((ev, i) => (
                <div key={i} className="mt-1 px-2 py-1 rounded bg-gray-800/60 text-gray-300 text-[11px]">• {ev}</div>
              ))}
            </div>
          </div>
        </Panel>

        {/* Module 3: Secure Communication */}
        <Panel title="SECURE COMMUNICATION — Module 3">
          <div className="space-y-2 text-xs">
            <label className="block">
              <span className="text-gray-500">Observation ID</span>
              <input readOnly value={request.rf_context.observation_id ?? ''}
                aria-describedby="module3-observation-help"
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-cyber-bg border border-gray-700 text-cyan-300 outline-none" />
              <span id="module3-observation-help" className="block mt-1 text-[10px] text-gray-500">Automatically matches the Module 2 observation ID.</span>
            </label>
            {([
              ['link_state', 'Link State', ['TRUSTED', 'DEGRADED', 'SUSPICIOUS', 'UNTRUSTED']],
              ['freshness_state', 'Freshness', ['FRESH', 'STALE', 'REPLAY']],
              ['auth_state', 'Auth State', ['VALID', 'SUSPICIOUS', 'INVALID']],
              ['integrity_state', 'Integrity', ['VALID', 'SUSPICIOUS', 'INVALID']],
              ['comm_decision', 'Comm Decision', ['MAINTAIN', 'SWITCH', 'BACKUP', 'SECURE_HOLD']],
            ] as const).map(([field, label, options]) => (
              <label key={field} className="block">
                <span className="text-gray-500">{label}</span>
                <select
                  value={(request.secure_communication as unknown as Record<string, unknown>)[field] as string ?? ''}
                  onChange={e => updateSC(field, e.target.value || null)}
                  className="mt-0.5 w-full px-2 py-1.5 rounded bg-cyber-bg border border-gray-700 text-gray-200 outline-none"
                >
                  {options.map(o => <option key={o}>{o}</option>)}
                </select>
              </label>
            ))}
            <label className="flex items-center gap-2 mt-1">
              <input
                type="checkbox"
                checked={request.secure_communication.replay_detected}
                onChange={e => updateSC('replay_detected', e.target.checked)}
                className="accent-cyan-400"
              />
              <span className="text-gray-300">Replay Detected</span>
            </label>
            <div>
              <span className="text-gray-500">Link Evidence</span>
              {(request.secure_communication.link_evidence ?? []).map((ev, i) => (
                <div key={i} className="mt-1 px-2 py-1 rounded bg-gray-800/60 text-gray-300 text-[11px]">• {ev}</div>
              ))}
            </div>
          </div>
        </Panel>
      </div>

      {/* Evaluate + Reset buttons */}
      <div className="flex gap-4 justify-center">
        <button
          type="submit"
          disabled={loading}
          className="flex items-center gap-2 px-10 py-3 rounded-xl bg-cyan-500 text-black font-bold hover:bg-cyan-400 transition disabled:opacity-50"
        >
          <Zap className="w-5 h-5" />
          {loading ? 'Running Pipeline...' : 'Run Defense Evaluation'}
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="flex items-center gap-2 px-6 py-3 rounded-xl border border-gray-700 text-gray-400 hover:text-gray-200 text-sm"
        >
          <RefreshCw className="w-4 h-4" /> Reset Inputs
        </button>
      </div>
      </form>
      {evaluationError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{evaluationError}</p>}
      <p className="text-center text-xs text-amber-400 flex items-center justify-center gap-1">
        <AlertCircle className="w-3 h-3" />
        RECOMMENDATION ONLY — NO ACTION EXECUTED
      </p>

      {/* ── Results ── */}
      </>)}
      {result && (
        <div className="space-y-6">

          {/* ── Three source + correlation panels ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* RF Context Summary */}
            <Panel title="NORMALIZED EVIDENCE — RF Context Supplied with Module 2">
              {([
                ['observation_id', 'Observation ID', ''],
                ['timestamp', 'Observation Timestamp', ''],
                ['rssi', 'RSSI', ' dBm'],
                ['snr', 'SNR', ' dB'],
                ['noise_floor', 'Noise Floor', ' dBm'],
                ['packet_rate', 'Packet Rate', ' packets/s'],
                ['frequency_mhz', 'Frequency', ' MHz'],
                ['bandwidth_mhz', 'Bandwidth', ' MHz'],
                ['packet_loss_pct', 'Packet Loss', '%'],
                ['latency_ms', 'Latency', ' ms'],
                ['interference_level', 'Interference Level', ''],
                ['channel_condition', 'Channel Condition', ''],
                ['distance_m', 'Distance', ' m'],
              ]).filter(([key]) => result.module1_context[key] != null && result.module1_context[key] !== '').map(([key, label, unit]) => (
                <StatRow key={key} label={label} value={
                  String(result.module1_context[key]) + unit
                } />
              ))}
            </Panel>

            {/* Threat Intelligence Summary */}
            <Panel title="NORMALIZED EVIDENCE — Module 2 Threat Intelligence">
              <StatRow label="Classification" value={result.correlation.module2_classification} highlight />
              {typeof result.module2_context.threat_confidence === 'number' && (
                <StatRow label="Reported Threat Confidence" value={`${(result.module2_context.threat_confidence * 100).toFixed(1)}% (evidence only)`} />
              )}
              <StatRow label="Severity" value={
                result.correlation.module2_severity
                  ? <SeverityBadge severity={result.correlation.module2_severity} />
                  : <span className="text-gray-500">None</span>
              } />
              <StatRow label="Triggered Rule" value={(result.module2_context.triggered_rule as string) || 'None'} highlight />
              <StatRow label="Abnormal Features" value={(result.module2_context.abnormal_features as string[] | undefined)?.join(', ') || 'None reported'} />
              <p className="text-xs text-gray-400 mt-3 mb-1">Statistical Deviation</p>
              {(['rssi', 'snr', 'noise_floor', 'packet_rate']).map(key => (
                <StatRow key={key} label={key.replace(/_/g, ' ')} value={
                  (result.module2_context.statistical_deviation as Record<string, number | null> | null)?.[key] ?? 'Not supplied'
                } />
              ))}
              <p className="text-xs text-gray-400 mt-3">Threat Evidence</p>
              <div className="mt-2">
                {((result.module2_context.evidence as string[]) || []).filter(ev => !/^Synthetic test:/i.test(ev.trim())).map((ev: string, i: number) => (
                  <p key={i} className="text-[11px] text-gray-400 mt-1">• {ev}</p>
                ))}
              </div>
            </Panel>

            {/* Secure Communication Summary */}
            <Panel title="NORMALIZED EVIDENCE — Module 3 Secure Communication">
              <StatRow label="Link State" value={result.correlation.module3_link_state} highlight />
              <StatRow label="Freshness" value={result.module3_context.freshness_state as string} />
              <StatRow label="Auth State" value={result.module3_context.auth_state as string} />
              <StatRow label="Integrity" value={result.module3_context.integrity_state as string} />
              <StatRow label="Replay Detected" value={
                result.correlation.module3_replay
                  ? <span className="text-red-400 font-bold">YES — REPLAY ATTACK</span>
                  : <span className="text-emerald-400">No</span>
              } />
              <StatRow label="Comm Decision" value={(result.module3_context.comm_decision as string) || 'Not supplied'} />
              <div className="mt-2">
                {((result.module3_context.link_evidence as string[]) || []).filter(ev => !ev.includes('[MOCK]') && !/^Synthetic communication state for /i.test(ev.trim())).map((ev: string, i: number) => (
                  <p key={i} className="text-[11px] text-gray-400 mt-1">• {ev}</p>
                ))}
              </div>
            </Panel>
          </div>

            <Panel title="MULTI-SOURCE EVIDENCE CORRELATION">
              <p className="text-[11px] text-gray-400 mb-3">{result.correlation.correlation_note}</p>
              {result.correlation.source_contributions.map(src => (
                <div key={src.source} className="mb-3">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-300">{src.source.replace(/_/g, ' ')}</span>
                    <span className="text-cyan-400">Evidence points: {src.normalized_score.toFixed(0)}</span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${src.normalized_score}%` }} />
                  </div>
                  <ul className="mt-1">
                    {src.evidence.filter(ev => !/^Synthetic (test:|communication state for )/i.test(ev.trim())).slice(0, 3).map((ev, i) => (
                      <li key={i} className="text-[10px] text-gray-500">• {ev}</li>
                    ))}
                  </ul>
                </div>
              ))}
              {result.correlation.correlated_risk_boost > 0 && (
                <div className="mt-2 p-2 rounded bg-cyan-500/10 border border-cyan-500/20">
                  <p className="text-[11px] text-cyan-400">Evidence alignment indicator: {result.correlation.correlated_risk_boost}. Shown as correlation context; the risk score uses the breakdown below.</p>
                </div>
              )}
              <div className="mt-4 rounded-lg border border-gray-700 bg-cyber-surface p-4">
                <h4 className="text-sm font-semibold text-gray-200">How your risk-scoring rules are defined</h4>
                <p className="mt-2 text-sm font-mono text-cyan-400">Risk = min(100, C + S + L + F + A + I)</p>
                <p className="mt-2 text-xs text-gray-400">Each input state contributes configured points. Add the six contributions and cap the total at 100.</p>
                <ul className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-gray-300">
                  <li>C = Threat classification: {result.risk_breakdown.classification_points} points</li>
                  <li>S = Threat severity: {result.risk_breakdown.severity_points} points</li>
                  <li>L = Communication link state: {result.risk_breakdown.link_state_points} points</li>
                  <li>F = Message freshness: {result.risk_breakdown.freshness_points} points</li>
                  <li>A = Authentication status: {result.risk_breakdown.auth_points} points</li>
                  <li>I = Integrity status: {result.risk_breakdown.integrity_points} points</li>
                </ul>
                <p className="mt-3 text-xs text-cyan-400">
                  Current calculation: min(100, {result.risk_breakdown.classification_points} + {result.risk_breakdown.severity_points} + {result.risk_breakdown.link_state_points} + {result.risk_breakdown.freshness_points} + {result.risk_breakdown.auth_points} + {result.risk_breakdown.integrity_points}) = {result.risk_score}
                </p>
              </div>
              <p className="text-[9px] text-gray-600 mt-2">Research contribution: multi-source correlation detects cases a single-source engine would miss</p>
            </Panel>

          {/* ── Main Decision Cards ── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Risk Score */}
            <div className={`rounded-xl border p-4 flex flex-col items-center ${riskBg(result.risk_level)}`}>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Overall Risk Score</p>
              <RiskGauge score={result.risk_score} level={result.risk_level} />
            </div>

            {/* Confidence */}
            <div className="rounded-xl border border-gray-800 bg-cyber-panel p-4 flex flex-col items-center justify-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Decision Confidence</p>
              <p className={`text-2xl font-bold ${confidenceColor(result.decision_confidence)}`}>
                {result.decision_confidence}
              </p>
              <p className="text-xs text-gray-400 text-center mt-2 leading-relaxed">
                {result.confidence_rationale}
              </p>
            </div>

            {/* Conflict */}
            <div className={`rounded-xl border p-4 flex flex-col items-center justify-center ${result.evidence_conflict ? 'border-amber-500/40 bg-amber-500/10' : 'border-gray-800 bg-cyber-panel'}`}>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Evidence Conflict</p>
              {result.evidence_conflict
                ? <AlertTriangle className="w-6 h-6 text-amber-400" />
                : <CheckCircle2 className="w-6 h-6 text-emerald-400" />}
              <p className={`text-sm font-bold mt-1 ${result.evidence_conflict ? 'text-amber-400' : 'text-emerald-400'}`}>
                {result.evidence_conflict ? 'YES' : 'NO'}
              </p>
              {result.evidence_conflict && (
                <p className="text-xs text-amber-300 text-center mt-2 leading-relaxed">
                  {result.conflict_reason}
                </p>
              )}
            </div>
          </div>

            <Panel title="DYNAMIC RISK SCORE BREAKDOWN">
              <div className="space-y-2">
                {result.risk_breakdown.components.map(c => (
                  <div key={c.source} className="flex justify-between items-center text-xs">
                    <div>
                      <span className="text-gray-300">{c.label}</span>
                      <p className="text-[9px] text-gray-600">{c.source}</p>
                    </div>
                    <span className="text-red-400 font-mono font-bold">+{c.points}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 pt-3 border-t border-gray-800 flex justify-between items-center">
                <span className="text-sm text-gray-400">Total (capped at 100)</span>
                <span className={`text-xl font-bold ${riskColor(result.risk_level)}`}>
                  {result.risk_score}/100
                </span>
              </div>
              <p className="text-[9px] text-gray-600 mt-2">
                Weights: initial prototype values — pending experimental calibration
              </p>
            </Panel>

          {/* ── Recommended Response ── */}
          <div className={`rounded-xl border p-6 text-center ${responseBg(result.recommended_response)}`}>
            <p className="text-[10px] uppercase tracking-widest mb-1 opacity-70">RECOMMENDED RESPONSE</p>
            <p className="text-3xl font-black tracking-tight">
              {result.recommended_response.replace(/_/g, ' ')}
            </p>
            <p className="text-sm opacity-70 mt-1">Response Status: {result.response_status}</p>
            <p className="text-[11px] opacity-60 mt-2 max-w-xl mx-auto">{result.response_rationale}</p>
          </div>

          {/* ── Explainability Panel ── */}
          <Panel title="WHY THIS DECISION? — Explainable Decision Engine">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-xs text-gray-500 mb-3">Decision Summary</p>
                <StatRow label="Incident ID" value={result.incident_id} />
                <StatRow label="Risk Score" value={`${result.risk_score}/100`} />
                <StatRow label="Risk Level" value={<SeverityBadge severity={result.risk_level} />} />
                <StatRow label="Confidence" value={result.decision_confidence} />
                <StatRow label="Conflict" value={result.evidence_conflict ? 'YES' : 'No'} />
                <StatRow label="Response" value={result.recommended_response.replace(/_/g, ' ')} highlight />
                <div className="mt-4 p-3 rounded bg-gray-800/50 border border-gray-700">
                  <p className="text-[10px] text-gray-500 mb-1">BASELINE COMPARISON</p>
                  <p className="text-xs text-gray-300">Baseline (no context): <strong>{result.baseline_response.replace(/_/g, ' ')}</strong></p>
                  <p className="text-xs text-gray-300">Proposed (Module 4): <strong>{result.recommended_response.replace(/_/g, ' ')}</strong></p>
                  <p className={`text-[11px] mt-1 ${result.baseline_vs_proposed !== 'SAME' ? 'text-cyan-400' : 'text-gray-500'}`}>
                    {result.baseline_vs_proposed.replace(/_/g, ' ')}
                  </p>
                </div>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-3">Ordered Reasoning Chain</p>
                <ul className="space-y-2 max-h-80 overflow-y-auto">
                  {result.reasons.map((r, i) => (
                    <li key={i} className={`flex items-start gap-2 text-xs ${r.startsWith('⚠') ? 'text-amber-300' : 'text-gray-300'}`}>
                      {r.startsWith('⚠')
                        ? <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />
                        : <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />}
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Panel>

          {/* ── Pipeline Stages Audit ── */}
          <Panel title="PIPELINE EXECUTION STAGES — Audit Trail">
            <div className="flex flex-wrap gap-2">
              {result.pipeline_stages.map((stage, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                    <CheckCircle2 className="w-3 h-3 text-cyan-400" />
                    <span className="text-[10px] text-cyan-300">{stage}</span>
                  </div>
                  {i < result.pipeline_stages.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-gray-700" />
                  )}
                </div>
              ))}
            </div>
            <p className="text-[9px] text-gray-600 mt-3">
              Incident {result.incident_id} logged to SQLite at {result.timestamp}
            </p>
          </Panel>
        </div>
      )}

      {/* ── Risk History Chart ── */}
      {historyError && <p role="alert" className="text-sm text-red-300">{historyError}</p>}
      {history.length > 0 && (
        <Panel title="RISK SCORE HISTORY — SQLite Audit Log">
          <HistoryChart history={history as { incident_id: string; risk_score: number; risk_level: string }[]} />
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-1 px-2">Incident</th>
                  <th className="text-left py-1 px-2">Observation ID</th>
                  <th className="text-left py-1 px-2">Date</th>
                  <th className="text-left py-1 px-2">Time</th>
                  <th className="text-left py-1 px-2">Risk</th>
                  <th className="text-left py-1 px-2">Level</th>
                  <th className="text-left py-1 px-2">Classification</th>
                  <th className="text-left py-1 px-2">Response</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-1 px-2 text-cyan-400 font-mono">{h.incident_id as string}</td>
                    <td className="py-1 px-2 font-mono">{String(h.observation_id ?? '')}</td>
                    <td className="py-1 px-2 text-gray-400">{String(h.timestamp).slice(0, 10)}</td>
                    <td className="py-1 px-2 text-gray-400">{String(h.timestamp).slice(11, 19)}</td>
                    <td className="py-1 px-2 font-mono">{h.risk_score as number}</td>
                    <td className="py-1 px-2"><SeverityBadge severity={h.risk_level as string} /></td>
                    <td className="py-1 px-2">{h.classification as string}</td>
                    <td className="py-1 px-2 max-w-[150px] truncate">{String(h.recommended_response ?? '').replace(/_/g, ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Pipeline visualization follows the risk history section. */}
      <PipelineViz active={!!result} />

      {!result && (
        <Panel title="MODULE 4 — DECISION PIPELINE">
          <p className="text-sm text-gray-500 text-center py-12">
            {mode === 'testing' ? 'Select a preset scenario or configure inputs manually, then click ' : 'Upload Module 2 and Module 3 JSON files above, then click '}
            <strong className="text-gray-300">{mode === 'testing' ? 'Run Defense Evaluation' : 'RUN FILE INTEGRATION'}</strong>
          </p>
        </Panel>
      )}
    </div>
  )
}
