import { CellInstance, Morphology, CalibrationInfo } from '../types'
import { CalibrationBadge } from './CalibrationBadge'

interface Props {
  cellCount: number
  morphology: Morphology
  calibration: CalibrationInfo
  selectedCell?: CellInstance | null
  onReset?: () => void
}

export function CellMetricsPanel({
  cellCount,
  morphology,
  calibration,
  selectedCell,
  onReset,
}: Props) {
  const isCalibrated = calibration.calibrated

  return (
    <div className="card" id="cell-metrics-panel">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="card-title">Quantitative Summary</span>
          <CalibrationBadge calibration={calibration} />
        </div>
      </div>
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Primary Stat Tiles */}
        <div className="stat-grid">
          <div className="stat-tile">
            <span className="stat-tile__label">Nuclei Count</span>
            <span className="stat-tile__value">{cellCount.toLocaleString()}</span>
            <span className="stat-tile__unit">detected instances</span>
          </div>

          <div className="stat-tile">
            <span className="stat-tile__label">Mean Area</span>
            {isCalibrated && morphology.mean_area_um2 !== null ? (
              <>
                <span className="stat-tile__value">{morphology.mean_area_um2.toFixed(1)}</span>
                <span className="stat-tile__unit">µm² / nucleus</span>
              </>
            ) : (
              <>
                <span className="stat-tile__value">{morphology.mean_area_px.toFixed(1)}</span>
                <span className="stat-tile__unit">px² / nucleus</span>
              </>
            )}
          </div>

          <div className="stat-tile">
            <span className="stat-tile__label">Mean Circularity</span>
            <span className="stat-tile__value">{morphology.mean_circularity.toFixed(2)}</span>
            <span className="stat-tile__unit">0–1 score (1 = circle)</span>
          </div>

          <div className="stat-tile">
            <span className="stat-tile__label">Nuclear Density</span>
            {isCalibrated && morphology.density_cells_per_mm2 !== null ? (
              <>
                <span className="stat-tile__value">{morphology.density_cells_per_mm2.toLocaleString()}</span>
                <span className="stat-tile__unit">cells / mm²</span>
              </>
            ) : (
              <>
                <span className="stat-tile__value" style={{ fontSize: 18, color: 'var(--text-muted)' }}>Uncalibrated</span>
                <span className="stat-tile__unit">requires µm scale</span>
              </>
            )}
          </div>
        </div>

        {/* Selected Cell Inspection Card */}
        {selectedCell ? (
          <div style={{
            background: 'var(--bg-panel)',
            border: '1px solid var(--accent-dim)',
            borderRadius: 'var(--radius-md)',
            padding: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                Inspect Nucleus #{selectedCell.cell_id}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Centroid: ({selectedCell.centroid_x}, {selectedCell.centroid_y})
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 4 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Area</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {isCalibrated && selectedCell.area_um2 !== null
                    ? `${selectedCell.area_um2} µm²`
                    : `${selectedCell.area_px} px²`}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Circularity</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {selectedCell.circularity.toFixed(3)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Mean Intensity</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {selectedCell.mean_intensity.toFixed(1)}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{
            fontSize: 12,
            color: 'var(--text-muted)',
            fontStyle: 'italic',
            textAlign: 'center',
            padding: '8px 0',
          }}>
            Hover or click on any nucleus in the segmentation overlay to inspect individual metrics.
          </div>
        )}
      </div>
    </div>
  )
}
