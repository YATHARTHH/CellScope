import { useState } from 'react'
import { CellInstance } from '../types'

interface Props {
  overlayB64: string
  maskB64: string
  cells: CellInstance[]
  isCalibrated: boolean
  onCellHover?: (cell: CellInstance | null) => void
  onCellSelect?: (cell: CellInstance | null) => void
}

export function SegmentationOverlay({
  overlayB64,
  maskB64,
  cells,
  isCalibrated,
  onCellHover,
  onCellSelect,
}: Props) {
  const [activeView, setActiveView] = useState<'overlay' | 'mask'>('overlay')
  const [hoveredCell, setHoveredCell] = useState<CellInstance | null>(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })

  const currentB64 = activeView === 'overlay' ? overlayB64 : maskB64

  return (
    <div className="card" id="segmentation-overlay-card">
      <div className="card-header">
        <span className="card-title">Segmentation Canvas</span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            className={`btn ${activeView === 'overlay' ? 'btn--primary' : 'btn--ghost'}`}
            onClick={() => setActiveView('overlay')}
            style={{ padding: '4px 12px', fontSize: 11 }}
          >
            Composite Overlay
          </button>
          <button
            className={`btn ${activeView === 'mask' ? 'btn--primary' : 'btn--ghost'}`}
            onClick={() => setActiveView('mask')}
            style={{ padding: '4px 12px', fontSize: 11 }}
          >
            Instance Masks
          </button>
        </div>
      </div>
      <div className="card-body" style={{ padding: 12, position: 'relative' }}>
        <div
          style={{ position: 'relative', overflow: 'hidden', borderRadius: 'var(--radius-md)' }}
          onMouseMove={e => {
            setMousePos({ x: e.clientX, y: e.clientY })
          }}
          onMouseLeave={() => {
            setHoveredCell(null)
            if (onCellHover) onCellHover(null)
          }}
        >
          <img
            src={`data:image/png;base64,${currentB64}`}
            alt="Segmentation Result"
            style={{ display: 'block', width: '100%', height: 'auto', borderRadius: 'var(--radius-md)' }}
          />
        </div>

        {/* Hover Tooltip */}
        {hoveredCell && (
          <div
            className="cell-tooltip fade-in"
            style={{
              top: mousePos.y + 12,
              left: mousePos.x + 12,
            }}
          >
            <div className="cell-tooltip__id">Nucleus #{hoveredCell.cell_id}</div>
            <div className="cell-tooltip__row">
              <span>Area:</span>
              <strong>
                {isCalibrated && hoveredCell.area_um2 !== null
                  ? `${hoveredCell.area_um2} µm²`
                  : `${hoveredCell.area_px} px²`}
              </strong>
            </div>
            <div className="cell-tooltip__row">
              <span>Circularity:</span>
              <strong>{hoveredCell.circularity.toFixed(3)}</strong>
            </div>
            <div className="cell-tooltip__row">
              <span>Mean Intensity:</span>
              <strong>{hoveredCell.mean_intensity.toFixed(1)}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
