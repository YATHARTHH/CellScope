import { useEffect, useState } from 'react'
import { Microscope, Activity, Database, BarChart2, ShieldCheck, Upload, Bot, FolderArchive, Cpu } from 'lucide-react'

import { AnalysisResult, AuditRow, CellInstance, HealthStatus } from './types'
import { ImageUploader } from './components/ImageUploader'
import { CellMetricsPanel } from './components/CellMetricsPanel'
import { HistogramPanel } from './components/HistogramPanel'
import { SplitViewer } from './components/SplitViewer'
import { AuditLogTable } from './components/AuditLogTable'
import { ModelInfoBar } from './components/ModelInfoBar'
import { SegmentationOverlay } from './components/SegmentationOverlay'

import { AICard } from './components/AICard'
import { AICopilotDrawer } from './components/AICopilotDrawer'
import { BatchProcessingPanel } from './components/BatchProcessingPanel'
import { ModelZooPanel } from './components/ModelZooPanel'

export type TabType = 'analysis' | 'copilot' | 'batch' | 'zoo' | 'history'

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [auditRows, setAuditRows] = useState<AuditRow[]>([])
  const [selectedCell, setSelectedCell] = useState<CellInstance | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('analysis')

  const handleReset = () => {
    setResult(null)
    setError(null)
    setSelectedCell(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Fetch system health on mount
  useEffect(() => {
    fetch('/api/v1/health')
      .then(res => res.json())
      .then(data => setHealth(data))
      .catch(() => setHealth({ status: 'degraded', model_version: 'Offline', engine: 'unknown', timestamp: '' }))

    fetchAuditLogs()
  }, [])

  const fetchAuditLogs = () => {
    fetch('/api/v1/analyses?limit=25')
      .then(res => res.json())
      .then(data => setAuditRows(data.analyses || []))
      .catch(() => {})
  }

  const handleUpload = async (file: File, pixelSizeUm: number | null) => {
    setLoading(true)
    setError(null)
    setSelectedCell(null)

    const formData = new FormData()
    formData.append('file', file)
    if (pixelSizeUm !== null) {
      formData.append('pixel_size_um', pixelSizeUm.toString())
    }

    try {
      const res = await fetch('/api/v1/segment', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Server returned ${res.status}`)
      }

      const data: AnalysisResult = await res.json()
      setResult(data)
      fetchAuditLogs()
    } catch (err: any) {
      setError(err.message || 'Analysis failed. Make sure the backend server is running.')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectAuditRow = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/analyses/${id}`)
      if (res.ok) {
        const data = await res.json()
        setResult(data)
        setActiveTab('analysis')
      }
    } catch (_) {}
  }

  return (
    <div className="app-shell">
      {/* Top Bar */}
      <header className="topbar">
        <div className="topbar-logo">
          <div className="logo-icon">
            <Microscope size={18} />
          </div>
          <span>CellScope</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 6 }}>
            v1.0 (Local CPU)
          </span>
        </div>

        <div className="topbar-spacer" />

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {result && (
            <button
              className="btn btn-secondary"
              onClick={handleReset}
              style={{
                fontSize: 12,
                padding: '6px 14px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                background: 'var(--accent)',
                color: '#090d16',
                fontWeight: 600,
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              <Upload size={14} /> Upload Another Image
            </button>
          )}

          <span style={{
            fontSize: 11,
            color: 'var(--accent)',
            background: 'var(--accent-muted)',
            padding: '4px 10px',
            borderRadius: 100,
            border: '1px solid var(--accent-dim)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}>
            <ShieldCheck size={12} /> Local Offline Deployment
          </span>
        </div>
      </header>

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-section">
          <div className="sidebar-section__title">Navigation</div>
          <div
            className={`sidebar-item ${activeTab === 'analysis' ? 'active' : ''}`}
            onClick={() => setActiveTab('analysis')}
          >
            <Activity /> Single Analysis
          </div>
          <div
            className={`sidebar-item ${activeTab === 'copilot' ? 'active' : ''}`}
            onClick={() => setActiveTab('copilot')}
          >
            <Bot /> Ask AI Copilot
          </div>
          <div
            className={`sidebar-item ${activeTab === 'batch' ? 'active' : ''}`}
            onClick={() => setActiveTab('batch')}
          >
            <FolderArchive /> Batch Processing
          </div>
          <div
            className={`sidebar-item ${activeTab === 'zoo' ? 'active' : ''}`}
            onClick={() => setActiveTab('zoo')}
          >
            <Cpu /> Model Zoo
          </div>
          <div
            className={`sidebar-item ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            <Database /> Audit & Compliance ({auditRows.length})
          </div>
        </div>

        <div className="sidebar-section" style={{ marginTop: 'auto' }}>
          <div className="sidebar-section__title">Dataset Specification</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <strong>Primary:</strong> BBBC039v1 (CC0)<br />
            <strong>Modality:</strong> 2D Nuclear Fluo<br />
            <strong>Engine:</strong> StarDist 2D<br />
            <strong>Baseline:</strong> Cellpose 3.x
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <ModelInfoBar
          health={health}
          cacheHit={result?.cache_hit}
          inferenceTimeMs={result?.inference_time_ms}
          inferenceEngine={result?.inference_engine}
        />

        {error && (
          <div style={{
            background: 'rgba(248, 113, 113, 0.1)',
            border: '1px solid var(--error)',
            color: 'var(--error)',
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            fontSize: 13,
          }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {activeTab === 'analysis' && (
          <>
            {/* Upload Area */}
            <ImageUploader
              onUpload={handleUpload}
              loading={loading}
              hasResult={!!result}
              onReset={handleReset}
            />

            {/* Results Grid */}
            {result && (
              <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {result.ai_insights && <AICard insights={result.ai_insights} />}

                <CellMetricsPanel
                  cellCount={result.cell_count}
                  morphology={result.morphology}
                  calibration={result.calibration}
                  selectedCell={selectedCell}
                  onReset={handleReset}
                />

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                  <SegmentationOverlay
                    overlayB64={result.annotated_image_b64}
                    maskB64={result.segmentation_mask_b64}
                    cells={result.cells}
                    isCalibrated={result.calibration.calibrated}
                    onCellHover={setSelectedCell}
                    onCellSelect={setSelectedCell}
                  />

                  <SplitViewer
                    originalB64={result.annotated_image_b64}
                    overlayB64={result.annotated_image_b64}
                  />
                </div>

                <HistogramPanel
                  cells={result.cells}
                  isCalibrated={result.calibration.calibrated}
                />
              </div>
            )}
          </>
        )}

        {activeTab === 'copilot' && (
          <AICopilotDrawer analysisResult={result} />
        )}

        {activeTab === 'batch' && (
          <BatchProcessingPanel />
        )}

        {activeTab === 'zoo' && (
          <ModelZooPanel />
        )}

        {activeTab === 'history' && (
          <AuditLogTable rows={auditRows} onSelect={handleSelectAuditRow} />
        )}
      </main>
    </div>
  )
}
