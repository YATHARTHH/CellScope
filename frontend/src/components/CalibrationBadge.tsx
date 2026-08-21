import { CalibrationInfo } from '../types'
import { Ruler, AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  calibration: CalibrationInfo
  onOverride?: (px: number) => void
}

const SOURCE_LABELS: Record<string, string> = {
  ome_tiff_metadata: 'OME-TIFF metadata',
  user_provided:     'User provided',
  unavailable:       'Unavailable',
}

export function CalibrationBadge({ calibration, onOverride }: Props) {
  const { calibrated, pixel_size_um, source } = calibration

  return (
    <div
      className={`calibration-badge ${calibrated ? 'calibration-badge--calibrated' : 'calibration-badge--uncalibrated'}`}
      title={`Source: ${SOURCE_LABELS[source] ?? source}`}
      id="calibration-badge"
    >
      {calibrated ? (
        <>
          <Ruler size={12} />
          <span>{pixel_size_um?.toFixed(4)} µm/px</span>
          <span style={{ opacity: 0.7, fontSize: 10 }}>({SOURCE_LABELS[source]})</span>
        </>
      ) : (
        <>
          <AlertTriangle size={12} />
          <span>Pixel units only</span>
          <span style={{ opacity: 0.7, fontSize: 10 }}>— physical size unknown</span>
        </>
      )}
    </div>
  )
}
