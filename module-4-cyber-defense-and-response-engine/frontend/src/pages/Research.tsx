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
            the system must <strong className="text-white">assess risk and recommend responses</strong> autonomously.
          </p>
        </Panel>

        <Panel title="PROPOSED SOLUTION">
          <p className="text-sm text-gray-300 leading-relaxed">
            An <strong className="text-cyan-400">Autonomous Cyber Defense and Response Engine</strong> that
            receives threat intelligence from SDR detection, AI classification, and secure communication modules,
            then performs evidence correlation, risk assessment, response selection, and explainable audit logging.
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
              Detection alert without correlated evidence or risk-based recommendations
            </p>
          </div>
        </Panel>

        <Panel title="PROPOSED APPROACH — MY COMPONENT">
          <div className="flex flex-col items-center py-4 space-y-1">
            {[
              'Threat Detected',
              'Risk Assessment',
              'Autonomous Decision',
              'Response Recommendation',
              'Explainable Decision & Audit Logging',
            ].map((step, i, arr) => (
              <div key={step} className="flex flex-col items-center">
                <div className={`px-4 py-2 rounded-lg text-sm font-medium ${
                  step.includes('Autonomous')
                    ? 'bg-cyan-500/10 border border-cyan-500/40 text-cyan-300'
                    : 'bg-purple-500/10 border border-purple-500/30 text-purple-300'
                }`}>
                  {step}
                </div>
                {i < arr.length - 1 && <ArrowDown className="w-4 h-4 text-gray-600 my-1" />}
              </div>
            ))}
            <p className="text-xs text-emerald-400 mt-3 text-center font-semibold">
              Correlated evidence · Explainable risk · Recommendations only
            </p>
          </div>
        </Panel>
      </div>

      <div className="mt-8 p-6 rounded-xl bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/20 text-center">
        <p className="text-lg font-bold text-white mb-2">
          "From Threat Detection to Autonomous Cyber Defense"
        </p>
        <p className="text-sm text-gray-400">
          Correlate · Assess · Recommend · Explain · Log
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
            { action: 'Decide', desc: 'Select a defense recommendation using risk and evidence' },
            { action: 'Recommend', desc: 'Channel switch, safe mode, operator alerts' },
            { action: 'Monitor', desc: 'Record evidence, risk, selected response, and explanations' },
          ].map(({ action, desc }) => (
            <div key={action} className="p-3 rounded-lg bg-cyber-bg border border-gray-800">
              <p className="text-cyan-400 font-semibold text-sm">{action}</p>
              <p className="text-xs text-gray-500 mt-1">{desc}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}
