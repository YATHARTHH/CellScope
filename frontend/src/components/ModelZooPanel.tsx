import { useEffect, useState } from 'react'
import { Cpu, CheckCircle, Zap, ShieldCheck } from 'lucide-react'

interface ModelInfo {
  key: string
  name: string
  architecture: string
  dataset: string
  ap50: number
  f1_score: number
  count_error: string
  avg_latency_ms: number
  status: string
}

export function ModelZooPanel() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [activeModel, setActiveModel] = useState<string>('stardist_finetuned')
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchModels()
  }, [])

  const fetchModels = () => {
    fetch('/api/v1/models')
      .then(res => res.json())
      .then(data => {
        setModels(data.models || [])
        setActiveModel(data.active_model || 'stardist_finetuned')
      })
      .catch(() => setError('Failed to load Model Zoo details.'))
  }

  const handleSwitch = async (key: string) => {
    if (key === 'cellpose_baseline') {
      alert('CellPose 3.x is kept as an offline benchmark baseline (51.0s latency). StarDist models are recommended for local CPU deployment.')
      return
    }

    setLoading(key)
    setError(null)

    try {
      const res = await fetch('/api/v1/models/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_key: key }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to switch model.')
      }

      const data = await res.json()
      setActiveModel(data.active_model)
    } catch (err: any) {
      setError(err.message || 'Model switch failed.')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="card fade-in" id="model-zoo-panel">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Cpu size={20} style={{ color: 'var(--accent)' }} />
          <div>
            <span className="card-title">Model Zoo & Inference Engines</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>
              Compare benchmark AP50 precision, F1 score, latency, and toggle active model
            </span>
          </div>
        </div>
      </div>

      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {error && (
          <div style={{ color: 'var(--error)', fontSize: 13, background: 'rgba(248,113,113,0.1)', padding: 12, borderRadius: 8 }}>
            {error}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
          {models.map(m => {
            const isActive = activeModel === m.key
            const isFinetuned = m.key === 'stardist_finetuned'

            return (
              <div
                key={m.key}
                style={{
                  background: isActive ? 'rgba(74, 222, 128, 0.06)' : 'var(--bg-panel)',
                  border: isActive ? '2px solid var(--accent)' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: 20,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                  position: 'relative',
                  boxShadow: isActive ? '0 0 24px rgba(74, 222, 128, 0.15)' : 'none',
                }}
              >
                {isActive && (
                  <div style={{
                    position: 'absolute',
                    top: 12,
                    right: 12,
                    background: 'var(--accent-muted)',
                    color: 'var(--accent)',
                    border: '1px solid var(--accent-dim)',
                    padding: '3px 10px',
                    borderRadius: 100,
                    fontSize: 11,
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}>
                    <CheckCircle size={12} /> Active Engine
                  </div>
                )}

                <div>
                  <div style={{ fontSize: 11, color: isFinetuned ? '#a78bfa' : 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                    {m.status}
                  </div>
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginTop: 4 }}>
                    {m.name}
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                    {m.architecture}
                  </p>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, background: 'var(--bg-elevated)', padding: 12, borderRadius: 8 }}>
                  <div>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block' }}>AP50 Precision</span>
                    <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>{(m.ap50 * 100).toFixed(1)}%</span>
                  </div>
                  <div>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block' }}>Instance F1</span>
                    <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--blue)' }}>{(m.f1_score * 100).toFixed(1)}%</span>
                  </div>
                  <div>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block' }}>Count Rel. Error</span>
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{m.count_error}</span>
                  </div>
                  <div>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block' }}>Latency / Image</span>
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{m.avg_latency_ms} ms</span>
                  </div>
                </div>

                <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  <strong>Dataset & Weight Origin:</strong> {m.dataset}
                </div>

                <button
                  className={`btn ${isActive ? 'btn--ghost' : 'btn--primary'}`}
                  disabled={isActive || loading === m.key}
                  onClick={() => handleSwitch(m.key)}
                  style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}
                >
                  {loading === m.key ? (
                    'Switching Engine…'
                  ) : isActive ? (
                    'Currently Active'
                  ) : (
                    <>
                      <Zap size={14} /> Activate Engine
                    </>
                  )}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
