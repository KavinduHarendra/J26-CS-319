import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Activity, Radio, ShieldAlert, TrendingUp, ArrowRight, RefreshCw } from 'lucide-react'
import { fetchUAVStatus, fetchIncidents } from '../api'
import type { Incident, UAVStatus } from '../types'
import { Panel, StatRow } from '../components/Panel'
import SeverityBadge from '../components/SeverityBadge'

export default function Dashboard() {
  const [uav, setUav] = useState<UAVStatus | null>(null)
  const [incidents, setIncidents] = useState<Incident[]>([])

  const loadData = useCallback(() => {
    fetchUAVStatus().then((r) => setUav(r.status))
    fetchIncidents().then((r) => setIncidents(r.incidents))
  }, [])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [loadData])

  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-1">
          AUTONOMOUS CYBER DEFENSE & RESPONSE ENGINE
        </h1>
        <p className="text-sm text-gray-500">
          AI-Driven SDR-Based Anti-Jamming and Wireless Threat Detection Framework for UAV Cyber Defense
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <Panel title="UAV STATUS" className="lg:col-span-1">
          {uav ? (
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xl font-bold text-cyan-400">{uav.uav_id}</span>
                <span className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  {uav.mission_status}
                </span>
              </div>
              <StatRow label="Communication" value={uav.communication} highlight />
              <StatRow label="Primary Channel" value={uav.primary_channel} />
              <StatRow label="Backup Channel" value={uav.backup_channel} />
              <StatRow label="GPS" value={uav.gps_status} />
              <StatRow label="Telemetry" value={uav.telemetry_status} />
              <StatRow label="Mode" value={uav.current_mode} />
              <StatRow label="Security" value={uav.security_status} />
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Loading...</p>
          )}
        </Panel>

        <Panel title="THREAT OVERVIEW" className="lg:col-span-1">
          {uav ? (
            <div>
              <StatRow label="Current Threat" value={uav.current_threat} highlight />
              <StatRow label="Severity" value={<SeverityBadge severity={uav.threat_severity} />} />
              <StatRow label="Threat Score" value={`${uav.threat_score}/100`} />
              <StatRow label="Forecast" value={
                <span className={uav.forecast === 'ESCALATING' ? 'text-red-400' : 'text-gray-200'}>
                  {uav.forecast}
                </span>
              } />
              <StatRow label="Recommended Response" value={uav.recommended_response} highlight />
            </div>
          ) : null}
        </Panel>

        <Panel title="QUICK START — DEMO FLOW" className="lg:col-span-1">
          <ol className="text-xs text-gray-400 space-y-2 list-decimal list-inside">
            <li>Open Threat Simulation page</li>
            <li>Click <strong className="text-gray-300">Simulate Jamming</strong></li>
            <li>Click <strong className="text-gray-300">Analyze Threat</strong></li>
            <li>Review forecast & decision</li>
            <li>Click <strong className="text-gray-300">Simulate Response</strong></li>
            <li>Check incident log below</li>
          </ol>
          <Link
            to="/threat-simulation"
            className="mt-4 flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 hover:bg-cyan-500/30 transition text-sm font-medium"
          >
            Go to Threat Simulation <ArrowRight className="w-4 h-4" />
          </Link>
        </Panel>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { icon: Radio, label: 'RF Threat Detection', sub: 'Simulated Input', color: 'text-cyan-400' },
          { icon: ShieldAlert, label: 'Risk Assessment', sub: 'Rule-Based Scoring', color: 'text-purple-400' },
          { icon: TrendingUp, label: 'Threat Forecast', sub: 'Conceptual Model', color: 'text-amber-400' },
          { icon: Activity, label: 'Autonomous Decision', sub: 'Response Engine', color: 'text-emerald-400' },
        ].map(({ icon: Icon, label, sub, color }) => (
          <div key={label} className="bg-[#111827] border border-gray-800 rounded-xl p-4 text-center">
            <Icon className={`w-6 h-6 mx-auto mb-2 ${color}`} />
            <p className="text-xs font-semibold text-gray-200">{label}</p>
            <p className="text-[10px] text-gray-500 mt-1">{sub}</p>
          </div>
        ))}
      </div>

      <Panel title="INCIDENT LOG">
        <div className="flex justify-end mb-3">
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-cyan-500/40 transition"
          >
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
        {incidents.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-6">
            No incidents yet. Run a threat simulation and simulate a response to populate the log.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-2 px-2">ID</th>
                  <th className="text-left py-2 px-2">Time</th>
                  <th className="text-left py-2 px-2">UAV</th>
                  <th className="text-left py-2 px-2">Threat</th>
                  <th className="text-left py-2 px-2">Severity</th>
                  <th className="text-left py-2 px-2">Score</th>
                  <th className="text-left py-2 px-2">Forecast</th>
                  <th className="text-left py-2 px-2">Decision</th>
                  <th className="text-left py-2 px-2">Response</th>
                  <th className="text-left py-2 px-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr key={inc.incident_id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-2 px-2 text-cyan-400 font-mono">{inc.incident_id}</td>
                    <td className="py-2 px-2">{inc.timestamp}</td>
                    <td className="py-2 px-2">{inc.uav_id}</td>
                    <td className="py-2 px-2">{inc.threat}</td>
                    <td className="py-2 px-2"><SeverityBadge severity={inc.severity} /></td>
                    <td className="py-2 px-2">{inc.score}</td>
                    <td className="py-2 px-2">{inc.forecast}</td>
                    <td className="py-2 px-2 max-w-[140px] truncate">{inc.decision}</td>
                    <td className="py-2 px-2">{inc.response}</td>
                    <td className="py-2 px-2">{inc.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}
