import { useNavigate } from 'react-router-dom'

interface Props {
  signedIn: boolean
}

const STATS = [
  { number: '64.5M', label: 'MSMEs in India' },
  { number: '1,450', label: 'compliance obligations per business per year' },
  { number: '42', label: 'regulatory updates every single day' },
  { number: '₹89,000Cr', label: 'penalties collected from MSMEs annually' },
]

const FEATURES = [
  {
    icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
    title: 'Compliance DNA',
    desc: 'A unique obligation set for your business — matched against 90 Indian regulations by state, entity type, age, and turnover.',
  },
  {
    icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6',
    title: 'Decay Score',
    desc: 'Every obligation gets a 0-100 urgency score that compounds as deadlines near. Color-coded red/amber/green.',
  },
  {
    icon: 'M3 12h6m6 0h6M3 6h18M3 18h18',
    title: 'Ripple Detection',
    desc: 'When a new circular drops, MongoDB Atlas Vector Search finds which of your obligations are affected.',
  },
  {
    icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
    title: 'Penalty Prediction',
    desc: 'Exact rupee figure for what you would pay if you missed each filing. Personalized to your size, turnover, and history.',
  },
  {
    icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
    title: 'Auto-Draft Filings',
    desc: 'Pre-populated PDF forms with category-specific advisor notes — documents needed, common mistakes, and a checklist.',
  },
  {
    icon: 'M21 12c0 1.66-4 3-9 3s-9-1.34-9-3m18 0c0-1.66-4-3-9-3s-9 1.34-9 3m18 0v6c0 1.66-4 3-9 3s-9-1.34-9-3v-6',
    title: 'Multi-Agent Reasoning',
    desc: 'A Compliance Officer agent delegates to six specialists, shows every step of its thinking, and explains every score.',
  },
]

export default function Landing({ signedIn }: Props) {
  const navigate = useNavigate()

  const cta = signedIn ? 'Open Dashboard' : 'Sign in to get started'
  const ctaPath = signedIn ? '/dashboard' : '/login'

  return (
    <div className="min-h-screen bg-canvas text-ink">
      {/* Hero */}
      <section className="relative bg-gradient-to-b from-panel to-canvas pb-20 overflow-hidden">
        <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full bg-accent/[0.08] blur-[140px]" />
        <header className="relative px-6 py-5 flex items-center justify-between max-w-6xl mx-auto">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-accent rounded-lg flex items-center justify-center shadow-glow">
              <svg className="w-5 h-5 text-canvas" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="font-bold text-ink">ComplianceOS</span>
          </div>
          <button onClick={() => navigate(ctaPath)} className="os-btn-accent text-xs px-4 py-2">
            {signedIn ? 'Dashboard' : 'Sign in'}
          </button>
        </header>

        <div className="relative max-w-4xl mx-auto px-6 pt-12 text-center">
          <span className="inline-block text-[10px] font-bold uppercase tracking-widest text-accent-soft bg-accent/15 border border-accent/25 px-3 py-1 rounded-full mb-4">
            Google Cloud Rapid Agent Hackathon · MongoDB Track
          </span>
          <h1 className="text-4xl sm:text-5xl font-black text-ink leading-tight">
            India's small businesses owe more in compliance penalties
            <br />
            <span className="bg-gradient-to-r from-accent-soft to-accent bg-clip-text text-transparent">
              than they pay in income tax.
            </span>
          </h1>
          <p className="mt-5 text-inkMute text-base sm:text-lg max-w-2xl mx-auto">
            ComplianceOS replaces a ₹5 lakh/year CA retainer with a ₹500/month AI agent.
            Built on Gemini, Agent Development Kit, and MongoDB Atlas.
          </p>
          <div className="mt-7 flex items-center justify-center gap-3 flex-wrap">
            <button onClick={() => navigate(ctaPath)} className="os-btn-accent px-5 py-2.5 text-sm">
              {cta} →
            </button>
            <a href="https://github.com" className="os-btn-ghost px-5 py-2.5 text-sm flex items-center gap-2">
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
              </svg>
              View on GitHub
            </a>
          </div>
        </div>

        {/* Numbers band */}
        <div className="relative max-w-5xl mx-auto px-6 mt-16 grid grid-cols-2 sm:grid-cols-4 gap-4">
          {STATS.map((s) => (
            <div key={s.label} className="os-card p-5 text-center">
              <p className="text-3xl sm:text-4xl font-black text-ink">{s.number}</p>
              <p className="text-[11px] text-inkMute mt-1 leading-snug">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Before / After */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <h2 className="text-2xl sm:text-3xl font-black text-ink text-center mb-3">
          Before ComplianceOS vs After
        </h2>
        <p className="text-center text-inkMute text-sm mb-10 max-w-xl mx-auto">
          Indian MSMEs spend ₹13–17 lakh/year on compliance — mostly on CA retainers to track deadlines.
          We turn that into ₹500/month of peace of mind.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="bg-red-500/[0.07] border border-red-500/20 rounded-2xl p-6">
            <p className="text-[10px] font-bold uppercase tracking-widest text-red-300 mb-3">Without ComplianceOS</p>
            <ul className="space-y-2.5 text-sm text-inkSoft">
              <li className="flex items-start gap-2"><span className="text-red-400 mt-0.5">✕</span> CA retainer ₹40,000-₹2,00,000/year</li>
              <li className="flex items-start gap-2"><span className="text-red-400 mt-0.5">✕</span> Track 1,450 obligations in Excel</li>
              <li className="flex items-start gap-2"><span className="text-red-400 mt-0.5">✕</span> Miss a deadline, pay ₹50/day penalty + interest</li>
              <li className="flex items-start gap-2"><span className="text-red-400 mt-0.5">✕</span> Read 42 new circulars every day to know what changed</li>
              <li className="flex items-start gap-2"><span className="text-red-400 mt-0.5">✕</span> Hire someone to fill GSTR-3B from scratch every month</li>
            </ul>
          </div>
          <div className="bg-accent/[0.07] border border-accent/25 rounded-2xl p-6">
            <p className="text-[10px] font-bold uppercase tracking-widest text-accent-soft mb-3">With ComplianceOS</p>
            <ul className="space-y-2.5 text-sm text-inkSoft">
              <li className="flex items-start gap-2"><span className="text-accent-soft mt-0.5">✓</span> ₹500/month subscription</li>
              <li className="flex items-start gap-2"><span className="text-accent-soft mt-0.5">✓</span> AI agent surfaces what's urgent today</li>
              <li className="flex items-start gap-2"><span className="text-accent-soft mt-0.5">✓</span> Live decay score warns you 30 days out</li>
              <li className="flex items-start gap-2"><span className="text-accent-soft mt-0.5">✓</span> Vector search ripples new circulars to your obligations</li>
              <li className="flex items-start gap-2"><span className="text-accent-soft mt-0.5">✓</span> One-click filing draft with checklist + PDF download</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Features grid */}
      <section className="bg-panel/40 border-y border-edge py-20">
        <div className="max-w-5xl mx-auto px-6">
          <h2 className="text-2xl sm:text-3xl font-black text-ink text-center mb-3">
            Six AI capabilities. One compliance officer.
          </h2>
          <p className="text-center text-inkMute text-sm mb-10 max-w-xl mx-auto">
            Powered by Gemini 2.0 Flash, orchestrated through Google Agent Development Kit,
            grounded in MongoDB Atlas — Vector Search, Atlas Search, Time Series, and Aggregations.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className="os-card os-card-hover p-5">
                <div className="w-10 h-10 bg-accent/15 rounded-xl flex items-center justify-center mb-3">
                  <svg className="w-5 h-5 text-accent-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={f.icon} />
                  </svg>
                </div>
                <h3 className="font-bold text-ink text-sm mb-1">{f.title}</h3>
                <p className="text-xs text-inkMute leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stack band */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <h3 className="text-xs font-bold uppercase tracking-widest text-inkMute text-center mb-6">
          Built on
        </h3>
        <div className="flex items-center justify-center gap-3 flex-wrap text-sm font-semibold text-inkMute">
          {['Gemini 2.0 Flash', 'Google ADK 2.0', 'MongoDB Atlas', 'Vector Search', 'Atlas Search', 'Time Series', 'MongoDB MCP'].map((s) => (
            <span key={s} className="px-4 py-2 bg-white/5 border border-edge rounded-full">{s}</span>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-gradient-to-br from-accent to-accent-deep text-canvas py-20">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl sm:text-4xl font-black mb-3">
            Stop paying penalties for deadlines you didn't know existed.
          </h2>
          <p className="text-canvas/80 text-sm sm:text-base mb-7 max-w-xl mx-auto">
            60 seconds to onboard. The agent does the rest.
          </p>
          <button
            onClick={() => navigate(ctaPath)}
            className="px-6 py-3 bg-canvas text-accent-soft text-sm font-bold rounded-xl hover:bg-panel transition-colors"
          >
            {cta} →
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-edge py-8">
        <div className="max-w-5xl mx-auto px-6 flex items-center justify-between flex-wrap gap-4 text-xs text-inkMute">
          <span>© 2026 ComplianceOS · MIT License</span>
          <span>Built for the Google Cloud Rapid Agent Hackathon</span>
        </div>
      </footer>
    </div>
  )
}
