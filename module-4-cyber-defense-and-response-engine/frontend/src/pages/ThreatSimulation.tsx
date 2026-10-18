import { Link } from 'react-router-dom'
import { useState } from 'react'
import {
  Play,
  RotateCcw,
  Zap,
  Brain,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import { analyzeThreat, fetchScenario, resetSimulation, simulateResponse } from '../api'
import type { FullAnalysis, SimulateResult, ThreatInput } from '../types'
import ForecastChart from '../components/ForecastChart'
import { Panel, StatRow } from '../components/Panel'
import SeverityBadge from '../components/SeverityBadge'

const DEFAULT_INPUT: ThreatInput = {
  uav_id: 'UAV-01',
  frequency_mhz: 2400,
  signal_strength_dbm: -62,
  noise_level_dbm: -95,
  snr_db: 33,
  bandwidth_mhz: 20,
  packet_loss_pct: 0.5,
  latency_ms: 28,
  authentication_status: 'VALID',
  controller_trust_status: 'TRUSTED',
  communication_status: 'STABLE',
  threat_type: 'Normal',
  threat_confidence: 0.05,
  previous_threat_score: 8,
  force_evidence_conflict: false,
  simulated_response_outcome: 'AUTO',
}

const THREAT_TYPES = [
  'Normal',
  'Jamming',
  'Spoofing',
  'Unauthorized Transmission',
  'Suspicious Command',
  'Replay Attempt',
  'Unknown Anomaly',
]

const SCENARIO_BUTTONS = [
  { id: 'normal', label: 'Normal' },
  { id: 'jamming', label: 'Simulate Jamming' },
  { id: 'spoofing', label: 'Simulate Spoofing' },
  { id: 'unauthorized', label: 'Simulate Unauthorized Transmission' },
  { id: 'suspicious_command', label: 'Simulate Suspicious Command' },
  { id: 'replay', label: 'Simulate Replay Attempt' },
  { id: 'escalation', label: 'Simulate Threat Escalation' },
  { id: 'conflicting_evidence', label: 'Conflicting Evidence' },
  { id: 'response_failure', label: 'Response Failure' },
]

export default function ThreatSimulation() {
  const [input, setInput] = useState<ThreatInput>(DEFAULT_INPUT)
  const [analysis, setAnalysis] = useState<FullAnalysis | null>(null)
  const [simResult, setSimResult] = useState<SimulateResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [simulating, setSimulating] = useState(false)

  const loadScenario = async (id: string) => {
    const { scenario } = await fetchScenario(id)
    setInput(scenario)
    setAnalysis(null)
    setSimResult(null)
  }

  const handleAnalyze = async () => {
    setLoading(true)
    setSimResult(null)
    try {
      const result = await analyzeThreat(input)
      setAnalysis(result)
    } finally {
      setLoading(false)
    }
  }

  const handleSimulate = async () => {
    if (!analysis) return
    setSimulating(true)
    try {
      const result = await simulateResponse({
        uav_id: input.uav_id,
        threat_type: analysis.analysis.threat_type,
        threat_score: analysis.analysis.threat_score,
        severity: analysis.analysis.severity,
        forecast_trend: analysis.forecast.trend,
        primary_response: analysis.decision.primary_response,
        primary_actions: analysis.decision.primary_actions,
        before_evidence: {
          threat_score: analysis.analysis.threat_score,
          packet_loss_pct: input.packet_loss_pct,
          snr_db: input.snr_db,
          communication_status: input.communication_status,
        },
        simulated_response_outcome: input.simulated_response_outcome,
      })
      setSimResult(result)
    } finally {
      setSimulating(false)
    }
  }

  const handleReset = async () => {
    await resetSimulation()
    setInput(DEFAULT_INPUT)
    setAnalysis(null)
    setSimResult(null)
  }

  const update = (field: keyof ThreatInput, value: string | number) => {
    setInput((prev) => ({ ...prev, [field]: value }))
    setAnalysis(null)
    setSimResult(null)
  }

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-white">Threat Simulation & Analysis</h1>
        <p className="text-sm text-gray-500 mt-1">
          Simulate RF/wireless threat inputs · Analyze · Forecast · Decide · Respond
        </p>
      </header>

      {/* Flow indicator */}
      <div className="flex flex-wrap items-center gap-1 text-[10px] text-gray-500 mb-6 overflow-x-auto pb-2">
        {['THREAT INPUT', 'ANALYSIS', 'RISK', 'FORECAST', 'DECISION', 'RESPONSE', 'UAV STATUS', 'LOG'].map((step, i) => (
          <span key={step} className="flex items-center gap-1">
            {i > 0 && <span className="text-gray-700">→</span>}
            <span className={`px-2 py-1 rounded ${analysis ? 'bg-cyan-500/10 text-cyan-400' : 'bg-gray-800'}`}>{step}</span>
          </span>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Input Panel */}
        <Panel title="THREAT INPUT — Sample / Simulated Data">
          <div className="flex flex-wrap gap-2 mb-4">
            {SCENARIO_BUTTONS.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => loadScenario(id)}
                className="px-3 py-1.5 text-xs rounded-lg border border-gray-700 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-gray-300 transition"
              >
                {label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-4 text-[11px]">
            <div className="rounded-lg border border-cyan-500/25 bg-cyan-500/5 p-3"><p className="font-semibold text-cyan-300">SDR / RF MOCK ADAPTER</p><p className="text-gray-500 mt-1">Frequency, signal, noise and SNR evidence</p></div>
            <div className="rounded-lg border border-purple-500/25 bg-purple-500/5 p-3"><p className="font-semibold text-purple-300">AI THREAT INTELLIGENCE</p><p className="text-gray-500 mt-1">Threat classification and confidence</p></div>
            <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-3"><p className="font-semibold text-emerald-300">SECURE COMMUNICATION</p><p className="text-gray-500 mt-1">Link, authentication and controller trust</p></div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            {([
              ['uav_id', 'UAV ID', 'text'],
              ['frequency_mhz', 'Frequency (MHz)', 'number'],
              ['signal_strength_dbm', 'Signal Strength (dBm)', 'number'],
              ['noise_level_dbm', 'Noise Level (dBm)', 'number'],
              ['snr_db', 'SNR (dB)', 'number'],
              ['bandwidth_mhz', 'Bandwidth (MHz)', 'number'],
              ['packet_loss_pct', 'Packet Loss (%)', 'number'],
              ['latency_ms', 'Latency (ms)', 'number'],
              ['authentication_status', 'Authentication', 'text'],
              ['controller_trust_status', 'Controller Trust', 'text'],
              ['communication_status', 'Communication', 'text'],
              ['threat_confidence', 'Threat Confidence', 'number'],
              ['previous_threat_score', 'Previous Threat Score', 'number'],
            ] as const).map(([field, label, type]) => (
              <label key={field} className="block">
                <span className="text-gray-500">{label}</span>
                <input
                  type={type}
                  value={input[field]}
                  onChange={(e) =>
                    update(field, type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value)
                  }
                  className="mt-1 w-full px-2 py-1.5 rounded bg-[#0a0e17] border border-gray-700 text-gray-200 focus:border-cyan-500/50 outline-none"
                />
              </label>
            ))}
            <label className="block col-span-2">
              <span className="text-gray-500">Threat Type</span>
              <select
                value={input.threat_type}
                onChange={(e) => update('threat_type', e.target.value)}
                className="mt-1 w-full px-2 py-1.5 rounded bg-[#0a0e17] border border-gray-700 text-gray-200 focus:border-cyan-500/50 outline-none"
              >
                {THREAT_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex gap-3 mt-4">
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-cyan-500 text-black font-semibold text-sm hover:bg-cyan-400 transition disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              {loading ? 'Analyzing...' : 'Analyze Threat'}
            </button>
            <button
              onClick={handleReset}
              className="px-4 py-2.5 rounded-lg border border-gray-700 text-gray-400 hover:text-gray-200 text-sm flex items-center gap-2"
            >
              <RotateCcw className="w-4 h-4" /> Reset
            </button>
          </div>
        </Panel>

        {/* Analysis Results */}
        {analysis ? (
          <div className="space-y-6">
            <Panel title="THREAT ANALYSIS — Explainable Scoring">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-3xl font-bold text-white">{analysis.analysis.threat_score}<span className="text-lg text-gray-500">/100</span></p>
                  <p className="text-xs text-gray-500">Threat Score</p>
                </div>
                <SeverityBadge severity={analysis.analysis.severity} />
              </div>
              <StatRow label="Threat Type" value={analysis.analysis.threat_type} />
              <StatRow label="Confidence" value={`${(analysis.analysis.confidence * 100).toFixed(0)}%`} />
              <StatRow label="Affected Communication" value={analysis.analysis.affected_communication} />
              <StatRow label="Decision Confidence" value={analysis.analysis.decision_confidence} />
              {analysis.analysis.evidence_conflict && (
                <div className="my-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/40">
                  <p className="text-xs font-semibold text-amber-300">EVIDENCE CONFLICT DETECTED</p>
                  {analysis.analysis.conflict_details.map((detail) => <p key={detail} className="text-[11px] text-gray-400 mt-1">{detail}</p>)}
                </div>
              )}
              <div className="mt-4">
                <p className="text-xs text-gray-500 mb-2">Score Factors:</p>
                <ul className="space-y-1">
                  {analysis.analysis.risk_factors.map((f, i) => (
                    <li key={i} className="flex justify-between text-xs">
                      <span className="text-gray-400">{f.label}</span>
                      <span className="text-red-400 font-mono">+{f.points}</span>
                    </li>
                  ))}
                </ul>
                <div className="flex justify-between mt-2 pt-2 border-t border-gray-800 font-semibold text-sm">
                  <span>Total</span>
                  <span className="text-cyan-400">{analysis.analysis.score_breakdown_total}</span>
                </div>
              </div>
            </Panel>
            <Panel title="MULTI-SOURCE CORRELATION">
              <div className="space-y-3">
                {analysis.analysis.source_contributions.map((source) => (
                  <div key={source.source}>
                    <div className="flex justify-between text-xs mb-1"><span className="text-gray-300">{source.source} <span className="text-gray-600">({Math.round(source.weight * 100)}%)</span></span><span className="text-cyan-300">{source.weighted_points} pts</span></div>
                    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden"><div className="h-full bg-cyan-500" style={{ width: `${source.raw_score}%` }} /></div>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-gray-600 mt-3">Weights loaded from backend/config/engine_config.json</p>
            </Panel>
            <Panel title="NORMALIZED EVIDENCE RECORD">
              <div className="grid grid-cols-2 gap-x-4">{Object.entries(analysis.analysis.normalized_evidence).map(([key, value]) => <StatRow key={key} label={key.replaceAll('_', ' ')} value={String(value)} />)}</div>
            </Panel>
          </div>
        ) : (
          <Panel title="THREAT ANALYSIS">
            <p className="text-sm text-gray-500 text-center py-12">
              Configure threat inputs or select a scenario, then click <strong className="text-gray-300">Analyze Threat</strong>
            </p>
          </Panel>
        )}
      </div>

      {analysis && (
        <>
          {/* Forecast */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mt-6">
            <Panel title="THREAT FORECAST — Conceptual / Prototype">
              <ForecastChart forecast={analysis.forecast} />
              <div className="grid grid-cols-3 gap-3 mt-4">
                {analysis.forecast.forecast_points.map((p) => (
                  <div key={p.minutes_ahead} className="text-center p-2 rounded bg-[#0a0e17] border border-gray-800">
                    <p className="text-[10px] text-gray-500">{p.label}</p>
                    <p className="text-lg font-bold text-amber-400">{p.score}</p>
                  </div>
                ))}
              </div>
              <p className="text-center mt-3 text-sm">
                Trend: <span className={analysis.forecast.trend === 'ESCALATING' ? 'text-red-400 font-bold' : 'text-gray-300'}>{analysis.forecast.trend}</span>
              </p>
              <p className="text-center text-[11px] text-gray-500">Forecast confidence: {analysis.forecast.confidence}</p>
            </Panel>

            {/* Decision Engine */}
            <Panel title="AUTONOMOUS DEFENSE DECISION">
              <div className="mb-4 p-3 rounded-lg bg-purple-500/10 border border-purple-500/30">
                <p className="text-[10px] text-purple-300 uppercase tracking-wider">Decision Mode</p>
                <p className="text-sm font-semibold text-purple-200">{analysis.decision.decision_mode}</p>
              </div>

              <div className="space-y-4">
                <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700">
                  <p className="text-[10px] text-gray-500 mb-1">REACTIVE RESPONSE (Current State Only)</p>
                  <p className="text-sm text-gray-300">{analysis.decision.reactive_response}</p>
                </div>

                {analysis.decision.forecast_influenced && (
                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                    <p className="text-[10px] text-amber-400 mb-1">FORECAST-AWARE RESPONSE (Predictive Defense)</p>
                    <p className="text-sm font-semibold text-amber-200">{analysis.decision.forecast_aware_response}</p>
                  </div>
                )}

                <div className="p-4 rounded-lg bg-cyan-500/10 border border-cyan-500/40">
                  <p className="text-[10px] text-cyan-400 mb-1">PRIMARY DECISION</p>
                  <p className="text-lg font-bold text-cyan-300">{analysis.decision.primary_response}</p>
                  <ul className="mt-2 space-y-1">
                    {analysis.decision.primary_actions.map((a, i) => (
                      <li key={i} className="text-xs text-gray-400 flex items-start gap-2">
                        <CheckCircle2 className="w-3 h-3 text-cyan-400 mt-0.5 shrink-0" /> {a}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </Panel>
          </div>

          {/* Explainability */}
          <Panel title="WHY DID THE ENGINE MAKE THIS DECISION?" className="mt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-xs text-gray-500 mb-3">Decision Context</p>
                <StatRow label="Threat" value={analysis.analysis.threat_type} />
                <StatRow label="Severity" value={<SeverityBadge severity={analysis.analysis.severity} />} />
                <StatRow label="Score" value={`${analysis.analysis.threat_score}/100`} />
                <StatRow label="Forecast" value={analysis.forecast.trend} />
                <StatRow label="Communication" value={input.communication_status} />
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-3">Reasons</p>
                <ul className="space-y-2">
                  {analysis.decision.reasons.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      {r}
                    </li>
                  ))}
                </ul>
                <p className="mt-4 p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-sm text-emerald-300">
                  Therefore: <strong>{analysis.decision.primary_response.toUpperCase()}</strong> recommended
                </p>
              </div>
            </div>
          </Panel>

          {/* Simulate Response */}
          <div className="mt-6 flex flex-col items-center gap-4">
            <button
              onClick={handleSimulate}
              disabled={simulating}
              className="flex items-center gap-2 px-8 py-3 rounded-xl bg-emerald-500 text-black font-bold hover:bg-emerald-400 transition disabled:opacity-50"
            >
              <Zap className="w-5 h-5" />
              {simulating ? 'Simulating...' : 'SIMULATE RESPONSE'}
            </button>
            <p className="text-xs text-amber-400 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              SIMULATED RESPONSE — NO REAL UAV CONTROL
            </p>
          </div>

          {simResult && (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mt-6">
              <Panel title="RESPONSE SIMULATION WORKFLOW">
                <ol className="space-y-2">
                  {simResult.steps.map((step, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm">
                      <span className="w-6 h-6 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-xs shrink-0">
                        {i + 1}
                      </span>
                      <span className="text-gray-300">{step}</span>
                    </li>
                  ))}
                </ol>
              </Panel>

              <Panel title="UPDATED UAV STATUS">
                <StatRow label="UAV" value={simResult.uav_status.uav_id} />
                <StatRow label="Communication" value={simResult.uav_status.communication} highlight />
                <StatRow label="Primary Channel" value={simResult.uav_status.primary_channel} />
                <StatRow label="Backup Channel" value={simResult.uav_status.backup_channel} />
                <StatRow label="Mode" value={simResult.uav_status.current_mode} />
                <StatRow label="Security" value={simResult.uav_status.security_status} />
                <StatRow label="Threat Status" value={simResult.incident.status} highlight />
                <div className="mt-4 p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-center">
                  <Brain className="w-5 h-5 text-emerald-400 mx-auto mb-1" />
                  <p className="text-sm text-emerald-300">Incident {simResult.incident.incident_id} logged</p>
                  <Link
                    to="/"
                    className="inline-block mt-2 text-xs text-cyan-400 hover:text-cyan-300 underline"
                  >
                    View updated status on Dashboard →
                  </Link>
                </div>
              </Panel>

              <Panel title="RESPONSE EFFECTIVENESS — BEFORE / AFTER">
                <div className="mb-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-center">
                  <p className="text-[10px] text-emerald-300">CLASSIFICATION</p>
                  <p className="text-xl font-bold text-emerald-200">{simResult.effectiveness.classification}</p>
                </div>
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div><p className="text-gray-500 mb-2">BEFORE</p>{Object.entries(simResult.effectiveness.before).map(([key, value]) => <StatRow key={key} label={key.replaceAll('_', ' ')} value={String(value)} />)}</div>
                  <div><p className="text-gray-500 mb-2">AFTER</p>{Object.entries(simResult.effectiveness.after).map(([key, value]) => <StatRow key={key} label={key.replaceAll('_', ' ')} value={String(value)} />)}</div>
                </div>
                <p className="text-[11px] text-gray-500 mt-3">{simResult.effectiveness.explanation}</p>
              </Panel>

              <Panel title="TIMESTAMPED AUDIT TRAIL">
                <ol className="space-y-2">
                  {simResult.incident.audit_trail.map((event, index) => (
                    <li key={`${event.stage}-${index}`} className="flex gap-3 text-xs"><span className="text-cyan-400 font-mono">{event.timestamp}</span><span className="text-gray-300">{event.stage}</span></li>
                  ))}
                </ol>
              </Panel>
            </div>
          )}
        </>
      )}
    </div>
  )
}
