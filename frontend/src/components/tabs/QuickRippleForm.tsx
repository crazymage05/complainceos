import { useState } from 'react'

const QUICK_EXAMPLES = [
  { label: 'GST rate change', text: 'GST rate revised for restaurants and food services under QRMP scheme' },
  { label: 'EPF wage ceiling', text: 'EPF wage ceiling enhanced — EPFO circular increases monthly PF contribution base' },
  { label: 'FSSAI deadline', text: 'FSSAI annual return deadline extended — FoSCoS portal update for food businesses' },
  { label: 'TDS threshold', text: 'TDS threshold revised under Income Tax Act — new slab rates for FY 2026-27' },
]

interface Props {
  onCheck: (description: string, effectiveDate: string) => void
  loading: boolean
  compact?: boolean
}

export default function QuickRippleForm({ onCheck, loading, compact = false }: Props) {
  const today = new Date().toISOString().split('T')[0]
  const [description, setDescription] = useState('')
  const [effectiveDate, setEffectiveDate] = useState(today)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!description.trim()) return
    onCheck(description.trim(), effectiveDate)
  }

  return (
    <form onSubmit={handleSubmit} className="os-card p-4 space-y-3">
      {!compact && (
        <div>
          <p className="text-xs font-semibold text-inkMute uppercase tracking-wide mb-2">Quick examples</p>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => setDescription(ex.text)}
                className="text-xs px-2.5 py-1 bg-accent/10 text-accent-soft border border-accent/20 rounded-full hover:bg-accent/20 transition-colors font-medium"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {compact && (
        <div className="flex flex-wrap gap-1.5 mb-1">
          {QUICK_EXAMPLES.slice(0, 2).map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => setDescription(ex.text)}
              className="text-xs px-2 py-0.5 bg-accent/10 text-accent-soft border border-accent/20 rounded-full hover:bg-accent/20 transition-colors"
            >
              {ex.label}
            </button>
          ))}
        </div>
      )}

      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Describe the regulation change… e.g. GST rate revised for e-commerce operators"
        rows={compact ? 2 : 3}
        className="w-full os-input px-3 py-2 text-sm resize-none"
      />

      <div className="flex items-center gap-2">
        <input
          type="date"
          value={effectiveDate}
          onChange={(e) => setEffectiveDate(e.target.value)}
          className="os-input px-3 py-1.5 text-xs [color-scheme:dark]"
        />
        <button
          type="submit"
          disabled={loading || !description.trim()}
          className="os-btn-accent flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs"
        >
          {loading ? (
            <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          )}
          {loading ? 'Analysing…' : 'Run Ripple Check'}
        </button>
      </div>
    </form>
  )
}
