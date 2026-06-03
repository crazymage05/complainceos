import { useRef, useState } from 'react'
import clsx from 'clsx'
import { chatDiscover, type ChatMessage, type DiscoveredObligation } from '../services/api'
import { pushToast } from './Toaster'

interface Props {
  businessId: string
  businessName: string
  onGoToObligations: () => void
}

const URGENCY_TONE: Record<DiscoveredObligation['urgency'], string> = {
  immediate: 'bg-red-500/15 text-red-300',
  next_30_days: 'bg-amber-500/15 text-amber-300',
  annual: 'bg-accent/15 text-accent-soft',
}
const URGENCY_LABEL: Record<DiscoveredObligation['urgency'], string> = {
  immediate: 'Immediate',
  next_30_days: 'Next 30 days',
  annual: 'Annual',
}

const INTRO = "Hi! I'm your compliance advisor. Tell me about how your business actually operates — contract workers, delivery apps, exports, multiple locations — and I'll surface obligations you might be missing."

export default function AIAdvisorTab({ businessId, businessName, onGoToObligations }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', content: INTRO }])
  const [discovered, setDiscovered] = useState<DiscoveredObligation[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([
    'We use delivery platforms like Swiggy/Zomato',
    'We employ contract workers',
    'We have more than 10 employees',
  ])
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [facts, setFacts] = useState<Record<string, any>>({})
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  function scrollToEnd() {
    requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }))
  }

  async function send(text: string, summarise = false) {
    if ((!text.trim() && !summarise) || busy) return
    setBusy(true)
    const userMsgs: ChatMessage[] = summarise
      ? messages
      : [...messages, { role: 'user', content: text.trim() } as ChatMessage]
    if (!summarise) {
      setMessages(userMsgs)
      setInput('')
      scrollToEnd()
    }
    try {
      const res = await chatDiscover(businessId, userMsgs, facts, summarise)
      setMessages((prev) => summarise ? [...prev, { role: 'assistant', content: res.reply }] : [...userMsgs, { role: 'assistant', content: res.reply }])
      setFacts(res.business_facts ?? facts)
      setSuggestions(res.suggestions ?? [])
      if (res.discovered?.length) {
        setDiscovered((prev) => {
          const seen = new Set(prev.map((d) => d.name.toLowerCase()))
          const merged = [...prev]
          for (const d of res.discovered) {
            if (!seen.has(d.name.toLowerCase())) { merged.push(d); seen.add(d.name.toLowerCase()) }
          }
          return merged
        })
      }
      scrollToEnd()
    } catch (err: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const status = (err as any)?.response?.status
      pushToast(status === 429 ? "Gemini's daily quota is exhausted — try again later." : 'Advisor request failed.', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Chat */}
      <div className="lg:col-span-2 os-panel flex flex-col h-[68vh]">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-3">
          {messages.map((m, i) => (
            <div key={i} className={clsx('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div className={clsx(
                'max-w-[85%] px-4 py-2.5 text-sm leading-relaxed',
                m.role === 'user'
                  ? 'bg-accent/15 border border-accent/25 text-inkSoft rounded-2xl rounded-br-sm'
                  : 'bg-panel2 border border-edge text-inkSoft rounded-2xl rounded-bl-sm whitespace-pre-wrap',
              )}>
                {m.content}
              </div>
            </div>
          ))}
          {busy && <div className="flex items-center gap-2 text-inkFaint text-xs"><span className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" /> advisor is thinking…</div>}
        </div>

        {suggestions.length > 0 && (
          <div className="px-3 pt-2 flex flex-wrap gap-1.5">
            {suggestions.map((s) => (
              <button key={s} onClick={() => send(s)} disabled={busy}
                className="text-xs px-2.5 py-1 rounded-full bg-white/5 border border-edge text-inkMute hover:bg-white/10 transition-colors">
                {s}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={(e) => { e.preventDefault(); send(input) }} className="p-3 flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)} disabled={busy}
            placeholder="Describe how your business operates…"
            className="os-input flex-1 px-3 py-2.5 text-sm" />
          <button type="submit" disabled={busy || !input.trim()} className="os-btn-accent px-4 py-2.5 text-sm">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 6l6 6-6 6" /></svg>
          </button>
        </form>
      </div>

      {/* Discovered panel */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-inkSoft">Discovered for {businessName}</h3>
          {discovered.length > 0 && (
            <span className="os-chip text-[11px] px-2 py-0.5">{discovered.length}</span>
          )}
        </div>

        {discovered.length === 0 ? (
          <div className="os-card p-6 text-center text-inkFaint">
            <p className="text-xs">Obligations the advisor uncovers will collect here, and are added to your plan as proposals.</p>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {discovered.map((d, i) => (
                <div key={i} className="os-card p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={clsx('text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full', URGENCY_TONE[d.urgency])}>
                      {URGENCY_LABEL[d.urgency]}
                    </span>
                    <span className="text-[10px] text-inkFaint capitalize">{d.category.replace(/_/g, ' ')}</span>
                  </div>
                  <p className="text-sm font-medium text-ink">{d.name}</p>
                  <p className="text-xs text-inkMute mt-0.5">{d.reason}</p>
                </div>
              ))}
            </div>
            <button onClick={onGoToObligations} className="os-btn-accent w-full px-4 py-2 text-sm">
              Review in Obligations →
            </button>
          </>
        )}

        <button onClick={() => send('', true)} disabled={busy || messages.length < 2}
          className="os-btn-ghost w-full px-4 py-2 text-xs">
          Summarise everything found
        </button>
      </div>
    </div>
  )
}
