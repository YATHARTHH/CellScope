import { useCallback, useRef, useState } from 'react'
import { Upload, Microscope } from 'lucide-react'

interface Props {
  onUpload: (file: File, pixelSizeUm: number | null) => void
  loading: boolean
  hasResult?: boolean
  onReset?: () => void
}

export function ImageUploader({ onUpload, loading, hasResult, onReset }: Props) {
  const [dragOver, setDragOver] = useState(false)
  const [pixelSizeInput, setPixelSizeInput] = useState('')
  const [pixelSizeError, setPixelSizeError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const resolvePixelSize = (): number | null => {
    const v = pixelSizeInput.trim()
    if (!v) return null
    const n = parseFloat(v)
    if (isNaN(n) || n <= 0) {
      setPixelSizeError('Pixel size must be a positive number (e.g. 0.325)')
      return null
    }
    setPixelSizeError('')
    return n
  }

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return
      const file = files[0]
      const ext = file.name.split('.').pop()?.toLowerCase()
      if (!['tif', 'tiff', 'png', 'jpg', 'jpeg'].includes(ext ?? '')) {
        setPixelSizeError('Unsupported format. Use OME-TIFF, TIFF, PNG, or JPG.')
        return
      }
      const px = resolvePixelSize()
      onUpload(file, px)
      // Reset input value so re-uploading the same or another file triggers onChange cleanly
      if (inputRef.current) {
        inputRef.current.value = ''
      }
    },
    [onUpload, pixelSizeInput]
  )

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      handleFiles(e.dataTransfer.files)
    },
    [handleFiles]
  )

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="card-title">Upload Microscopy Image</span>
        {hasResult && onReset && (
          <button
            className="btn btn-secondary"
            onClick={onReset}
            style={{ fontSize: 12, padding: '4px 12px' }}
          >
            Clear / New Upload
          </button>
        )}
      </div>
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Pixel size input */}
        <div>
          <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
            Pixel size (µm/px) — optional
          </label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              className="input"
              type="number"
              min="0.001"
              step="0.001"
              placeholder="e.g. 0.325 for 20× objective"
              value={pixelSizeInput}
              onChange={e => { setPixelSizeInput(e.target.value); setPixelSizeError('') }}
              style={{ maxWidth: 240 }}
              id="pixel-size-input"
            />
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Leave blank to auto-read from OME-TIFF metadata
            </span>
          </div>
          {pixelSizeError && (
            <p style={{ fontSize: 12, color: 'var(--error)', marginTop: 4 }}>{pixelSizeError}</p>
          )}
        </div>

        {/* Drop zone */}
        <div
          id="image-drop-zone"
          className={`uploader ${dragOver ? 'drag-over' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => !loading && inputRef.current?.click()}
          style={{ cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1 }}
        >
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <div className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
              <p style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 14 }}>
                Segmenting nuclei…
              </p>
              <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                Executing StarDist 2D inference on local CPU
              </p>
            </div>
          ) : (
            <>
              <div className="uploader__icon">
                <Microscope size={48} />
              </div>
              <p className="uploader__title">
                {hasResult ? 'Click or drop a new image to replace current analysis' : 'Drop fluorescence image here'}
              </p>
              <p className="uploader__subtitle">
                2D single-channel nuclear fluorescence (DAPI / Hoechst)
              </p>
              <div className="uploader__formats">
                {['OME-TIFF', '.tif', '.tiff', '.png', '.jpg'].map(f => (
                  <span key={f} className="format-tag">{f}</span>
                ))}
              </div>
              <p style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
                Max 50 MB
              </p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".tif,.tiff,.png,.jpg,.jpeg"
            style={{ display: 'none' }}
            onChange={e => handleFiles(e.target.files)}
            id="image-file-input"
          />
        </div>
      </div>
    </div>
  )
}
