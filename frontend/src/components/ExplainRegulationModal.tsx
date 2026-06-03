import { useEffect, useRef, useState } from 'react'
import { explainRegulation, type RagAnswer } from '../services/api'

interface Props {
  open: boolean
  onClose: () => void
  businessId: string
  initialQuestion?: string
}

export default function ExplainRegulationModal({ open, onClose, businessId, initialQuestion }: Props) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState<RagAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const lastRun = useRef<string | null>(null)

  async function run(q: string) {
    if (!q.trim()) return
    setLoading(true)
    setError(null)
    setAnswer(null)
    try {
      const res = await explainRegulation(q.trim(), businessId || undefined)
      setAnswer(res)
    } catch (err: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const status = (err as any)?.response?.status
      setError(status === 429
        ? "Gemini's free-tier daily quota is exhausted. Try again after it resets, or add a paid key."
        : 'Could not fetch an answer — please try again.')
    } finally {
      setLoading(false)
    }
  }

  // Auto-run when opened with a seeded question.
  useEffect(() => {
    if (open && initialQuestion && lastRun.current !== initialQuestion) {
      lastRun.current = initialQuestion
      setQuestion(initialQuestion)
      run(initialQuestion)
    }
    if (!open) {
      lastRun.current = null
      setAnswer(null)
      setError(null)
      setQuestion('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialQuestion])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative os-panel shadow-glow w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-edge sticky top-0 bg-panel">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-accent-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093M12 17h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="font-bold text-ink">Ask the regulatory corpus</h2>
          </div>
          <button onClick={onClose} className="text-inkFaint hover:text-ink transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <div className="p-6 space-y-4">
          <form onSubmit={(e) => { e.preventDefault(); run(question) }} className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What is GSTR-9 and when is it due?"
              className="os-input flex-1 px-3 py-2.5 text-sm"
            />
            <button type="submit" disabled={loading || !question.trim()} className="os-btn-accent px-4 py-2.5 text-sm flex items-center gap-2">
              {loading && <span className="w-4 h-4 border-2 border-canvas border-t-transparent rounded-full animate-spin" />}
              Ask
            </button>
          </form>

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>
          )}

          {loading && !answer && (
            <div className="space-y-2 animate-pulse">
              <div className="h-3 bg-white/10 rounded w-full" />
              <div className="h-3 bg-white/10 rounded w-5/6" />
              <div className="h-3 bg-white/5 rounded w-2/3" />
            </div>
          )}

          {answer && (
            <div className="space-y-4">
              <div className="os-card p-4">
                <p className="text-sm text-inkSoft leading-relaxed whitespace-pre-wrap">{answer.answer}</p>
              </div>
              {answer.citations.length > 0 && (
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-inkFaint mb-2">
                    Grounded in {answer.citations.length} regulation{answer.citations.length === 1 ? '' : 's'} · {answer.retrieval_method}
                  </p>
                  <div className="space-y-1.5">
                    {answer.citations.map((c) => (
                      <div key={c.label} className="flex items-start gap-2 text-xs bg-panel2 border border-edge rounded-lg px-3 py-2">
                        <span className="font-bold text-accent-soft flex-shrink-0">[{c.label}]</span>
                        <div className="min-w-0">
                          <p className="text-inkSoft font-medium">{c.name}</p>
                          <p className="text-inkFaint text-[10px] mt-0.5">
                            {c.category}{c.found_by?.length ? ` · found by ${c.found_by.join(' + ')}` : ''}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
