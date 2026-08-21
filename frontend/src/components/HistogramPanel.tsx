import { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { CellInstance } from '../types'

interface Props {
  cells: CellInstance[]
  isCalibrated: boolean
}

export function HistogramPanel({ cells, isCalibrated }: Props) {
  const data = useMemo(() => {
    if (!cells || cells.length === 0) return []

    const values = cells.map(c =>
      isCalibrated && c.area_um2 !== null ? c.area_um2 : c.area_px
    )

    const min = Math.min(...values)
    const max = Math.max(...values)
    const binCount = 15
    const step = (max - min) / binCount || 1

    const bins = Array.from({ length: binCount }, (_, i) => {
      const binStart = min + i * step
      const binEnd = min + (i + 1) * step
      return {
        label: `${Math.round(binStart)}–${Math.round(binEnd)}`,
        rangeStart: binStart,
        rangeEnd: binEnd,
        count: 0,
      }
    })

    values.forEach(v => {
      const idx = Math.min(
        Math.floor((v - min) / step),
        binCount - 1
      )
      if (idx >= 0 && idx < binCount) {
        bins[idx].count += 1
      }
    })

    return bins
  }, [cells, isCalibrated])

  if (!cells || cells.length === 0) return null

  const unit = isCalibrated ? 'µm²' : 'px²'

  return (
    <div className="card" id="histogram-panel">
      <div className="card-header">
        <span className="card-title">Nuclear Area Distribution ({unit})</span>
      </div>
      <div className="card-body" style={{ height: 220, padding: '16px 8px 8px 8px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: '#8ba4be', fontSize: 10 }}
              axisLine={{ stroke: '#1e3448' }}
              tickLine={false}
              angle={-20}
              textAnchor="end"
            />
            <YAxis
              tick={{ fill: '#8ba4be', fontSize: 10 }}
              axisLine={{ stroke: '#1e3448' }}
              tickLine={false}
              allowDecimals={false}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload
                  return (
                    <div style={{
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border)',
                      padding: '8px 12px',
                      borderRadius: 6,
                      fontSize: 12,
                      color: 'var(--text-primary)',
                    }}>
                      <div><strong>Range:</strong> {d.label} {unit}</div>
                      <div><strong>Nuclei Count:</strong> {d.count}</div>
                    </div>
                  )
                }
                return null
              }}
            />
            <Bar dataKey="count" fill="var(--accent)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
