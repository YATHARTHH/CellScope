import { useState } from 'react'
import { Bot, Send, Sparkles, FileText, HelpCircle, BarChart, Copy, Check } from 'lucide-react'
import { AnalysisResult } from '../types'

interface Message {
  sender: 'user' | 'ai'
  text: string
  timestamp: string
}

interface Props {
  analysisResult: AnalysisResult | null
}

export function AICopilotDrawer({ analysisResult }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'ai',
      text: 'Hello! I am your AI Microscopy Copilot. Ask me to generate manuscript captions, explain circularity/pleomorphism scores, or suggest statistical analysis plans for your sample.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)

  const quickPrompts = [
    { label: 'Manuscript Caption', prompt: 'Generate a manuscript figure caption for this sample.', icon: FileText },
    { label: 'Circularity Score', prompt: 'Explain what the mean circularity score means scientifically.', icon: HelpCircle },
    { label: 'Statistical Advice', prompt: 'What statistical test should I run to compare conditions?', icon: BarChart },
  ]

  const handleSend = async (customPrompt?: string) => {
    const textToSend = customPrompt || input.trim()
    if (!textToSend || loading) return

    const userMsg: Message = {
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages(prev => [...prev, userMsg])
    if (!customPrompt) setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/v1/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: textToSend,
          context: analysisResult
            ? {
                cell_count: analysisResult.cell_count,
                mean_area_px: analysisResult.morphology.mean_area_px,
                mean_area_um2: analysisResult.morphology.mean_area_um2,
                mean_circularity: analysisResult.morphology.mean_circularity,
                density_cells_per_mm2: analysisResult.morphology.density_cells_per_mm2,
                calibrated: analysisResult.calibration.calibrated,
                pixel_size_um: analysisResult.calibration.pixel_size_um,
              }
            : null,
        }),
      })

      const data = await res.json()
      const aiMsg: Message = {
        sender: 'ai',
        text: data.response || 'I analyzed your query.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages(prev => [...prev, aiMsg])
    } catch (_) {
      setMessages(prev => [
        ...prev,
        {
          sender: 'ai',
          text: 'Apologies, I encountered a temporary connection issue. Please try again.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text: string, idx: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx(null), 2000)
  }

  return (
    <div className="card fade-in" style={{ height: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}>
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Bot size={20} style={{ color: '#a78bfa' }} />
          <div>
            <span className="card-title">Ask AI Copilot Assistant</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>
              Scientific interpretation & manuscript caption generation
            </span>
          </div>
        </div>
      </div>

      <div className="card-body" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 16 }}>
        {/* Quick Prompts Bar */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
          {quickPrompts.map((qp, idx) => {
            const Icon = qp.icon
            return (
              <button
                key={idx}
                className="btn btn-ghost"
                onClick={() => handleSend(qp.prompt)}
                disabled={loading}
                style={{ fontSize: 11, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
              >
                <Icon size={12} style={{ color: '#a78bfa' }} /> {qp.label}
              </button>
            )
          })}
        </div>

        {/* Message Stream */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, paddingRight: 4 }}>
          {messages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
              }}
            >
              <div
                style={{
                  background: msg.sender === 'user' ? 'var(--accent-muted)' : 'var(--bg-panel)',
                  border: msg.sender === 'user' ? '1px solid var(--accent-dim)' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '10px 14px',
                  fontSize: 13,
                  color: msg.sender === 'user' ? 'var(--accent)' : 'var(--text-primary)',
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.6,
                  position: 'relative',
                }}
              >
                {msg.text}
                {msg.sender === 'ai' && (
                  <button
                    onClick={() => copyToClipboard(msg.text, idx)}
                    style={{
                      position: 'absolute',
                      top: 6,
                      right: 6,
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                    }}
                    title="Copy to clipboard"
                  >
                    {copiedIdx === idx ? <Check size={12} style={{ color: 'var(--accent)' }} /> : <Copy size={12} />}
                  </button>
                )}
              </div>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start' }}>
                {msg.timestamp}
              </span>
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#a78bfa', fontSize: 12 }}>
              <Sparkles size={14} className="glow-pulse" /> AI Assistant thinking…
            </div>
          )}
        </div>

        {/* Input Form */}
        <form
          onSubmit={e => { e.preventDefault(); handleSend() }}
          style={{ display: 'flex', gap: 8, marginTop: 14 }}
        >
          <input
            className="input"
            type="text"
            placeholder="Ask about your sample, manuscript caption, or statistics..."
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
          />
          <button className="btn btn--primary" type="submit" disabled={loading || !input.trim()}>
            <Send size={14} />
          </button>
        </form>
      </div>
    </div>
  )
}
