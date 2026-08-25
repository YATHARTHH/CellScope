import { useState, useRef } from 'react'
import { FolderArchive, Upload, Download, Printer, CheckCircle, AlertTriangle } from 'lucide-react'

interface BatchItem {
  filename: string
  cell_count: number
  mean_area_px: number
  mean_area_um2: number | null
  mean_circularity: number
  inference_time_ms: number
  calibrated: boolean
  error?: string
}

interface BatchResult {
  total_images: number
  total_cells: number
  mean_cells_per_image: number
  mean_area_px: number
  mean_area_um2: number | null
  mean_circularity: number
  items: BatchItem[]
}

export function BatchProcessingPanel() {
  const [loading, setLoading] = useState(false)
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleBatchUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setLoading(true)
    setError(null)

    const formData = new FormData()
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i])
    }

    try {
      const res = await fetch('/api/v1/segment_batch', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Batch request failed with status ${res.status}`)
      }

      const data: BatchResult = await res.json()
      setBatchResult(data)
    } catch (err: any) {
      setError(err.message || 'Batch segmentation failed.')
    } finally {
      setLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const exportCSV = () => {
    if (!batchResult) return
    let csv = 'Filename,Nuclei_Count,Mean_Area_px,Mean_Area_um2,Mean_Circularity,Latency_ms,Calibrated,Error\n'
    batchResult.items.forEach(item => {
      csv += `"${item.filename}",${item.cell_count},${item.mean_area_px},${item.mean_area_um2 || ''},${item.mean_circularity},${item.inference_time_ms || 0},${item.calibrated},"${item.error || ''}"\n`
    })

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `CellScope_Batch_Report_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
  }

  const printReport = () => {
    window.print()
  }

  return (
    <div className="card fade-in" id="batch-processing-panel">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <FolderArchive size={20} style={{ color: 'var(--accent)' }} />
          <div>
            <span className="card-title">Batch Microscopy Segmentation</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>
              Process up to 50 images in parallel with automated quantitative summary
            </span>
          </div>
        </div>

        {batchResult && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary" onClick={exportCSV} style={{ fontSize: 12, padding: '6px 12px' }}>
              <Download size={14} /> Export Batch CSV
            </button>
            <button className="btn btn-primary" onClick={printReport} style={{ fontSize: 12, padding: '6px 12px' }}>
              <Printer size={14} /> Print Lab Report
            </button>
          </div>
        )}
      </div>

      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Upload Zone */}
        <div
          className="uploader"
          onClick={() => !loading && fileInputRef.current?.click()}
          style={{ cursor: loading ? 'not-allowed' : 'pointer', padding: '36px 20px' }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".tif,.tiff,.png,.jpg,.jpeg"
            style={{ display: 'none' }}
            onChange={e => handleBatchUpload(e.target.files)}
          />
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <div className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
              <p style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 14 }}>
                Segmenting batch images…
              </p>
            </div>
          ) : (
            <>
              <div className="uploader__icon">
                <Upload size={40} />
              </div>
              <p className="uploader__title">
                Click or drop multiple microscopy images (Up to 50 files)
              </p>
              <p className="uploader__subtitle">
                Supports .tif, .tiff, .png, .jpg single-channel fluorescence files
              </p>
            </>
          )}
        </div>

        {error && (
          <div style={{ color: 'var(--error)', fontSize: 13, background: 'rgba(248,113,113,0.1)', padding: 12, borderRadius: 8 }}>
            {error}
          </div>
        )}

        {/* Batch Results Overview */}
        {batchResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="stat-grid">
              <div className="stat-tile">
                <span className="stat-tile__label">Total Images</span>
                <span className="stat-tile__value">{batchResult.total_images}</span>
                <span className="stat-tile__unit">processed fields</span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile__label">Total Nuclei</span>
                <span className="stat-tile__value">{batchResult.total_cells.toLocaleString()}</span>
                <span className="stat-tile__unit">detected instances</span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile__label">Mean Nuclei / Field</span>
                <span className="stat-tile__value">{batchResult.mean_cells_per_image}</span>
                <span className="stat-tile__unit">cells / image</span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile__label">Mean Circularity</span>
                <span className="stat-tile__value">{batchResult.mean_circularity}</span>
                <span className="stat-tile__unit">0–1 roundness</span>
              </div>
            </div>

            {/* Per-File Summary Table */}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Nuclei Count</th>
                    <th>Mean Area (px²)</th>
                    <th>Mean Area (µm²)</th>
                    <th>Mean Circularity</th>
                    <th>Latency</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {batchResult.items.map((item, idx) => (
                    <tr key={idx}>
                      <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.filename}</td>
                      <td className="highlight">{item.cell_count.toLocaleString()}</td>
                      <td>{item.mean_area_px.toFixed(1)}</td>
                      <td>{item.mean_area_um2 ? `${item.mean_area_um2.toFixed(1)} µm²` : 'Uncalibrated'}</td>
                      <td>{item.mean_circularity.toFixed(2)}</td>
                      <td>{item.inference_time_ms ? `${item.inference_time_ms.toFixed(0)} ms` : '—'}</td>
                      <td>
                        {item.error ? (
                          <span style={{ color: 'var(--error)', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <AlertTriangle size={12} /> Error
                          </span>
                        ) : (
                          <span style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <CheckCircle size={12} /> Success
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
