import type { ReactNode } from 'react'

export function Panel({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`bg-cyber-panel border border-gray-800 rounded-xl overflow-hidden ${className}`}>
      <div className="px-4 py-3 border-b border-gray-800 bg-cyber-surface">
        <h3 className="text-sm font-semibold text-gray-200">{title}</h3>
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}

export function StatRow({ label, value, highlight }: { label: string; value: ReactNode; highlight?: boolean }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-800/50 last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <span className={`text-sm font-medium ${highlight ? 'text-cyan-400' : 'text-gray-200'}`}>{value}</span>
    </div>
  )
}
