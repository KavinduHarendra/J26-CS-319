import { useState, useCallback, useEffect } from 'react'
import {
  Shield, AlertTriangle, CheckCircle2, TrendingUp, TrendingDown,
  Minus, AlertCircle, RefreshCw, Zap, Activity, Radio, Lock,
  ArrowRight, ChevronRight, BarChart3,
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { evaluateThreat, evaluateFiles, fetchEvaluateScenarios, fetchEvaluateScenario, fetchEscalationStep, fetchRiskHistory, resetEvaluate } from '../api'
import type { EvaluateRequest, EvaluateResponse, EvaluateScenario } from '../types'
import { Panel, StatRow } from '../components/Panel'
import SeverityBadge from '../components/SeverityBadge'

// ─── Default request payload ──────────────────────────────────────────────────

const DEFAULT_REQUEST: EvaluateRequest = {
  rf_context: {
    observation_id: 'OBS-DEMO-001',
    timestamp: new Date().toISOString(),
    rssi: -62.0, snr: 33.0, noise_floor: -95.0, packet_rate: 99.0,
    frequency_mhz: 2400.0,
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

function trendIcon(trend: string) {
  if (trend === 'ESCALATING') return <TrendingUp className="w-5 h-5 text-red-400" />
  if (trend === 'IMPROVING') return <TrendingDown className="w-5 h-5 text-emerald-400" />
  if (trend === 'STABLE') return <Minus className="w-5 h-5 text-yellow-400" />
  return <AlertCircle className="w-5 h-5 text-gray-500" />
}

function confidenceColor(c: string) {
  return c === 'HIGH' ? 'text-emerald-400' : c === 'LOW' ? 'text-red-400' : 'text-yellow-400'
}

// ─── Pipeline Visualization ──────────────────────────────────────────────────

function PipelineViz({ active }: { active: boolean }) {
  const stages = [
    { label: 'MODULE 1\nRF Evidence', color: 'text-cyan-400 border-cyan-500/40 bg-cyan-500/10', icon: Radio },
    { label: 'MODULE 2\nThreat Intel', color: 'text-purple-400 border-purple-500/40 bg-purple-500/10', icon: Shield },
    { label: 'MODULE 3\nComm Trust', color: 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10', icon: Lock },
  ]
  return (
    <div className="bg-[#0d1321] border border-gray-800 rounded-xl p-4">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Decision Pipeline — Multi-Source Correlation</p>
      <div className="flex items-center gap-2 flex-wrap">
        {stages.map(({ label, color, icon: Icon }) => (
          <div key={label} className={`flex flex-col items-center px-3 py-2 rounded-lg border text-center text-[10px] font-semibold ${color}`}>
            <Icon className="w-4 h-4 mb-1" />
            {label.split('\n').map((l, i) => <span key={i}>{l}</span>)}
          </div>
        ))}
        <ChevronRight className="w-4 h-4 text-gray-600" />
        <div className={`flex flex-col items-center px-3 py-2 rounded-lg border text-center text-[10px] font-semibold ${active ? 'text-amber-400 border-amber-500/40 bg-amber-500/10 animate-pulse' : 'text-gray-500 border-gray-700'}`}>
          <Activity className="w-4 h-4 mb-1" />
          MULTI-SOURCE{'\n'}CORRELATION
        </div>
        <ChevronRight className="w-4 h-4 text-gray-600" />
        <div className={`flex flex-col items-center px-3 py-2 rounded-lg border text-center text-[10px] font-semibold ${active ? 'text-red-400 border-red-500/40 bg-red-500/10' : 'text-gray-500 border-gray-700'}`}>
          <BarChart3 className="w-4 h-4 mb-1" />
          RISK{'\n'}SCORE
        </div>
        <ChevronRight className="w-4 h-4 text-gray-600" />
        <div className={`flex flex-col items-center px-3 py-2 rounded-lg border text-center text-[10px] font-semibold ${active ? 'text-purple-400 border-purple-500/40 bg-purple-500/10' : 'text-gray-500 border-gray-700'}`}>
          <TrendingUp className="w-4 h-4 mb-1" />
          TREND{'\n'}ANALYSIS
        </div>
        <ChevronRight className="w-4 h-4 text-gray-600" />
        <div className={`flex flex-col items-center px-4 py-2 rounded-lg border text-center text-[10px] font-bold ${active ? 'text-cyan-300 border-cyan-500/60 bg-cyan-500/15' : 'text-gray-500 border-gray-700'}`}>
          <Zap className="w-4 h-4 mb-1" />
          DEFENSE{'\n'}RESPONSE
        </div>
      </div>
    </div>
  )
}

// ─── Module Status Bar ────────────────────────────────────────────────────────

function ModuleStatusBar({ result }: { result: EvaluateResponse | null }) {
  const modules = [
    { label: 'MODULE 1 — SDR RF DETECTION', owner: 'W.H.M.S.R. Bandara', color: 'text-cyan-400', icon: Radio },
    { label: 'MODULE 2 — AI THREAT INTEL', owner: 'N.K.B.H. Rathnayake', color: 'text-purple-400', icon: Shield },
    { label: 'MODULE 3 — SECURE COMMS', owner: 'U.L.K.H. Liyanage', color: 'text-emerald-400', icon: Lock },
    { label: 'MODULE 4 — DEFENSE ENGINE', owner: 'T.H. Ranasinghe', color: 'text-amber-400', icon: Activity },
  ]
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {modules.map(({ label, owner, color, icon: Icon }) => (
        <div key={label} className="bg-[#111827] border border-gray-800 rounded-xl p-3 flex items-start gap-2">
          <Icon className={`w-4 h-4 shrink-0 mt-0.5 ${color}`} />
          <div>
            <p className={`text-[10px] font-semibold ${color}`}>{label}</p>
            <p className="text-[9px] text-gray-600">{owner}</p>
            <p className="text-[9px] text-gray-500 mt-0.5">
              {result ? '● MOCK INPUT RECEIVED' : '○ SIMULATION / MOCK MODE'}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Risk Score Gauge ─────────────────────────────────────────────────────────

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

// ─── Trend History Chart ──────────────────────────────────────────────────────

function TrendChart({ scores }: { scores: number[] }) {
  const data = scores.map((s, i) => ({ obs: `Obs ${i + 1}`, risk: s }))
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="obs" stroke="#6b7280" fontSize={10} />
          <YAxis domain={[0, 100]} stroke="#6b7280" fontSize={10} />
          <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }} />
          <ReferenceLine y={75} stroke="#ef4444" strokeDasharray="4 4" />
          <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="risk" stroke="#06b6d4" strokeWidth={2} dot={{ r: 4 }} name="Risk Score" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── History Chart (from API) ─────────────────────────────────────────────────

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

export default function Evaluate() {
  const [request, setRequest] = useState<EvaluateRequest>(DEFAULT_REQUEST)
  const [result, setResult] = useState<EvaluateResponse | null>(null)
  const [scenarios, setScenarios] = useState<EvaluateScenario[]>([])
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<Record<string, unknown>[]>([])
  const [module2File, setModule2File] = useState<File | null>(null)
  const [module3File, setModule3File] = useState<File | null>(null)
  const [integrationError, setIntegrationError] = useState<string | null>(null)

  const loadScenarios = useCallback(async () => {
    try {
      const data = await fetchEvaluateScenarios()
      setScenarios(data.scenarios)
    } catch { /* backend may not be running */ }
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const data = await fetchRiskHistory()
      setHistory(data.history)
    } catch { /* ok */ }
  }, [])

  useEffect(() => {
    loadScenarios()
    loadHistory()
  }, [loadScenarios, loadHistory])

  const handleEvaluate = async () => {
    setLoading(true)
    try {
      const res = await evaluateThreat(request)
      setResult(res)
      loadHistory()
    } catch (e) {
      console.error('Evaluate failed', e)
    } finally {
      setLoading(false)
    }
  }

  const handleFileEvaluate = async () => {
    if (!module2File || !module3File) {
      setIntegrationError('Select both Module 2 and Module 3 JSON files.')
      return
    }
    setLoading(true)
    setIntegrationError(null)
    try {
      const res = await evaluateFiles(module2File, module3File)
      if (res.integration_status === 'FAILED') {
        setIntegrationError(`${res.error_code ?? 'INTEGRATION_ERROR'}: ${res.message ?? 'Validation failed.'}`)
        setResult(null)
      } else {
        setResult(res)
        loadHistory()
      }
    } catch (e) {
      setIntegrationError(e instanceof Error ? e.message : 'File integration failed.')
    } finally {
      setLoading(false)
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
    try {
      const data = await fetchEvaluateScenario(id)
      setRequest(data.payload)
      setResult(null)
    } catch { /* ok */ }
  }

  const loadEscalationStep = async (step: number) => {
    try {
      const data = await fetchEscalationStep(step)
      setRequest(data.payload)
      setResult(null)
    } catch { /* ok */ }
  }

  const handleReset = async () => {
    try { await resetEvaluate() } catch { /* ok */ }
    setResult(null)
    setHistory([])
    setRequest(DEFAULT_REQUEST)
  }

  const updateTI = (field: string, value: unknown) => {
    setRequest(prev => ({
      ...prev,
      threat_intelligence: { ...prev.threat_intelligence, [field]: value },
    }))
    setResult(null)
  }

  const updateSC = (field: string, value: unknown) => {
    setRequest(prev => ({
      ...prev,
      secure_communication: { ...prev.secure_communication, [field]: value },
    }))
    setResult(null)
  }

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <header>
        <h1 className="text-2xl font-bold text-white">
          Autonomous Cyber Defense &amp; Response Engine
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Explainable RF-Aware Risk Assessment and Response Prioritization for UAV Cyber Defense
          {' '}·{' '}
          <span className="text-amber-400 font-medium">Module 4 — T. H. Ranasinghe · J26-CS-319</span>
        </p>
      </header>

      {/* ── Module Status Bar ── */}
      <ModuleStatusBar result={result} />

      {/* ── Pipeline Visualization ── */}
      <PipelineViz active={!!result} />

      <Panel title="FILE-BASED INTEGRATION — Module 2 + Module 3 JSON">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <label className="text-xs text-gray-400">
            <span className="block mb-1">Module 2 threat intelligence</span>
            <input type="file" accept=".json,application/json" onChange={e => setModule2File(e.target.files?.[0] ?? null)}
              className="w-full text-xs text-gray-300 file:mr-2 file:rounded file:border-0 file:bg-purple-500/20 file:px-2 file:py-1 file:text-purple-300" />
          </label>
          <label className="text-xs text-gray-400">
            <span className="block mb-1">Module 3 secure communication</span>
            <input type="file" accept=".json,application/json" onChange={e => setModule3File(e.target.files?.[0] ?? null)}
              className="w-full text-xs text-gray-300 file:mr-2 file:rounded file:border-0 file:bg-emerald-500/20 file:px-2 file:py-1 file:text-emerald-300" />
          </label>
          <button onClick={handleFileEvaluate} disabled={loading}
            className="px-4 py-2 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 text-xs font-semibold hover:bg-cyan-500/30 disabled:opacity-50">
            {loading ? 'PROCESSING...' : 'RUN FILE INTEGRATION'}
          </button>
        </div>
        <p className="text-[10px] text-gray-600 mt-3">Files are validated independently, matched by observation ID (or timestamp fallback), then passed through the same HCRDM pipeline and audit log.</p>
        {integrationError && <p className="text-xs text-red-300 mt-2">{integrationError}</p>}
        {result?.integration_status === 'SUCCESS' && (
          <div className="flex items-center gap-3 mt-2">
            <p className="text-xs text-emerald-300">File integration succeeded using {result.match_method} matching.</p>
            <button onClick={downloadResult} className="text-xs text-cyan-300 underline hover:text-cyan-200">Download decision JSON</button>
          </div>
        )}
      </Panel>

      {/* ── Scenario Selector ── */}
      <Panel title="PP1 DEMO SCENARIOS — Select to Load">
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

      {/* ── Three Input Panels + Evaluate Button ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Panel 1: RF Context */}
        <Panel title="SDR RF CONTEXT — Module 1 (Mock Input)">
          <div className="space-y-2 text-xs">
            <p className="text-[10px] text-cyan-400 font-semibold mb-2">OBSERVATION: {request.rf_context.observation_id}</p>
            {([
              ['rssi', 'RSSI (dBm)'],
              ['snr', 'SNR (dB)'],
              ['noise_floor', 'Noise Floor (dBm)'],
              ['packet_rate', 'Packet Rate (pkt/s)'],
              ['frequency_mhz', 'Frequency (MHz)'],
            ] as const).map(([field, label]) => (
              <label key={field} className="block">
                <span className="text-gray-500">{label}</span>
                <input
                  type="number"
                  value={request.rf_context[field] ?? ''}
                  onChange={e => setRequest(prev => ({
                    ...prev,
                    rf_context: { ...prev.rf_context, [field]: parseFloat(e.target.value) || 0 },
                  }))}
                  className="mt-0.5 w-full px-2 py-1.5 rounded bg-[#0a0e17] border border-gray-700 text-gray-200 focus:border-cyan-500/50 outline-none"
                />
              </label>
            ))}
            <p className="text-[9px] text-gray-600 mt-2">Module 1 Owner: W.H.M.S.R. Bandara — Mock Adapter Active</p>
          </div>
        </Panel>

        {/* Panel 2: Threat Intelligence */}
        <Panel title="AI THREAT INTELLIGENCE — Module 2 (Mock Input)">
          <div className="space-y-2 text-xs">
            <label className="block">
              <span className="text-gray-500">Classification</span>
              <select
                value={request.threat_intelligence.classification}
                onChange={e => updateTI('classification', e.target.value)}
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-[#0a0e17] border border-gray-700 text-gray-200 outline-none"
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
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-[#0a0e17] border border-gray-700 text-gray-200 outline-none"
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
                className="mt-0.5 w-full px-2 py-1.5 rounded bg-[#0a0e17] border border-gray-700 text-gray-200 outline-none"
              />
            </label>
            <div>
              <span className="text-gray-500">Evidence</span>
              {(request.threat_intelligence.evidence ?? []).map((ev, i) => (
                <div key={i} className="mt-1 px-2 py-1 rounded bg-gray-800/60 text-gray-300 text-[11px]">• {ev}</div>
              ))}
            </div>
            <p className="text-[9px] text-gray-600 mt-1">Module 2 Owner: N.K.B.H. Rathnayake — Mock Adapter Active</p>
          </div>
        </Panel>

        {/* Panel 3: Secure Communication */}
        <Panel title="SECURE COMMUNICATION — Module 3 (Mock Input)">
          <div className="space-y-2 text-xs">
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
                  className="mt-0.5 w-full px-2 py-1.5 rounded bg-[#0a0e17] border border-gray-700 text-gray-200 outline-none"
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
            <p className="text-[9px] text-gray-600 mt-1">Module 3 Owner: U.L.K.H. Liyanage — Mock Adapter Active</p>
          </div>
        </Panel>
      </div>

      {/* Evaluate + Reset buttons */}
      <div className="flex gap-4 justify-center">
        <button
          onClick={handleEvaluate}
          disabled={loading}
          className="flex items-center gap-2 px-10 py-3 rounded-xl bg-cyan-500 text-black font-bold hover:bg-cyan-400 transition disabled:opacity-50"
        >
          <Zap className="w-5 h-5" />
          {loading ? 'Running Pipeline...' : 'EVALUATE — Run Module 4 Pipeline'}
        </button>
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-6 py-3 rounded-xl border border-gray-700 text-gray-400 hover:text-gray-200 text-sm"
        >
          <RefreshCw className="w-4 h-4" /> Reset
        </button>
      </div>
      <p className="text-center text-xs text-amber-400 flex items-center justify-center gap-1">
        <AlertCircle className="w-3 h-3" />
        SIMULATED RESPONSE — NO REAL UAV CONTROL
      </p>

      {/* ── Results ── */}
      {result && (
        <div className="space-y-6">

          {/* ── Main Decision Cards ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Risk Score */}
            <div className={`col-span-2 md:col-span-1 rounded-xl border p-4 flex flex-col items-center ${riskBg(result.risk_level)}`}>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Overall Risk Score</p>
              <RiskGauge score={result.risk_score} level={result.risk_level} />
            </div>

            {/* Trend */}
            <div className="rounded-xl border border-gray-800 bg-[#111827] p-4 flex flex-col items-center justify-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Trend</p>
              {trendIcon(result.trend)}
              <p className={`text-sm font-bold mt-1 ${result.trend === 'ESCALATING' ? 'text-red-400' : result.trend === 'IMPROVING' ? 'text-emerald-400' : 'text-yellow-400'}`}>
                {result.trend}
              </p>
              <p className="text-[9px] text-gray-600 mt-1">slope: {result.trend_window.slope}</p>
            </div>

            {/* Confidence */}
            <div className="rounded-xl border border-gray-800 bg-[#111827] p-4 flex flex-col items-center justify-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Decision Confidence</p>
              <p className={`text-2xl font-bold ${confidenceColor(result.decision_confidence)}`}>
                {result.decision_confidence}
              </p>
              <p className="text-[9px] text-gray-600 text-center mt-1 max-w-[100px] leading-3">
                {result.confidence_rationale.slice(0, 60)}…
              </p>
            </div>

            {/* Conflict */}
            <div className={`rounded-xl border p-4 flex flex-col items-center justify-center ${result.evidence_conflict ? 'border-amber-500/40 bg-amber-500/10' : 'border-gray-800 bg-[#111827]'}`}>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Evidence Conflict</p>
              {result.evidence_conflict
                ? <AlertTriangle className="w-6 h-6 text-amber-400" />
                : <CheckCircle2 className="w-6 h-6 text-emerald-400" />}
              <p className={`text-sm font-bold mt-1 ${result.evidence_conflict ? 'text-amber-400' : 'text-emerald-400'}`}>
                {result.evidence_conflict ? 'YES' : 'NO'}
              </p>
              {result.evidence_conflict && (
                <p className="text-[9px] text-amber-300 text-center mt-1 max-w-[100px] leading-3">
                  {result.conflict_reason?.slice(0, 50)}…
                </p>
              )}
            </div>
          </div>

          {/* ── Recommended Response ── */}
          <div className={`rounded-xl border p-6 text-center ${responseBg(result.recommended_response)}`}>
            <p className="text-[10px] uppercase tracking-widest mb-1 opacity-70">RECOMMENDED RESPONSE</p>
            <p className="text-3xl font-black tracking-tight">
              {result.recommended_response.replace(/_/g, ' ')}
            </p>
            <p className="text-sm opacity-70 mt-1">Response Status: {result.response_status}</p>
            <p className="text-[11px] opacity-60 mt-2 max-w-xl mx-auto">{result.response_rationale}</p>
          </div>

          {/* ── Three source + correlation panels ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* RF Context Summary */}
            <Panel title="MODULE 1 — RF CONTEXT SUMMARY">
              <StatRow label="Observation ID" value={result.observation_id} />
              {Object.entries(result.module1_context).map(([k, v]) =>
                v != null && k !== 'observation_id' && k !== 'timestamp'
                  ? <StatRow key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
                  : null
              )}
            </Panel>

            {/* Threat Intelligence Summary */}
            <Panel title="MODULE 2 — THREAT INTELLIGENCE SUMMARY">
              <StatRow label="Classification" value={result.correlation.module2_classification} highlight />
              <StatRow label="Severity" value={
                result.correlation.module2_severity
                  ? <SeverityBadge severity={result.correlation.module2_severity} />
                  : <span className="text-gray-500">None</span>
              } />
              {(result.module2_context.triggered_rule as string) && (
                <StatRow label="Triggered Rule" value={result.module2_context.triggered_rule as string} highlight />
              )}
              <div className="mt-2">
                {((result.module2_context.evidence as string[]) || []).map((ev: string, i: number) => (
                  <p key={i} className="text-[11px] text-gray-400 mt-1">• {ev}</p>
                ))}
              </div>
            </Panel>

            {/* Secure Communication Summary */}
            <Panel title="MODULE 3 — SECURE COMMUNICATION SUMMARY">
              <StatRow label="Link State" value={result.correlation.module3_link_state} highlight />
              <StatRow label="Freshness" value={result.module3_context.freshness_state as string} />
              <StatRow label="Auth State" value={result.module3_context.auth_state as string} />
              <StatRow label="Integrity" value={result.module3_context.integrity_state as string} />
              <StatRow label="Replay Detected" value={
                result.correlation.module3_replay
                  ? <span className="text-red-400 font-bold">YES — REPLAY ATTACK</span>
                  : <span className="text-emerald-400">No</span>
              } />
              {(result.module3_context.comm_decision as string) && (
                <StatRow label="Comm Decision" value={result.module3_context.comm_decision as string} />
              )}
              <div className="mt-2">
                {((result.module3_context.link_evidence as string[]) || []).filter(ev => !ev.includes('[MOCK]')).map((ev: string, i: number) => (
                  <p key={i} className="text-[11px] text-gray-400 mt-1">• {ev}</p>
                ))}
              </div>
            </Panel>
          </div>

          {/* ── Multi-Source Correlation + Risk Breakdown ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Panel title="MULTI-SOURCE EVIDENCE CORRELATION">
              <p className="text-[11px] text-gray-400 mb-3">{result.correlation.correlation_note}</p>
              {result.correlation.source_contributions.map(src => (
                <div key={src.source} className="mb-3">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-300">{src.source.replace(/_/g, ' ')}</span>
                    <span className="text-cyan-400">{Math.round(src.weight * 100)}% weight · score {src.normalized_score.toFixed(0)}</span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${src.normalized_score}%` }} />
                  </div>
                  <ul className="mt-1">
                    {src.evidence.slice(0, 3).map((ev, i) => (
                      <li key={i} className="text-[10px] text-gray-500">• {ev}</li>
                    ))}
                  </ul>
                </div>
              ))}
              {result.correlation.correlated_risk_boost > 0 && (
                <div className="mt-2 p-2 rounded bg-cyan-500/10 border border-cyan-500/20">
                  <p className="text-[11px] text-cyan-400">+{result.correlation.correlated_risk_boost} cross-source correlation boost applied</p>
                </div>
              )}
              <p className="text-[9px] text-gray-600 mt-2">Research contribution: multi-source correlation detects cases a single-source engine would miss</p>
            </Panel>

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
          </div>

          {/* ── Trend + Conflict ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Panel title={`TREND ANALYSIS — ${result.trend}`}>
              {result.trend_window.scores.length >= 2
                ? <TrendChart scores={result.trend_window.scores} />
                : <p className="text-sm text-gray-500 text-center py-6">
                    {result.trend} — window has {result.trend_window.scores.length} observation(s).
                    Run more evaluations to populate trend.
                  </p>
              }
              <div className="mt-2 flex justify-between text-xs">
                <span className="text-gray-500">Window: {result.trend_window.scores.join(' → ')}</span>
                <span className="text-gray-500">Slope: {result.trend_window.slope}</span>
              </div>
              <p className="text-[9px] text-gray-600 mt-1">{result.trend_window.method}</p>
            </Panel>

            <Panel title="CONFLICT DETECTION & CONFIDENCE">
              <div className={`p-3 rounded-lg border mb-3 ${result.evidence_conflict ? 'bg-amber-500/10 border-amber-500/40' : 'bg-emerald-500/10 border-emerald-500/30'}`}>
                <p className={`text-xs font-semibold ${result.evidence_conflict ? 'text-amber-300' : 'text-emerald-300'}`}>
                  {result.evidence_conflict ? '⚠ EVIDENCE CONFLICT DETECTED' : '✓ No Evidence Conflict'}
                </p>
                {result.evidence_conflict && result.conflict_reason && (
                  <p className="text-[11px] text-gray-300 mt-1">{result.conflict_reason}</p>
                )}
              </div>
              <div className="p-3 rounded-lg bg-[#0a0e17] border border-gray-800">
                <p className="text-[10px] text-gray-500 mb-1">DECISION CONFIDENCE</p>
                <p className={`text-lg font-bold ${confidenceColor(result.decision_confidence)}`}>
                  {result.decision_confidence}
                </p>
                <p className="text-[11px] text-gray-400 mt-1">{result.confidence_rationale}</p>
              </div>
            </Panel>
          </div>

          {/* ── Explainability Panel ── */}
          <Panel title="WHY THIS DECISION? — Explainable Decision Engine">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-xs text-gray-500 mb-3">Decision Summary</p>
                <StatRow label="Incident ID" value={result.incident_id} />
                <StatRow label="Risk Score" value={`${result.risk_score}/100`} />
                <StatRow label="Risk Level" value={<SeverityBadge severity={result.risk_level} />} />
                <StatRow label="Trend" value={result.trend} />
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
      {history.length > 0 && (
        <Panel title="RISK SCORE HISTORY — SQLite Audit Log">
          <HistoryChart history={history as { incident_id: string; risk_score: number; risk_level: string }[]} />
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-1 px-2">Incident</th>
                  <th className="text-left py-1 px-2">Date</th>
                  <th className="text-left py-1 px-2">Time</th>
                  <th className="text-left py-1 px-2">Risk</th>
                  <th className="text-left py-1 px-2">Level</th>
                  <th className="text-left py-1 px-2">Trend</th>
                  <th className="text-left py-1 px-2">Classification</th>
                  <th className="text-left py-1 px-2">Response</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-1 px-2 text-cyan-400 font-mono">{h.incident_id as string}</td>
                    <td className="py-1 px-2 text-gray-400">{String(h.timestamp).slice(0, 10)}</td>
                    <td className="py-1 px-2 text-gray-400">{String(h.timestamp).slice(11, 19)}</td>
                    <td className="py-1 px-2 font-mono">{h.risk_score as number}</td>
                    <td className="py-1 px-2"><SeverityBadge severity={h.risk_level as string} /></td>
                    <td className="py-1 px-2">{h.trend as string}</td>
                    <td className="py-1 px-2">{h.classification as string}</td>
                    <td className="py-1 px-2 max-w-[150px] truncate">{String(h.recommended_response ?? '').replace(/_/g, ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {!result && (
        <Panel title="MODULE 4 — DECISION PIPELINE">
          <p className="text-sm text-gray-500 text-center py-12">
            Select a PP1 scenario above, or configure inputs manually, then click{' '}
            <strong className="text-gray-300">EVALUATE — Run Module 4 Pipeline</strong>
          </p>
        </Panel>
      )}
    </div>
  )
}
