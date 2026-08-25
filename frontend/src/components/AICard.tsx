import { Sparkles, CheckCircle, ShieldCheck } from 'lucide-react'

interface Props {
  insights: {
    status: string
    bullets: string[]
    confidence_score: number
  } | null
}

export function AICard({ insights }: Props) {
  if (!insights) return null

  return (
    <div className="ai-card fade-in" id="ai-insights-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: 'rgba(167, 139, 250, 0.2)',
            border: '1px solid rgba(167, 139, 250, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#a78bfa',
          }}>
            <Sparkles size={18} />
          </div>
          <div>
            <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
              AI Diagnostic Findings Summary
            </h4>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Automated morphology & biological health interpretation
            </span>
          </div>
        </div>

        <div style={{
          fontSize: 11,
          fontWeight: 600,
          color: '#a78bfa',
          background: 'rgba(167, 139, 250, 0.12)',
          padding: '4px 10px',
          borderRadius: 100,
          border: '1px solid rgba(167, 139, 250, 0.3)',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}>
          <ShieldCheck size={12} /> {Math.round(insights.confidence_score * 100)}% Confidence
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {insights.bullets.map((bullet, idx) => (
          <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12.5, color: 'var(--text-primary)', lineHeight: 1.5 }}>
            <CheckCircle size={15} style={{ color: '#a78bfa', flexShrink: 0, marginTop: 2 }} />
            <span>{bullet}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
