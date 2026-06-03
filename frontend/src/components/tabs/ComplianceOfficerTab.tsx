import { useRef, useState } from 'react'
import clsx from 'clsx'
import { streamAgent, type AgentEvent } from '../../services/api'

interface Props {
  businessId: string
  businessName: string
}

interface Turn {
  question: string
  steps: { author: string; text?: string; tool?: string }[]
  answer: string
  error?: string
  done: boolean
}

const SUGGESTIONS = [
  "What's most urgent this week?",
  'Which obligations carry imprisonment risk?',
  'How much could I owe if I miss everything?',
  'Prepare a filing for my most overdue item',
]

export default function ComplianceOfficerTab({ businessId, businessName }: Props) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  function scrollToEnd() {
    requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }))
  }

  // Translate raw Gemini/agent errors into plain language, and flag the
  // transient ones (503 high-demand) that are worth auto-retrying.
  function classifyError(raw: string): { text: string; transient: boolean } {
    const m = (raw || '').toLowerCase()
    if (m.includes('503') || m.includes('unavailable') || m.includes('overload') || m.includes('high demand')) {
      return { text: 'Gemini is busy right now (high demand) — retrying…', transient: true }
    }
    if (m.includes('429') || m.includes('quota') || m.includes('resource_exhausted') || m.includes('rate')) {
      return { text: "Gemini's free-tier daily limit is reached. Try again after it resets, or add a paid API key.", transient: false }
    }
    return { text: 'The agent hit a problem. Please tap send to try again.', transient: false }
  }

  // Run one streamed agent turn into turns[idx]; returns whether it ended in a
  // transient (retryable) error.
  async function runTurn(idx: number, q: string): Promise<boolean> {
    let transient = false
    try {
      await streamAgent(q, businessId || undefined, (ev: AgentEvent) => {
        if (ev.kind === 'error') {
          const c = classifyError(ev.message || '')
          if (c.transient) transient = true
          setTurns((prev) => { const n = [...prev]; n[idx] = { ...n[idx], error: c.text, done: true }; return n })
        } else if (ev.kind === 'final') {
          setTurns((prev) => { const n = [...prev]; n[idx] = { ...n[idx], answer: ev.answer || n[idx].answer || '(no answer returned)', done: true }; return n })
        } else {
          setTurns((prev) => {
            const n = [...prev]; const t = { ...n[idx] }
            for (const p of (ev.parts ?? []).filter((x) => x.text?.trim())) t.steps = [...t.steps, { author: ev.author || 'agent', text: p.text }]
            for (const p of (ev.parts ?? []).filter((x) => x.tool)) t.steps = [...t.steps, { author: ev.author || 'agent', tool: p.tool }]
            n[idx] = t; return n
          })
        }
        scrollToEnd()
      })
    } catch (e) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const c = classifyError(String((e as any)?.message ?? e))
      if (c.transient) transient = true
      setTurns((prev) => { const n = [...prev]; n[idx] = { ...n[idx], error: c.text, done: true }; return n })
    }
    return transient
  }

  async function ask(question: string) {
    if (!question.trim() || busy) return
    const q = question.trim()
    setInput('')
    setBusy(true)
    const idx = turns.length
    setTurns((prev) => [...prev, { question: q, steps: [], answer: '', done: false }])
    scrollToEnd()

    let transient = await runTurn(idx, q)
    // One automatic retry for a transient 503/high-demand blip.
    if (transient) {
      await new Promise((r) => setTimeout(r, 1500))
      setTurns((prev) => { const n = [...prev]; n[idx] = { question: q, steps: [], answer: '', done: false }; return n })
      scrollToEnd()
      transient = await runTurn(idx, q)
    }

    setBusy(false)
    setTurns((prev) => { const n = [...prev]; if (n[idx] && !n[idx].done) n[idx] = { ...n[idx], done: true }; return n })
    scrollToEnd()
  }

  return (
    <div className="os-panel flex flex-col h-[70vh]">
      {/* Header */}
      <div className="px-5 py-3 border-b border-edge flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-accent/15 flex items-center justify-center">
          <svg className="w-4 h-4 text-accent-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 2l7 3v6c0 4.4-3 8.5-7 9.9C8 19.5 5 15.4 5 11V5l7-3z" /></svg>
        </div>
        <div>
          <p className="text-sm font-bold text-ink leading-none">Compliance Officer</p>
          <p className="text-[11px] text-inkFaint mt-0.5">Multi-agent · {businessName}</p>
        </div>
      </div>

      {/* Conversation */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-5">
        {turns.length === 0 && (
          <div className="text-center text-inkFaint py-8">
            <p className="text-sm text-inkMute mb-4">Ask your AI compliance officer anything about your obligations.</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => ask(s)} className="text-xs px-3 py-1.5 rounded-full bg-white/5 border border-edge text-inkMute hover:bg-white/10 transition-colors">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <div key={i} className="space-y-3">
            {/* User */}
            <div className="flex justify-end">
              <div className="max-w-[80%] bg-accent/15 border border-accent/25 rounded-2xl rounded-br-sm px-4 py-2.5">
                <p className="text-sm text-inkSoft">{t.question}</p>
              </div>
            </div>

            {/* Agent reasoning */}
            {t.steps.length > 0 && (
              <details className="group" open={!t.done}>
                <summary className="cursor-pointer text-[11px] font-semibold text-inkFaint hover:text-inkMute flex items-center gap-1.5">
                  <span className={clsx('w-1.5 h-1.5 rounded-full', t.done ? 'bg-inkFaint' : 'bg-accent animate-pulse')} />
                  {t.done ? `${t.steps.length} reasoning steps` : 'Thinking…'}
                </summary>
                <div className="mt-2 ml-3 pl-3 border-l border-edge space-y-1.5">
                  {t.steps.map((s, j) => (
                    <div key={j} className="text-xs">
                      {s.tool ? (
                        <span className="text-inkFaint">→ <span className="font-mono text-accent-soft/80">{s.author}</span> called <span className="font-mono">{s.tool}</span></span>
                      ) : (
                        <span className="text-inkMute"><span className="font-mono text-accent-soft/80">{s.author}</span>: {s.text}</span>
                      )}
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* Answer */}
            {t.error ? (
              <div className="rounded-2xl rounded-bl-sm border border-red-500/30 bg-red-500/10 px-4 py-2.5 max-w-[85%]">
                <p className="text-sm text-red-300">{t.error}</p>
              </div>
            ) : t.answer ? (
              <div className="rounded-2xl rounded-bl-sm bg-panel2 border border-edge px-4 py-2.5 max-w-[85%]">
                <p className="text-sm text-inkSoft whitespace-pre-wrap leading-relaxed">{t.answer}</p>
              </div>
            ) : !t.done ? (
              <div className="flex items-center gap-2 text-inkFaint text-xs"><span className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" /> working…</div>
            ) : null}
          </div>
        ))}
      </div>

      {/* Input */}
      <form onSubmit={(e) => { e.preventDefault(); ask(input) }} className="p-3 border-t border-edge flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          placeholder="Ask about deadlines, penalties, a regulation change…"
          className="os-input flex-1 px-3 py-2.5 text-sm"
        />
        <button type="submit" disabled={busy || !input.trim()} className="os-btn-accent px-4 py-2.5 text-sm flex items-center gap-2">
          {busy
            ? <span className="w-4 h-4 border-2 border-canvas border-t-transparent rounded-full animate-spin" />
            : <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 6l6 6-6 6" /></svg>}
        </button>
      </form>
    </div>
  )
}
