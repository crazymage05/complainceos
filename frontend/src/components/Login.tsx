import { useState } from 'react'
import { signInWithGoogle } from '../services/firebase'

export default function Login() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleGoogle() {
    setLoading(true)
    setError(null)
    try {
      await signInWithGoogle()
      // App.tsx will redirect via onAuthChange
    } catch (err) {
      setError('Sign-in failed. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen bg-canvas flex items-center justify-center p-4 overflow-hidden">
      {/* Ambient emerald glow */}
      <div className="pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-accent/10 blur-[120px]" />

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-accent rounded-2xl shadow-glow mb-4">
            <svg className="w-9 h-9 text-canvas" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-ink">ComplianceOS</h1>
          <p className="text-inkMute mt-2 text-sm">AI-powered compliance for Indian businesses</p>
        </div>

        {/* Card */}
        <div className="os-panel shadow-panel p-8">
          <h2 className="text-xl font-semibold text-ink mb-2">Welcome back</h2>
          <p className="text-inkMute text-sm mb-6">
            Sign in to manage your compliance obligations and never miss a deadline.
          </p>

          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-300 text-sm">
              {error}
            </div>
          )}

          <button
            onClick={handleGoogle}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-edge rounded-xl text-inkSoft font-medium hover:bg-white/5 hover:border-edge transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-inkMute border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            )}
            {loading ? 'Signing in…' : 'Continue with Google'}
          </button>

          <p className="text-xs text-inkFaint text-center mt-4">
            By signing in, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>

        {/* Features */}
        <div className="mt-8 grid grid-cols-3 gap-4">
          {[
            { icon: '⚡', title: 'AI-Driven', desc: 'Decay scoring' },
            { icon: '🔔', title: 'Ripple Alerts', desc: 'Reg changes' },
            { icon: '📄', title: 'Auto Drafts', desc: 'One-click file' },
          ].map((f) => (
            <div key={f.title} className="text-center p-3 os-card">
              <div className="text-2xl mb-1">{f.icon}</div>
              <div className="text-xs font-semibold text-inkSoft">{f.title}</div>
              <div className="text-xs text-inkFaint">{f.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
