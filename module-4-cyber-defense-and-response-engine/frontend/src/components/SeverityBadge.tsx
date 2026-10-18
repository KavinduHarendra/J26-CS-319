const colors: Record<string, string> = {
  LOW: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  MEDIUM: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
  HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/40',
  CRITICAL: 'bg-red-500/20 text-red-400 border-red-500/40',
  NONE: 'bg-gray-500/20 text-gray-400 border-gray-500/40',
}

export default function SeverityBadge({ severity }: { severity: string }) {
  const key = severity.toUpperCase()
  return (
    <span className={`inline-flex px-2.5 py-0.5 rounded border text-xs font-semibold ${colors[key] || colors.NONE}`}>
      {severity}
    </span>
  )
}
