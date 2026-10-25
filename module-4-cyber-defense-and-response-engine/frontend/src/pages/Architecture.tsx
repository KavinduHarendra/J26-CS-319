import { ArrowDown } from 'lucide-react'
import { Panel } from '../components/Panel'

const workflow = [
  { step: 'RF / UAV DATA', desc: 'Raw RF metrics, telemetry, and communication data from SDR and UAV (simulated in prototype)' },
  { step: 'THREAT INPUT', desc: 'Structured threat indicators: SNR, packet loss, auth status, threat type, confidence' },
  { step: 'THREAT ANALYSIS', desc: 'Explainable rule-based scoring combining detection module outputs' },
  { step: 'RISK SCORING', desc: 'Threat score 0–100 mapped to LOW / MEDIUM / HIGH / CRITICAL severity' },
  { step: 'AUTONOMOUS DECISION ENGINE', desc: 'Combines current risk and correlated evidence to select a defense recommendation' },
  { step: 'RESPONSE RECOMMENDATION', desc: 'Channel switch, safe mode, monitoring, operator alerts' },
  { step: 'DECISION AUDIT LOGGING', desc: 'Incident log with full decision audit trail' },
]

const architecture = [
  { name: 'SDR RF Threat Detection', role: 'Detects jamming, interference, abnormal RF patterns', sim: true },
  { name: 'AI Threat Intelligence', role: 'Classifies threats, provides confidence scores', sim: true },
  { name: 'Secure UAV Communication', role: 'Authentication, encryption, channel management', sim: true },
  { name: 'AUTONOMOUS CYBER DEFENSE & RESPONSE ENGINE', role: 'YOUR COMPONENT — Evidence correlation, risk assessment, response recommendation, and audit logging', sim: false, highlight: true },
  { name: 'Response Recommendation', role: 'Recommended actions for operator review; no execution', sim: true },
]

const sampleData = [
  'Timestamp', 'Frequency', 'Signal Strength', 'Noise', 'SNR',
  'Bandwidth', 'Packet Loss', 'Threat Type', 'Threat Score',
]

export default function Architecture() {
  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">System Workflow & Architecture</h1>
        <p className="text-sm text-gray-500 mt-1">
          Conceptual integration of research framework components
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="SYSTEM WORKFLOW — MY COMPONENT PROCESS">
          <div className="space-y-1">
            {workflow.map(({ step, desc }, i) => (
              <div key={step}>
                <div className={`p-3 rounded-lg border ${step.includes('AUTONOMOUS') ? 'bg-cyan-500/10 border-cyan-500/40' : 'bg-cyber-bg border-gray-800'}`}>
                  <p className={`text-sm font-semibold ${step.includes('AUTONOMOUS') ? 'text-cyan-400' : 'text-gray-200'}`}>{step}</p>
                  <p className="text-xs text-gray-500 mt-1">{desc}</p>
                </div>
                {i < workflow.length - 1 && (
                  <div className="flex justify-center py-1">
                    <ArrowDown className="w-4 h-4 text-gray-600" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </Panel>

        <div className="space-y-6">
          <Panel title="FRAMEWORK ARCHITECTURE — COMPONENT INTEGRATION">
            <div className="space-y-2">
              {architecture.map(({ name, role, sim, highlight }) => (
                <div key={name}>
                  <div className={`p-3 rounded-lg border ${highlight ? 'bg-purple-500/10 border-purple-500/40' : 'bg-cyber-bg border-gray-800'}`}>
                    <div className="flex items-center justify-between">
                      <p className={`text-sm font-semibold ${highlight ? 'text-purple-300' : 'text-gray-200'}`}>{name}</p>
                      {sim && <span className="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-500">Simulated Input</span>}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{role}</p>
                  </div>
                  <div className="flex justify-center py-1">
                    <ArrowDown className="w-4 h-4 text-gray-600" />
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="SAMPLE INPUT DATA — Expected Fields (Prototype)">
            <div className="flex flex-wrap gap-2">
              {sampleData.map((field) => (
                <span key={field} className="px-2 py-1 rounded bg-gray-800 text-xs text-gray-400">{field}</span>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-3">
              Future inputs from: SDR RF monitoring · Controlled UAV flights · Simulated RF conditions · Public RF datasets · UAV telemetry
            </p>
            <p className="text-[10px] text-amber-500/80 mt-2">
              No confidential or real departmental data exposed in this prototype
            </p>
          </Panel>
        </div>
      </div>
    </div>
  )
}
