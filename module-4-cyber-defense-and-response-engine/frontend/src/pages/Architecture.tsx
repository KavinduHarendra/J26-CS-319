import { ArrowDown, RefreshCw } from 'lucide-react'
import { Panel } from '../components/Panel'

const workflow = [
  { step: 'RF / UAV DATA', desc: 'Raw RF metrics, telemetry, and communication data from SDR and UAV (simulated in prototype)' },
  { step: 'THREAT INPUT', desc: 'Structured threat indicators: SNR, packet loss, auth status, threat type, confidence' },
  { step: 'THREAT ANALYSIS', desc: 'Explainable rule-based scoring combining detection module outputs' },
  { step: 'RISK SCORING', desc: 'Threat score 0–100 mapped to LOW / MEDIUM / HIGH / CRITICAL severity' },
  { step: 'FORECASTING', desc: 'Linear trend analysis on historical scores — conceptual prototype forecast' },
  { step: 'AUTONOMOUS DECISION ENGINE', desc: 'Combines current risk + forecast to select proactive or reactive defense' },
  { step: 'RESPONSE RECOMMENDATION', desc: 'Channel switch, safe mode, monitoring, operator alerts' },
  { step: 'RESPONSE SIMULATION', desc: 'Simulated execution — no real UAV control in prototype' },
  { step: 'UAV STATUS', desc: 'Updated communication, mode, and security posture' },
  { step: 'FEEDBACK / LOGGING', desc: 'Incident log with full decision audit trail' },
]

const architecture = [
  { name: 'SDR RF Threat Detection', role: 'Detects jamming, interference, abnormal RF patterns', sim: true },
  { name: 'AI Threat Intelligence', role: 'Classifies threats, provides confidence scores', sim: true },
  { name: 'Secure UAV Communication', role: 'Authentication, encryption, channel management', sim: true },
  { name: 'AUTONOMOUS CYBER DEFENSE & RESPONSE ENGINE', role: 'YOUR COMPONENT — Risk assessment, forecasting, decision, response', sim: false, highlight: true },
  { name: 'Response Recommendation', role: 'Actionable defense commands for UAV/flight controller', sim: true },
  { name: 'UAV / Flight Controller', role: 'Pixhawk, telemetry, mission execution', sim: true },
]

const hardware = [
  { device: 'HackRF / SDR', interface: 'RF Data Interface' },
  { device: 'Pixhawk / UAV', interface: 'Telemetry Interface' },
  { device: 'Autonomous Defense Engine', interface: 'Response Interface' },
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
                <div className={`p-3 rounded-lg border ${step.includes('AUTONOMOUS') ? 'bg-cyan-500/10 border-cyan-500/40' : 'bg-[#0a0e17] border-gray-800'}`}>
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
                  <div className={`p-3 rounded-lg border ${highlight ? 'bg-purple-500/10 border-purple-500/40' : 'bg-[#0a0e17] border-gray-800'}`}>
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
            <div className="mt-4 p-3 rounded-lg border border-dashed border-gray-700 flex items-center gap-2 text-xs text-gray-500">
              <RefreshCw className="w-4 h-4" />
              Telemetry / Feedback loop → Autonomous Cyber Defense Engine
            </div>
          </Panel>

          <Panel title="FUTURE HARDWARE INTEGRATION (Conceptual)">
            {hardware.map(({ device, interface: iface }) => (
              <div key={device} className="flex items-center gap-3 py-2 border-b border-gray-800/50 last:border-0">
                <span className="text-sm text-gray-300 w-48">{device}</span>
                <ArrowDown className="w-4 h-4 text-gray-600 rotate-[-90deg]" />
                <span className="text-sm text-cyan-400">{iface}</span>
              </div>
            ))}
            <p className="text-[10px] text-gray-600 mt-3">
              Physical IoT/UAV integration planned for future research phase (6 months)
            </p>
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
