import { ArrowDown, ArrowRight } from 'lucide-react'
import { Panel } from '../components/Panel'

export default function Research() {
  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white">My Research Contribution</h1>
        <p className="text-sm text-gray-500 mt-1">
          Autonomous Cyber Defense and Response Engine — Individual Research Component
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <Panel title="PROBLEM">
          <p className="text-sm text-gray-300 leading-relaxed">
            UAV wireless communication is vulnerable to RF attacks including jamming, spoofing,
            unauthorized transmissions, and suspicious commands. Detection alone is insufficient —
            the system must <strong className="text-white">decide and respond</strong> autonomously.
          </p>
        </Panel>

        <Panel title="PROPOSED SOLUTION">
          <p className="text-sm text-gray-300 leading-relaxed">
            An <strong className="text-cyan-400">Autonomous Cyber Defense and Response Engine</strong> that
            receives threat intelligence from SDR detection, AI classification, and secure communication modules,
            then performs risk assessment, threat forecasting, and autonomous defense decision-making.
          </p>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <Panel title="TRADITIONAL APPROACH">
          <div className="flex flex-col items-center py-6">
            <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm font-semibold">
              Threat Detected
            </div>
            <ArrowDown className="w-5 h-5 text-gray-600 my-2" />
            <div className="px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 text-sm">
              Alert Operator
            </div>
            <p className="text-xs text-gray-500 mt-4 text-center">
              Reactive · Manual · No predictive capability
            </p>
          </div>
        </Panel>

        <Panel title="PROPOSED APPROACH — MY COMPONENT">
          <div className="flex flex-col items-center py-4 space-y-1">
            {[
              'Threat Detected',
              'Risk Assessment',
              'Threat Forecast',
              'Autonomous Decision',
              'Response Recommendation',
              'Response Execution',
              'Feedback & Logging',
            ].map((step, i, arr) => (
              <div key={step} className="flex flex-col items-center">
                <div className={`px-4 py-2 rounded-lg text-sm font-medium ${
                  step.includes('Autonomous') || step.includes('Forecast')
                    ? 'bg-cyan-500/10 border border-cyan-500/40 text-cyan-300'
                    : 'bg-purple-500/10 border border-purple-500/30 text-purple-300'
                }`}>
                  {step}
                </div>
                {i < arr.length - 1 && <ArrowDown className="w-4 h-4 text-gray-600 my-1" />}
              </div>
            ))}
            <p className="text-xs text-emerald-400 mt-3 text-center font-semibold">
              Proactive · Autonomous · Forecast-aware
            </p>
          </div>
        </Panel>
      </div>

      <Panel title="REACTIVE vs PREDICTIVE DEFENSE — Key Research Concept">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Reactive Defense</p>
            <p className="text-sm text-gray-300 mb-3">
              Current threat score = 55 (HIGH) → <strong className="text-yellow-400">Increase Monitoring</strong>
            </p>
            <p className="text-xs text-gray-500">
              Responds only to current state. May be too late if threat is escalating rapidly.
            </p>
          </div>
          <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
            <p className="text-xs text-amber-400 uppercase tracking-wider mb-2">Predictive / Forecast-Aware Defense</p>
            <p className="text-sm text-gray-300 mb-3">
              Forecast: score expected to reach 82 in 15 min → <strong className="text-amber-300">Prepare Backup Communication</strong>
            </p>
            <p className="text-xs text-gray-500">
              Acts before critical threshold. Demonstrates research value of forecasting in autonomous defense.
            </p>
          </div>
        </div>
      </Panel>

      <div className="mt-8 p-6 rounded-xl bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/20 text-center">
        <p className="text-lg font-bold text-white mb-2">
          "From Threat Detection to Autonomous Cyber Defense"
        </p>
        <p className="text-sm text-gray-400">
          Assess · Predict · Decide · Recommend · Respond · Monitor
        </p>
        <div className="flex items-center justify-center gap-2 mt-4 text-xs text-gray-500">
          <span>Detection</span>
          <ArrowRight className="w-3 h-3" />
          <span>Intelligence</span>
          <ArrowRight className="w-3 h-3" />
          <span className="text-cyan-400 font-semibold">Autonomous Defense (My Component)</span>
          <ArrowRight className="w-3 h-3" />
          <span>Response</span>
        </div>
      </div>

      <Panel title="WHAT MY COMPONENT DOES" className="mt-6">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[
            { action: 'Assess', desc: 'Combine module outputs into unified risk score' },
            { action: 'Predict', desc: 'Forecast threat escalation using trend analysis' },
            { action: 'Decide', desc: 'Select optimal defense response autonomously' },
            { action: 'Recommend', desc: 'Channel switch, safe mode, operator alerts' },
            { action: 'Respond', desc: 'Generate response workflows (simulated)' },
            { action: 'Monitor', desc: 'Log incidents and update UAV status' },
          ].map(({ action, desc }) => (
            <div key={action} className="p-3 rounded-lg bg-[#0a0e17] border border-gray-800">
              <p className="text-cyan-400 font-semibold text-sm">{action}</p>
              <p className="text-xs text-gray-500 mt-1">{desc}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}
