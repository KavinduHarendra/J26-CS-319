import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Activity, Radio, ShieldAlert, FileText, ArrowRight, RefreshCw } from 'lucide-react'
import { fetchEvaluateIncidents } from '../api'
import { Panel, StatRow } from '../components/Panel'
import SeverityBadge from '../components/SeverityBadge'

export default function Dashboard() {
  const [incidents, setIncidents] = useState<Record<string, unknown>[]>([])
  const [error, setError] = useState<string | null>(null)
  const loadData = useCallback(async () => {
    try {
      const data = await fetchEvaluateIncidents(100)
      setIncidents(data.incidents)
      setError(null)
    } catch {
      setError('Unable to load audit records. Check that the backend is running, then refresh.')
    }
  }, [])
  useEffect(() => {
    void loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [loadData])
  const latest = incidents.at(-1)
  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-1">CYBER DEFENSE & RESPONSE ENGINE</h1>
        <p className="text-sm text-gray-500">Evidence correlation, risk assessment, response recommendations, and audit logging</p>
      </header>
      {error && <p role="alert" className="mb-4 text-sm text-red-300">{error}</p>}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <Panel title="LATEST OBSERVATION">
          {latest ? <>
            <StatRow label="Observation ID" value={String(latest.observation_id ?? '')} highlight />
            <StatRow label="Timestamp" value={String(latest.timestamp ?? '')} />
            <StatRow label="Link State" value={String(latest.link_state ?? '')} />
            <StatRow label="Authentication" value={String(latest.auth_state ?? '')} />
            <StatRow label="Integrity" value={String(latest.integrity_state ?? '')} />
            <StatRow label="Freshness" value={String(latest.freshness_state ?? '')} />
          </> : <p className="text-sm text-gray-500">No evaluated observations yet.</p>}
        </Panel>
        <Panel title="RISK OVERVIEW">
          {latest ? <>
            <StatRow label="Classification" value={String(latest.classification ?? '')} highlight />
            <StatRow label="Risk Level" value={<SeverityBadge severity={String(latest.risk_level ?? '')} />} />
            <StatRow label="Risk Score" value={`${latest.risk_score}/100`} />
            <StatRow label="Evidence Conflict" value={latest.evidence_conflict ? 'YES' : 'NO'} />
            <StatRow label="Recommended Response" value={String(latest.recommended_response ?? '').replaceAll('_', ' ')} highlight />
          </> : <p className="text-sm text-gray-500">Run an evaluation to view risk and recommendations.</p>}
        </Panel>
        <Panel title="EVALUATION WORKFLOW">
          <ol className="text-xs text-gray-400 space-y-2 list-decimal list-inside">
            <li>Open Defense Evaluation</li><li>Upload Module 2 and Module 3 JSON files</li>
            <li>Run file integration</li><li>Review correlated evidence and risk score</li>
            <li>Review the recommendation and explanation</li><li>Check the audit log below</li>
          </ol>
          <Link to="/" className="mt-4 flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 hover:bg-cyan-500/30 transition text-sm font-medium">
            Go to Defense Evaluation <ArrowRight className="w-4 h-4" />
          </Link>
        </Panel>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { icon: Radio, label: 'Evidence Correlation', sub: 'Module 2 + Module 3', color: 'text-cyan-400' },
          { icon: ShieldAlert, label: 'Risk Assessment', sub: 'Explainable Scoring', color: 'text-purple-400' },
          { icon: Activity, label: 'Response Selection', sub: 'Recommendations Only', color: 'text-amber-400' },
          { icon: FileText, label: 'Decision & Audit', sub: 'SQLite Records', color: 'text-emerald-400' },
        ].map(({ icon: Icon, label, sub, color }) => <div key={label} className="bg-[#111827] border border-gray-800 rounded-xl p-4 text-center">
          <Icon className={`w-6 h-6 mx-auto mb-2 ${color}`} /><p className="text-xs font-semibold text-gray-200">{label}</p><p className="text-[10px] text-gray-500 mt-1">{sub}</p>
        </div>)}
      </div>
      <Panel title="INCIDENT AUDIT LOG">
        <div className="flex justify-end mb-3"><button onClick={loadData} className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-gray-700 text-gray-400 hover:text-gray-200"><RefreshCw className="w-3 h-3" /> Refresh</button></div>
        {incidents.length === 0 ? <p className="text-sm text-gray-500 text-center py-6">No incidents yet. Run a defense evaluation to populate the audit log.</p> : <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-gray-500 border-b border-gray-800">{['ID', 'Time', 'Observation', 'Classification', 'Risk Level', 'Score', 'Triggered Rule', 'Recommended Response', 'Status'].map(label => <th key={label} className="text-left py-2 px-2">{label}</th>)}</tr></thead>
            <tbody>{incidents.map(inc => <tr key={String(inc.incident_id)} className="border-b border-gray-800/50 hover:bg-gray-800/30">
              <td className="py-2 px-2 text-cyan-400 font-mono">{String(inc.incident_id)}</td>
              <td className="py-2 px-2">{String(inc.timestamp)}</td><td className="py-2 px-2">{String(inc.observation_id ?? '')}</td>
              <td className="py-2 px-2">{String(inc.classification ?? '')}</td><td className="py-2 px-2"><SeverityBadge severity={String(inc.risk_level ?? '')} /></td>
              <td className="py-2 px-2">{String(inc.risk_score)}</td><td className="py-2 px-2">{String(inc.triggered_rule ?? 'None')}</td>
              <td className="py-2 px-2">{String(inc.recommended_response ?? '').replaceAll('_', ' ')}</td><td className="py-2 px-2">{String(inc.response_status ?? '')}</td>
            </tr>)}</tbody>
          </table>
        </div>}
      </Panel>
    </div>
  )
}
