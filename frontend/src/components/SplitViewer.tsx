import { useState, useRef, useCallback } from 'react'
import { Eye, Layers } from 'lucide-react'

interface Props {
  originalB64: string
  overlayB64: string
}

export function SplitViewer({ originalB64, overlayB64 }: Props) {
  const [sliderPos, setSliderPos] = useState(50)
  const containerRef = useRef<HTMLDivElement>(null)

  const handleMove = useCallback((clientX: number) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = clientX - rect.left
    const pct = Math.max(0, Math.min(100, (x / rect.width) * 100))
    setSliderPos(pct)
  }, [])

  const onMouseMove = (e: React.MouseEvent) => {
    if (e.buttons === 1) handleMove(e.clientX)
  }

  const onTouchMove = (e: React.TouchEvent) => {
    if (e.touches.length > 0) handleMove(e.touches[0].clientX)
  }

  return (
    <div className="card" id="split-viewer-card">
      <div className="card-header">
        <span className="card-title">Interactive Overlay Comparison</span>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-secondary)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Eye size={12} color="var(--text-muted)" /> Left: Raw Image
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Layers size={12} color="var(--accent)" /> Right: StarDist Masks
          </span>
        </div>
      </div>
      <div className="card-body" style={{ padding: 12 }}>
        <div
          ref={containerRef}
          className="split-viewer"
          onMouseMove={onMouseMove}
          onTouchMove={onTouchMove}
          id="split-viewer-container"
        >
          {/* Base: Segmentation overlay */}
          <img
            src={`data:image/png;base64,${overlayB64}`}
            alt="Segmentation Overlay"
            className="split-viewer__image"
          />

          {/* Top clipped: Original image */}
          <div
            className="split-viewer__overlay"
            style={{ width: `${sliderPos}%` }}
          >
            <img
              src={`data:image/png;base64,${overlayB64}`}
              alt="Raw Image"
              className="split-viewer__image"
              style={{
                filter: 'grayscale(100%) contrast(120%)',
                mixBlendMode: 'normal',
              }}
            />
          </div>

          {/* Divider line & handle */}
          <div
            className="split-viewer__divider"
            style={{ left: `${sliderPos}%` }}
          >
            <div className="split-viewer__handle">
              ↔
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
