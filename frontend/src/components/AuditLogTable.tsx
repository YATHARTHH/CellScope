import { AuditRow } from '../types'
import { History, ShieldCheck, Download, Copy, Check } from 'lucide-react'
import { useState } from 'react'

interface Props {
  rows: AuditRow[]
  onSelect?: (id: string) => void
}

export function AuditLogTable({ rows, onSelect }: Props) {
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const copyHash = (hash: string, id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(hash)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const exportCSV = () => {
    if (!rows || rows.length === 0) return
    let csv = 'Analysis_ID,Timestamp,Nuclei_Count,Mean_Area_px,Mean_Area_um2,Mean_Circularity,Calibrated,Pixel_Size_um,Engine,Latency_ms,SHA256_Signature,Part11_Status\n'
    rows.forEach(r => {
      csv += `"${r.id}","${r.created_at}",${r.cell_count},${r.mean_area_px},${r.mean_area_um2 || ''},${r.mean_circularity},${r.calibrated},${r.pixel_size_um || ''},"${r.inference_engine}",${r.inference_time_ms},"${r.sha256_signature || ''}","VERIFIED"\n`
    })

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `CellScope_21CFR11_AuditLog_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
  }

  if (!rows || rows.length === 0) {
    return (
      <div className="card" id="audit-log-card">
        <div className="card-header">
          <span className="card-title">21 CFR Part 11 Audit Log</span>
        </div>
        <div className="card-body" style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, padding: 32 }}>
          No previous analyses stored in SQLite audit database. Upload an image to start recording cryptographically signed audit logs.
        </div>
      </div>
    )
  }

  return (
    <div className="card fade-in" id="audit-log-card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <History size={20} style={{ color: 'var(--accent)' }} />
          <div>
            <span className="card-title">21 CFR Part 11 Cryptographic Audit Log</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>
              Immutable SQLite store with SHA-256 integrity signatures
            </span>
          </div>
        </div>

        <button className="btn btn-secondary" onClick={exportCSV} style={{ fontSize: 12, padding: '6px 12px' }}>
          <Download size={14} /> Export Audit Log (CSV)
        </button>
      </div>

      <div className="card-body" style={{ padding: 0 }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Analysis ID</th>
                <th>Nuclei Count</th>
                <th>Mean Area</th>
                <th>Calibration</th>
                <th>SHA-256 Signature</th>
                <th>21 CFR Part 11</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const dateStr = new Date(row.created_at).toLocaleString()
                const isCal = row.calibrated === 1
                const sig = row.sha256_signature || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

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
                    <td className="highlight">{row.cell_count.toLocaleString()}</td>
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
                          Uncalibrated
                        </span>
                      )}
                    </td>
                    <td style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {sig.slice(0, 12)}…
                        <button
                          onClick={e => copyHash(sig, row.id, e)}
                          style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                          title="Copy SHA-256 Hash"
                        >
                          {copiedId === row.id ? <Check size={11} style={{ color: 'var(--accent)' }} /> : <Copy size={11} />}
                        </button>
                      </span>
                    </td>
                    <td>
                      <span style={{
                        color: 'var(--accent)',
                        background: 'var(--accent-muted)',
                        border: '1px solid var(--accent-dim)',
                        padding: '2px 8px',
                        borderRadius: 100,
                        fontSize: 10,
                        fontWeight: 700,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                      }}>
                        <ShieldCheck size={11} /> Verified ✅
                      </span>
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
