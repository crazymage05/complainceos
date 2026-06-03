import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-canvas text-ink flex items-center justify-center p-6">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-accent/10 border border-accent/30 mb-6">
          <svg className="w-9 h-9 text-accent-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <p className="text-6xl font-black text-ink tracking-tight">404</p>
        <p className="text-inkMute mt-2 mb-6">This page isn't on the compliance map.</p>
        <Link to="/" className="os-btn-accent px-5 py-2.5 text-sm inline-block">
          Back to dashboard
        </Link>
      </div>
    </div>
  )
}
