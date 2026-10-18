import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Forecast } from '../types'

function formatTime(value: string) {
  if (value.startsWith('+')) return value
  const match = value.match(/^(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?$/i)
  if (!match) return value
  const [, hour, minute, period] = match
  return `${hour.padStart(2, '0')}:${minute}${period ? ` ${period.toUpperCase()}` : ''}`
}

export default function ForecastChart({ forecast }: { forecast: Forecast }) {
  const chartData: Array<{
    time: string
    historical?: number
    current?: number
    forecast?: number
  }> = forecast.historical
    .filter((point) => point.type !== 'current')
    .map((point) => ({ time: formatTime(point.time), historical: point.score }))

  // Use the final measured point as the bridge between historical and forecast lines.
  const currentPoint = chartData.at(-1)
  if (currentPoint) {
    currentPoint.current = forecast.current_score
    currentPoint.forecast = forecast.current_score
  }

  chartData.push(
    ...forecast.forecast_points.map((point) => ({
      time: `+${point.minutes_ahead}m`,
      forecast: point.score,
    })),
  )

  return (
    <div className="w-full">
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" stroke="#6b7280" fontSize={11} />
            <YAxis domain={[0, 100]} stroke="#6b7280" fontSize={11} />
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <Legend />
            <ReferenceLine y={75} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'Critical', fill: '#ef4444', fontSize: 10 }} />
            <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: 'High', fill: '#f59e0b', fontSize: 10 }} />
            <Line type="monotone" dataKey="historical" stroke="#06b6d4" strokeWidth={2} dot={{ r: 4 }} name="Historical" connectNulls />
            <Line type="monotone" dataKey="current" stroke="#8b5cf6" strokeWidth={3} dot={{ r: 6 }} name="Current" connectNulls />
            <Line type="monotone" dataKey="forecast" stroke="#f59e0b" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 4 }} name="Forecast (Prototype)" connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-center text-[10px] leading-4 text-gray-500">
        Conceptual Forecast — {forecast.method}
      </p>
    </div>
  )
}
