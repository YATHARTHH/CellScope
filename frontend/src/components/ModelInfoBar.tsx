import { HealthStatus } from '../types'

interface Props {
  health: HealthStatus | null
  cacheHit?: boolean
  inferenceTimeMs?: number
  inferenceEngine?: string
}

export function ModelInfoBar({
  health,
  cacheHit,
  inferenceTimeMs,
  inferenceEngine,
}: Props) {
  const isHealthy = health?.status === 'ok'

  return (
    <div className="model-bar" id="model-info-bar">
      <div className="model-bar__item">
        <span
          className="model-bar__dot"
          style={{
            background: isHealthy ? 'var(--accent)' : 'var(--error)',
            boxShadow: isHealthy ? '0 0 6px var(--accent)' : '0 0 6px var(--error)',
          }}
        />
        <span className="model-bar__label">System Status:</span>
        <span className="model-bar__value">
          {health ? health.status.toUpperCase() : 'CONNECTING...'}
        </span>
      </div>

      <div className="model-bar__item">
        <span className="model-bar__label">Active Model:</span>
        <span className="model-bar__value">
          {health?.model_version || 'StarDist2D (2D_versatile_fluo)'}
        </span>
      </div>

      <div className="model-bar__item">
        <span className="model-bar__label">Engine:</span>
        <span className="model-bar__value">
          {inferenceEngine || health?.engine || 'native_tf'}
        </span>
      </div>

      {inferenceTimeMs !== undefined && (
        <div className="model-bar__item">
          <span className="model-bar__label">Inference Latency:</span>
          <span className="model-bar__value" style={{ color: 'var(--accent)' }}>
            {inferenceTimeMs} ms
          </span>
        </div>
      )}

      {cacheHit !== undefined && (
        <div className="model-bar__item">
          <span className="model-bar__label">Cache:</span>
          <span
            className="model-bar__value"
            style={{ color: cacheHit ? 'var(--blue)' : 'var(--text-secondary)' }}
          >
            {cacheHit ? 'HIT (SHA-256)' : 'MISS'}
          </span>
        </div>
      )}
    </div>
  )
}
