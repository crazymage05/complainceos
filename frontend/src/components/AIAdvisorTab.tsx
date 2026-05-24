import { useState, useEffect, useRef } from 'react'
import clsx from 'clsx'
import {
  chatDiscover,
  getChatDiscoveries,
  interpretCircular,
  type ChatMessage,
  type ChatDiscovery,
  type DiscoveredObligation,
  type CircularInterpretResponse,
} from '../services/api'

interface AIAdvisorTabProps {
  businessId: string
  businessName: string
  onGoToObligations: () => void
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  discovered?: DiscoveredObligation[]
  suggestions?: string[]
}

// Fix 1: Generic opener — doesn't telegraph the Swiggy discovery
const OPENER: DisplayMessage = {
  role: 'assistant',
  content:
    "To make sure we haven't missed any compliance obligations, I'd like to ask a few questions about how your business actually operates. Let's start — what does your business sell or do, and how do your customers typically buy from you?",
  discovered: [],
  suggestions: ['We sell food / run a restaurant', 'We sell products online', 'We provide services to businesses', 'We run a retail shop'],
}

const URGENCY_STYLES: Record<string, string> = {
  immediate: 'bg-red-100 text-red-700',
  next_30_days: 'bg-amber-100 text-amber-700',
  annual: 'bg-gray-100 text-gray-600',
}

const CIRCULAR_CHAR_LIMIT = 8000

// Reconstruct baseline business_facts from persisted discoveries so Gemini
// doesn't re-ask questions already answered in a previous session.
function seedFactsFromDiscoveries(discoveries: ChatDiscovery[]): Record<string, unknown> {
  if (!discoveries.length) return {}
  const facts: Record<string, unknown> = { onboarding_started: true }
  for (const d of discoveries) {
    const n = d.obligation_name.toLowerCase()
    const c = d.category.toLowerCase()
    if (n.includes('tcs') || n.includes('ecommerce') || n.includes('e-commerce') || n.includes('delivery platform')) {
      facts['uses_delivery_platforms'] = true
    }
    if (n.includes('epf') || n.includes('pf') || n.includes('esi') || n.includes('contract worker') || c === 'labour') {
      facts['has_employees'] = true
    }
    if (n.includes('fssai') || c === 'food_safety') {
      facts['serves_food'] = true
    }
    if (n.includes('posh') || n.includes('sexual harassment')) {
      facts['has_10_plus_employees'] = true
    }
    if (n.includes('import') || n.includes('export') || n.includes('iec')) {
      facts['has_international_trade'] = true
    }
    if (n.includes('fire') || n.includes('noc')) {
      facts['has_physical_premises'] = true
    }
    if (n.includes('shop') || n.includes('establishment') || c === 'shops_establishments') {
      facts['has_physical_shop'] = true
    }
  }
  return facts
}

function ChatView({
  businessId,
  onGoToObligations,
}: {
  businessId: string
  onGoToObligations: () => void
}) {
  const [messages, setMessages] = useState<DisplayMessage[]>([OPENER])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  // Fix 2: business_facts accumulates across window
  const [businessFacts, setBusinessFacts] = useState<Record<string, unknown>>({})
  // Fix 4: session-discovered (in-memory) + persisted (from DB)
  const [sessionDiscovered, setSessionDiscovered] = useState<DiscoveredObligation[]>([])
  const [persistedDiscoveries, setPersistedDiscoveries] = useState<ChatDiscovery[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  // Load existing discoveries from MongoDB on mount + reconstruct businessFacts
  // so Gemini doesn't re-ask questions from a previous session
  useEffect(() => {
    getChatDiscoveries(businessId)
      .then((discoveries) => {
        setPersistedDiscoveries(discoveries)
        if (discoveries.length) {
          setBusinessFacts(seedFactsFromDiscoveries(discoveries))
        }
      })
      .catch(() => {})
  }, [businessId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send(text: string, isSummary = false) {
    if (!text.trim() || loading) return

    const userMsg: DisplayMessage = { role: 'user', content: text }
    const updated = isSummary ? messages : [...messages, userMsg]
    if (!isSummary) setMessages(updated)
    setInput('')
    setLoading(true)

    try {
      // Pre-seed opener into API context so Gemini has the full conversation
      const apiMessages: ChatMessage[] = [
        { role: 'assistant', content: OPENER.content },
        ...updated.slice(1).map((m) => ({ role: m.role, content: m.content })),
        ...(isSummary ? [{ role: 'user' as const, content: text }] : []),
      ]

      const res = await chatDiscover(businessId, apiMessages, businessFacts, isSummary)

      const assistantMsg: DisplayMessage = {
        role: 'assistant',
        content: res.reply,
        discovered: res.discovered ?? [],
        suggestions: isSummary ? [] : (res.suggestions ?? []),
      }

      setMessages((prev) => [...prev, ...(isSummary ? [{ role: 'user' as const, content: text }, assistantMsg] : [assistantMsg])])

      // Fix 2: Merge returned business_facts into running state
      if (res.business_facts && Object.keys(res.business_facts).length) {
        setBusinessFacts(res.business_facts)
      }

      if (res.discovered?.length) {
        setSessionDiscovered((prev) => [...prev, ...res.discovered])
        // Refresh persisted list to show newly written items
        getChatDiscoveries(businessId).then(setPersistedDiscoveries).catch(() => {})
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: "I'm having trouble connecting right now. Please try again in a moment.",
          discovered: [],
          suggestions: [],
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const totalDiscovered = sessionDiscovered.length

  return (
    <div className="flex flex-col">
      {/* Session discoveries banner */}
      {totalDiscovered > 0 && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl">
          <p className="text-xs font-bold text-amber-700 uppercase tracking-wide mb-2">
            ⚠️ {totalDiscovered} obligation{totalDiscovered > 1 ? 's' : ''} discovered this session
          </p>
          <div className="space-y-1.5">
            {sessionDiscovered.map((o, i) => (
              <div key={i} className="bg-white rounded-lg border border-amber-100 px-3 py-2 text-xs flex items-start gap-2">
                <span className={clsx('mt-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold flex-shrink-0', URGENCY_STYLES[o.urgency] ?? 'bg-gray-100 text-gray-600')}>
                  {o.urgency.replace('_', ' ')}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="font-semibold text-gray-900">{o.name}</span>
                  <span className="text-gray-500 ml-1.5">— {o.reason}</span>
                </div>
                {/* Fix 5: Go to Obligations button on discovery */}
                <button
                  onClick={onGoToObligations}
                  className="flex-shrink-0 text-[10px] px-2 py-0.5 bg-green-100 text-green-700 border border-green-200 rounded-full hover:bg-green-200 transition-colors font-semibold whitespace-nowrap"
                >
                  View Obligations →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Previously persisted discoveries */}
      {persistedDiscoveries.length > 0 && sessionDiscovered.length === 0 && (
        <div className="mb-4 p-3 bg-gray-50 border border-gray-200 rounded-xl">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            {persistedDiscoveries.length} previously flagged obligation{persistedDiscoveries.length > 1 ? 's' : ''}
          </p>
          <div className="space-y-1">
            {persistedDiscoveries.slice(0, 5).map((d, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                <span className={clsx('px-1.5 py-0.5 rounded-full text-[10px] font-bold flex-shrink-0', URGENCY_STYLES[d.urgency] ?? 'bg-gray-100 text-gray-600')}>
                  {d.urgency.replace('_', ' ')}
                </span>
                <span className="font-medium text-gray-800">{d.obligation_name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="overflow-y-auto space-y-4 pr-1" style={{ maxHeight: 380 }}>
        {messages.map((msg, i) => (
          <div key={i} className={clsx('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            <div className="max-w-[82%]">
              {msg.role === 'assistant' && (
                <div className="flex items-center gap-1.5 mb-1">
                  <div className="w-5 h-5 bg-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  <span className="text-xs font-semibold text-purple-700">AI Advisor</span>
                </div>
              )}

              <div className={clsx(
                'rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap',
                msg.role === 'user'
                  ? 'bg-gray-900 text-white rounded-br-sm'
                  : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-bl-sm',
              )}>
                {msg.content}
              </div>

              {/* Inline discovered obligations */}
              {msg.discovered && msg.discovered.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  {msg.discovered.map((o, j) => (
                    <div key={j} className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5 text-xs">
                      <p className="font-bold text-amber-800 mb-0.5">⚠️ Obligation Discovered</p>
                      <p className="font-semibold text-gray-900">{o.name}</p>
                      <p className="text-gray-600 mt-0.5">{o.reason}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Suggestion buttons — only on last assistant message */}
              {msg.role === 'assistant' &&
                msg.suggestions &&
                msg.suggestions.length > 0 &&
                i === messages.length - 1 &&
                !loading && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {msg.suggestions.map((s, j) => (
                      <button
                        key={j}
                        onClick={() => send(s)}
                        className="text-xs px-3 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded-full hover:bg-purple-100 transition-colors font-medium"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div className="w-5 h-5 bg-purple-100 rounded-full flex items-center justify-center">
              <div className="w-2.5 h-2.5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            </div>
            AI Advisor is thinking…
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="mt-3 flex items-center gap-2 pt-3 border-t border-gray-100">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) } }}
          placeholder="Type your answer or click a suggestion above…"
          disabled={loading}
          className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-transparent placeholder-gray-400 disabled:bg-gray-50"
        />
        <button
          onClick={() => send(input)}
          disabled={loading || !input.trim()}
          className="w-10 h-10 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-200 text-white rounded-xl flex items-center justify-center transition-colors flex-shrink-0"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>

      {/* Fix 6: Manual summary button — user-triggered, not auto on message count */}
      {messages.length > 3 && !loading && (
        <button
          onClick={() => send('Please summarise all compliance obligations you have discovered in this conversation as a structured list.', true)}
          className="mt-3 w-full flex items-center justify-center gap-2 py-2 text-xs font-semibold text-purple-700 border border-purple-200 rounded-xl hover:bg-purple-50 transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          Generate Summary Report
        </button>
      )}
    </div>
  )
}

// ─── Circular Interpreter ─────────────────────────────────────────────────────

const EXAMPLE_CIRCULARS = [
  {
    label: 'GST Cloud Kitchen / ECO',
    source: 'CBIC Circular No. 207/19/2023-GST',
    text: `CIRCULAR No. 207/19/2023-GST — Government of India, Ministry of Finance, Department of Revenue, CBIC

Subject: Clarification on GST applicability for cloud kitchen operators supplying food through Electronic Commerce Operators (Swiggy, Zomato, etc.)

1. Representations have been received on whether cloud kitchen operators providing food preparation services through ECOs are liable under Section 9(5) of CGST Act, 2017.

2. Clarified: All restaurant services including cloud kitchens supplied through ECOs are taxable under Section 9(5). The ECO shall be liable to collect and pay tax. Cloud kitchen operators need not register under GST if their exclusive supplies are through ECOs, subject to annual turnover threshold of ₹40 lakh (₹20 lakh for special category states).

3. ECOs must deduct TCS at 1% on net value of taxable supplies. Cloud kitchens must provide GSTIN to ECO or obtain Nil-rated registration if below threshold.

4. This circular is effective from 1st April 2024. All previous clarifications on this matter stand superseded.`,
  },
  {
    label: 'EPF Wage Ceiling Enhanced',
    source: 'EPFO Circular No. EPFO/HO/OT/2024/5523',
    text: `EMPLOYEES' PROVIDENT FUND ORGANISATION — Head Office
Circular No. EPFO/HO/OT/2024/5523, Date: 15th March 2024

Subject: Enhancement of wage ceiling for EPF coverage under EPF & MP Act, 1952

The Central Government has notified enhancement of the wage ceiling from ₹15,000 to ₹21,000 per month for EPF coverage effective 1st April 2024.

All covered establishments must:
1. Enrol all employees drawing wages up to ₹21,000/month as EPF members from 1st April 2024
2. Revise employer contribution — 12% of ₹21,000 = ₹2,520/month per employee
3. Update ECR filings to reflect enhanced wage ceiling — incorrect filings attract interest @ 12% p.a.
4. New joiners in the ₹15,001–₹21,000 band must be enrolled immediately; no exemption for existing employees crossing the old threshold

Penalty for non-compliance: Interest @ 12% p.a. plus damages up to 25% of dues under Section 14B.`,
  },
  {
    label: 'FSSAI Annual Return Deadline',
    source: 'FSSAI Order No. P.17011/100/2024/FSSAI',
    text: `Food Safety and Standards Authority of India — Ministry of Health & Family Welfare
Order No. P.17011/100/2024/FSSAI

Subject: Mandatory Annual Return filing on FoSCoS portal — Revised deadline and new requirements for FY 2024-25

1. Annual Return in Form D-1 for FY 2024-25 shall be filed on FoSCoS portal (foscos.fssai.gov.in) by 31st May 2025 (extended from 30th April 2025).

2. New mandatory fields for FBOs with annual turnover exceeding ₹12 lakh:
   - Number of products manufactured/handled by category
   - Cold chain facilities declaration (if applicable)
   - Third-party audit status

3. Late filing penalty: ₹100 per day per license, maximum ₹5,000.

4. FBOs operating through cloud kitchens and delivery-only models must file separately for each licensed premise.

5. Non-filing may result in show-cause notice and license suspension under FSS Act, 2006, Section 32.`,
  },
]

const URGENCY_CARD: Record<string, { bg: string; border: string; text: string }> = {
  high: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800' },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800' },
  low: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-800' },
}

function CircularView({ businessId }: { businessId: string }) {
  const [source, setSource] = useState('')
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<CircularInterpretResponse | null>(null)

  function loadExample(ex: (typeof EXAMPLE_CIRCULARS)[0]) {
    setSource(ex.source)
    setText(ex.text)
    setResult(null)
  }

  async function analyse() {
    if (!text.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const res = await interpretCircular(businessId, text.trim(), source.trim())
      setResult(res)
    } catch {
      setResult({
        plain_summary: 'Analysis failed — please try again.',
        affected_business_types: [],
        key_changes: [],
        applies_to_this_business: false,
        reason: 'API error',
        urgency: 'medium',
        affected_categories: [],
      })
    } finally {
      setLoading(false)
    }
  }

  const overLimit = text.length > CIRCULAR_CHAR_LIMIT
  const urgencyStyle = result ? (URGENCY_CARD[result.urgency] ?? URGENCY_CARD.medium) : null

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Load example circular</p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_CIRCULARS.map((ex) => (
            <button key={ex.label} onClick={() => loadExample(ex)}
              className="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 border border-blue-100 rounded-lg hover:bg-blue-100 transition-colors font-medium">
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <input type="text" value={source} onChange={(e) => setSource(e.target.value)}
        placeholder="Circular source (e.g. CBIC Circular No. 207/2023)"
        className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent placeholder-gray-400" />

      <div className="relative">
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={9}
          placeholder="Paste the full circular text here…"
          className={clsx(
            'w-full border rounded-xl px-4 py-2.5 text-xs font-mono focus:outline-none focus:ring-2 focus:border-transparent placeholder-gray-400 resize-none',
            overLimit ? 'border-amber-400 focus:ring-amber-400' : 'border-gray-200 focus:ring-blue-400'
          )} />
        <div className={clsx('absolute bottom-2 right-3 text-[10px] font-medium', overLimit ? 'text-amber-600' : 'text-gray-400')}>
          {text.length.toLocaleString()} / {CIRCULAR_CHAR_LIMIT.toLocaleString()} chars
          {overLimit && ' — paste remainder as a second analysis'}
        </div>
      </div>

      <button onClick={analyse} disabled={loading || !text.trim()}
        className="w-full flex items-center justify-center gap-2 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold rounded-xl transition-colors text-sm">
        {loading ? (
          <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Gemini is reading the circular…</>
        ) : (
          <><svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>Analyse Circular</>
        )}
      </button>

      {result && (
        <div className="space-y-4">
          <div className={clsx('flex items-start gap-3 p-4 rounded-xl border-2',
            result.applies_to_this_business ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200')}>
            <div className={clsx('w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0',
              result.applies_to_this_business ? 'bg-red-100' : 'bg-green-100')}>
              {result.applies_to_this_business ? (
                <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>
            <div>
              <p className={clsx('font-bold text-sm', result.applies_to_this_business ? 'text-red-800' : 'text-green-800')}>
                {result.applies_to_this_business ? '⚠️ This circular applies to your business' : '✓ Does not apply to your business'}
              </p>
              <p className="text-xs text-gray-600 mt-0.5">{result.reason}</p>
            </div>
          </div>

          <div className={clsx('rounded-xl border p-4', urgencyStyle?.bg, urgencyStyle?.border)}>
            <p className="text-xs font-bold uppercase tracking-wide mb-2 opacity-60">Plain language summary</p>
            <p className={clsx('text-sm leading-relaxed font-medium', urgencyStyle?.text)}>{result.plain_summary}</p>
          </div>

          {result.key_changes.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-3">Action Required</p>
              <div className="space-y-3">
                {result.key_changes.map((c, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs font-bold text-blue-700">{i + 1}</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{c.change}</p>
                      <p className="text-xs text-gray-400 mt-0.5">Effective: {c.effective_date}</p>
                      <p className="text-xs text-blue-700 mt-0.5 font-medium">→ {c.action_required}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.affected_business_types.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Affected Business Types</p>
              <div className="flex flex-wrap gap-1.5">
                {result.affected_business_types.map((t, i) => (
                  <span key={i} className="text-xs px-2.5 py-1 bg-gray-100 text-gray-700 rounded-full font-medium">{t}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Main Export ──────────────────────────────────────────────────────────────

export default function AIAdvisorTab({ businessId, businessName, onGoToObligations }: AIAdvisorTabProps) {
  const [subTab, setSubTab] = useState<'chat' | 'circular'>('chat')

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-semibold text-gray-800">AI Compliance Advisor</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Powered by Gemini — discovers hidden obligations and interprets government circulars for {businessName}
        </p>
      </div>

      <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        <button onClick={() => setSubTab('chat')}
          className={clsx('px-4 py-2 rounded-lg text-sm font-semibold transition-all',
            subTab === 'chat' ? 'bg-white text-purple-700 shadow-sm' : 'text-gray-500 hover:text-gray-700')}>
          Discover Obligations
        </button>
        <button onClick={() => setSubTab('circular')}
          className={clsx('px-4 py-2 rounded-lg text-sm font-semibold transition-all',
            subTab === 'circular' ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-700')}>
          Read Circular
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        {subTab === 'chat'
          ? <ChatView businessId={businessId} onGoToObligations={onGoToObligations} />
          : <CircularView businessId={businessId} />
        }
      </div>
    </div>
  )
}
