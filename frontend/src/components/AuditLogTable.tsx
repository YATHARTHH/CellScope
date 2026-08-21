import { AuditRow } from '../types'
import { History, CheckCircle, Clock } from 'lucide-react'

interface Props {
  rows: AuditRow[]
  onSelect?: (id: string) => void
}

export function AuditLogTable({ rows, onSelect }: Props) {
  if (!rows || rows.length === 0) {
    return (
      <div className="card" id="audit-log-card">
        <div className="card-header">
          <span className="card-title">Recent Analysis History</span>
        </div>
        <div className="card-body" style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, padding: 32 }}>
          No previous analyses stored in SQLite. Upload an image to start recording audit logs.
        </div>
      </div>
    )
  }

  return (
    <div className="card" id="audit-log-card">
      <div className="card-header">
        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <History size={14} /> Audit Log (SQLite Store)
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Last {rows.length} analyses</span>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Analysis ID</th>
                <th>Count</th>
                <th>Mean Area</th>
                <th>Calibration</th>
                <th>Engine</th>
                <th>Latency</th>
                <th>Cache</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const dateStr = new Date(row.created_at).toLocaleTimeString()
                const isCal = row.calibrated === 1

                return (
                  <tr
                    key={row.id}
                    onClick={() => onSelect && onSelect(row.id)}
                    style={{ cursor: onSelect ? 'pointer' : 'default' }}
                  >
                    <td style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>{dateStr}</td>
                    <td style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {row.id.slice(0, 8)}…
                    </td>
                    <td className="highlight">{row.cell_count}</td>
                    <td>
                      {isCal && row.mean_area_um2 !== null
                        ? `${row.mean_area_um2} µm²`
                        : `${row.mean_area_px} px²`}
                    </td>
                    <td>
                      {isCal ? (
                        <span style={{ color: 'var(--accent)', fontSize: 11 }}>
                          {row.pixel_size_um} µm/px
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                          Pixels only
                        </span>
                      )}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{row.inference_engine}</td>
                    <td style={{ fontSize: 11 }}>{row.inference_time_ms} ms</td>
                    <td>
                      {row.cache_hit === 1 ? (
                        <span style={{ color: 'var(--blue)', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <Clock size={10} /> Hit
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <CheckCircle size={10} /> Miss
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
